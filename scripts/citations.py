"""
Build the citation graph: parse references, teach the labeler, run the student

One call runs one stage and step, and every stage is resume-safe against its own output.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any, LiteralString, cast

from graphiv.core.cli import print_config, resolve

STAGE = "citations"

# (stage, step) -> Preprocessor method; step "" is the stage default
_DISPATCH: dict[tuple[str, str], str] = {
    ("parse", ""): "parse",
    ("label", "gold"): "label_gold",
    ("label", "refine"): "label_refine",
    ("label", "sample"): "label_sample",
    ("label", "teacher"): "label_teacher",
    ("label", "sample_rare"): "label_sample_rare",
    ("bert", "train"): "train_student",
    ("bert", "infer"): "infer_student",
    ("bert", "relabel"): "relabel_edges",
}


def _kwargs(
    stage: str, step: str, c: dict[str, Any]
) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
    """
    Translate the resolved config into the chosen method's keyword arguments

    Args:
        stage: parse, label or bert.
        step: the step within that stage.
        c: the resolved stage config.

    Returns:
        Keyword arguments for the Preprocessor method.
    """
    if stage == "parse":
        out: dict[str, Any] = {  # pyright: ignore[reportExplicitAny]
            "workers": int(c["workers"]),
            "checkpoint_every": int(c["checkpoint_every"]),
            "no_write": bool(c["no_write"]),
        }
        if int(c["limit"]) > 0:
            out["limit"] = int(c["limit"])
        return out
    if stage == "label" and step == "refine":
        return {
            "generations": int(c["generations"]),
            "source": str(c["label_source"]),
            "stratified": int(c["stratified"]),
            "rare": int(c["rare"]),
            "seed": int(c["seed"]),
            "batch_size": int(c["refine_batch_size"]),
            "parallelism": int(c["refine_parallelism"]),
            "holdout": float(c["holdout"]),
        }
    if stage == "label" and step == "sample":
        return {"target": int(c["sample_target"])}
    if stage == "label" and step == "teacher":
        return {
            "parallelism": int(c["parallelism"]),
            "batch_size": int(c["batch_size"]),
            "teacher_model": str(c["teacher_model"]),
            "teacher_prompt": str(c["teacher_prompt"]),
            "labels_db": str(c["labels_db"]),
            "model_tag": str(c["model_tag"]),
        }
    if stage == "bert" and step == "train":
        return {
            "epochs": int(c["epochs"]),
            "batch_size": int(c["train_batch_size"]),
            "suffix": str(c["suffix"]),
            "labels_db": str(c["labels_db"]),
            "dataset_cache": str(c["dataset_cache"]),
            "oversample_power": float(c["oversample_power"]),
            "class_weights": bool(c["class_weights"]),
        }
    if stage == "bert" and step == "infer":
        return {"batch_size": int(c["infer_batch_size"]), "suffix": str(c["suffix"])}
    if stage == "bert" and step == "relabel":
        return {
            "suffix": str(c["suffix"]),
            "table": str(c["intent_table"]),
            "batch_size": int(c["infer_batch_size"]),
            "chunk": int(c["relabel_chunk"]),
        }
    return {}


def _pg_count(dsn: str, query: str) -> int | None:
    """
    Read one Postgres scalar under a timeout, so a dry-run never seq-scans

    Args:
        dsn: connection string.
        query: a scalar-returning SELECT.

    Returns:
        The count, or None when Postgres or the table is unavailable.
    """
    try:
        import psycopg

        with psycopg.connect(dsn, options="-c statement_timeout=15000") as conn:
            row = conn.execute(cast(LiteralString, query)).fetchone()  # pyright: ignore[reportAny]
        return int(row[0]) if row else 0  # pyright: ignore[reportAny]
    except Exception as e:  # noqa: BLE001
        print(f"[{STAGE}]   (pg probe skipped: {e})")
        return None


def _sqlite_count(db: Path, query: str) -> int | None:
    """
    Read one SQLite scalar read-only

    Args:
        db: database file.
        query: a scalar-returning SELECT.

    Returns:
        The count, or None when the file or table is absent.
    """
    if not db.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            row: tuple[int] = conn.execute(query).fetchone()
        finally:
            conn.close()
        return int(row[0])
    except sqlite3.Error as e:
        print(f"[{STAGE}]   (sqlite probe skipped: {e})")
        return None


def _probe(stage: str, step: str, dsn: str) -> None:
    """
    Report the artifact state for the chosen stage without mutating anything

    Args:
        stage: parse, label or bert.
        step: the step within that stage.
        dsn: Postgres connection string.
    """
    import graphiv.preprocess.label._common as lc

    if stage == "parse":
        n = _pg_count(dsn, "SELECT count(*) FROM citation")
        done = _pg_count(dsn, "SELECT count(DISTINCT citing_id) FROM citation")
        print(f"[{STAGE}] citation rows={n} citing_papers_done={done}")
    elif stage == "label" and step == "refine":
        n = _pg_count(dsn, "SELECT count(*) FROM gold_label WHERE intent IS NOT NULL")
        print(f"[{STAGE}] gold_label: {n if n is not None else '?'} labeled rows")
    elif stage == "label" and step in ("teacher", ""):
        labels = _sqlite_count(lc.LABELS_DB, "SELECT count(*) FROM label WHERE ok = 1")
        sample = lc.SAMPLE_TXT.exists()
        print(f"[{STAGE}] labels.db rows={labels} sample.txt={'present' if sample else 'absent'}")
    elif stage == "label":
        print(f"[{STAGE}] sample.txt={'present' if lc.SAMPLE_TXT.exists() else 'absent'}")
    elif stage == "bert" and step == "relabel":
        n = _pg_count(dsn, "SELECT count(*) FROM citation_intent_v2")
        print(f"[{STAGE}] citation_intent_v2 rows={n if n is not None else 0}")
    elif stage == "bert":
        import graphiv.preprocess.intent._common as bc

        # mirrors infer.count_remaining so the partial intent-null index is used
        remaining = _pg_count(
            dsn,
            "SELECT count(*) FROM citation "
            "WHERE cited_id IS NOT NULL AND sentence IS NOT NULL "
            "AND length(sentence) BETWEEN 30 AND 1000 AND intent IS NULL",
        )
        ckpt = bc.STUDENT_CKPT.exists()
        print(f"[{STAGE}] student_ckpt={'present' if ckpt else 'absent'} remaining={remaining}")


def main() -> None:
    """
    Dispatch one citation-graph stage and step onto the Preprocessor
    """
    r = resolve(
        STAGE,
        sys.argv[1:],
        required=(
            "stage",
            "step",
            "limit",
            "workers",
            "checkpoint_every",
            "no_write",
            "sample_target",
            "parallelism",
            "batch_size",
            "epochs",
            "train_batch_size",
            "infer_batch_size",
            "suffix",
            "holdout",
            "teacher_model",
            "teacher_prompt",
            "labels_db",
            "model_tag",
            "dataset_cache",
            "intent_table",
            "relabel_chunk",
            "oversample_power",
            "class_weights",
        ),
    )
    print_config(STAGE, r)

    stage = str(r.config["stage"])
    step = str(r.config["step"])
    key = (stage, step)
    if key not in _DISPATCH:
        valid = ", ".join(f"{s}/{t}" if t else s for s, t in _DISPATCH)
        raise SystemExit(f"[{STAGE}] no stage/step '{stage}/{step}'. valid: {valid}")

    method = _DISPATCH[key]
    kwargs = _kwargs(stage, step, r.config)
    _probe(stage, step, r.globals.pg_dsn)

    if r.dry_run:
        print(f"[{STAGE}] would dispatch: Preprocessor.{method}(**{kwargs})")
        return

    from graphiv import Preprocessor

    getattr(Preprocessor.from_config(r.globals), method)(**kwargs)


if __name__ == "__main__":
    main()
