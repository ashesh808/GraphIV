"""Phase-3 entry point — build the labeled citation graph (preprocessing).

One stage per invocation (--set-stage), each a resume-safe sub-pipeline:
  parse  — HTML -> matched citations (selectolax + layered resolver) -> Postgres `citation`
  label  — teacher pseudo-labels; --set-step {sample,teacher,sample_rare}
  bert   — DistilBERT student; --set-step {train,infer}

Non-destructive: every stage is idempotent (skip-sets / WHERE x IS NULL / IF NOT EXISTS).
--dry-run runs read-only probes of the current artifacts and prints the sub-argv it would
dispatch, without importing the heavy stage modules or touching data.
    uv run python phases/phase-3/run.py --set-stage parse [--set-workers N] [--dry-run]
    uv run python phases/phase-3/run.py --set-stage label --set-step teacher
    uv run python phases/phase-3/run.py --set-stage bert  --set-step infer
"""

from __future__ import annotations

import importlib
import sqlite3
import sys
from pathlib import Path
from typing import LiteralString, cast

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "components"))
sys.path.insert(0, str(_HERE.parent))

from _framework import print_config, resolve  # noqa: E402

# Module + main() to dispatch, keyed by (stage, step). step "" = stage default.
_DISPATCH: dict[tuple[str, str], str] = {
    ("parse", ""): "parse.visualize",
    ("label", "sample"): "label.sample",
    ("label", "teacher"): "label.teacher",
    ("label", "sample_rare"): "label.sample_rare",
    ("bert", "train"): "bert.train",
    ("bert", "infer"): "bert.infer",
}


def _sub_argv(stage: str, step: str, c: dict[str, object]) -> list[str]:
    """Translate resolved config into the chosen stage module's native argv."""
    if stage == "parse":
        argv = [
            "--workers",
            str(c["workers"]),
            "--checkpoint-every",
            str(c["checkpoint_every"]),
        ]
        if int(c["limit"]) > 0:  # pyright: ignore[reportArgumentType]
            argv += ["--limit", str(c["limit"])]
        if bool(c["no_write"]):
            argv += ["--no-write"]
        return argv
    if stage == "label" and step == "sample":
        return ["--target", str(c["sample_target"])]
    if stage == "label" and step == "teacher":
        return [
            "--parallelism",
            str(c["parallelism"]),
            "--batch-size",
            str(c["batch_size"]),
        ]
    if stage == "label" and step == "sample_rare":
        return []
    if stage == "bert" and step == "train":
        return [
            "--epochs",
            str(c["epochs"]),
            "--batch-size",
            str(c["train_batch_size"]),
            "--out-suffix",
            str(c["suffix"]),
        ]
    if stage == "bert" and step == "infer":
        return [
            "--suffix",
            str(c["suffix"]),
            "--batch-size",
            str(c["infer_batch_size"]),
        ]
    return []


def _pg_count(dsn: str, query: str) -> int | None:
    """Read-only Postgres scalar; None if PG/table unavailable."""
    try:
        import psycopg

        # Bound the probe: a dry-run must stay responsive, so a count that would
        # seq-scan the 173M-row table aborts quickly instead of hanging.
        with psycopg.connect(dsn, options="-c statement_timeout=15000") as conn:
            row = conn.execute(
                cast(LiteralString, query)
            ).fetchone()  # pyright: ignore[reportAny]
        return int(row[0]) if row else 0  # pyright: ignore[reportAny]
    except Exception as e:  # noqa: BLE001 — probe must never abort a dry-run
        print(f"[phase-3]   (pg probe skipped: {e})")
        return None


def _sqlite_count(db: Path, query: str) -> int | None:
    """Read-only SQLite scalar; None if db/table absent."""
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
        print(f"[phase-3]   (sqlite probe skipped: {e})")
        return None


def _probe(stage: str, step: str) -> None:
    """Report the current artifact state for the chosen stage (no mutation)."""
    import label._common as lc  # light: os/pathlib only

    if stage == "parse":
        n = _pg_count(lc.ARXIVKG_PG_DSN, "SELECT count(*) FROM citation")
        done = _pg_count(
            lc.ARXIVKG_PG_DSN, "SELECT count(DISTINCT citing_id) FROM citation"
        )
        print(f"[phase-3] citation rows={n} citing_papers_done={done}")
    elif stage == "label" and step in ("teacher", ""):
        labels = _sqlite_count(lc.LABELS_DB, "SELECT count(*) FROM label WHERE ok = 1")
        sample = lc.SAMPLE_TXT.stat().st_size if lc.SAMPLE_TXT.exists() else None
        print(
            f"[phase-3] labels.db rows={labels} sample.txt={'present' if sample else 'absent'}"
        )
    elif stage == "label":
        present = lc.SAMPLE_TXT.exists()
        print(
            f"[phase-3] sample.txt={'present' if present else 'absent'} ({lc.SAMPLE_TXT})"
        )
    elif stage == "bert":
        import bert._common as bc

        ckpt = bc.STUDENT_CKPT.exists()
        # mirror infer.count_remaining's filter — uses the partial intent-null index,
        # so it stays cheap instead of seq-scanning the 173M-row table.
        remaining = _pg_count(
            lc.ARXIVKG_PG_DSN,
            "SELECT count(*) FROM citation "
            "WHERE cited_id IS NOT NULL AND sentence IS NOT NULL "
            "AND length(sentence) BETWEEN 30 AND 1000 AND intent IS NULL",
        )
        print(
            f"[phase-3] student_ckpt={'present' if ckpt else 'absent'} remaining_to_label={remaining}"
        )


def main() -> None:
    r = resolve(
        _HERE,
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
        ),
    )
    print_config("phase-3", r)

    stage = str(r.config["stage"])
    step = str(r.config["step"])
    key = (stage, step)
    if key not in _DISPATCH:
        valid = ", ".join(f"{s}/{t}" if t else s for s, t in _DISPATCH)
        raise SystemExit(f"[phase-3] no stage/step '{stage}/{step}'. valid: {valid}")

    target = _DISPATCH[key]
    argv = _sub_argv(stage, step, r.config)
    _probe(stage, step)

    if r.dry_run:
        print(f"[phase-3] would dispatch: {target}.main()  argv={argv}")
        return

    sys.argv = [target, *argv]
    importlib.import_module(target).main()


if __name__ == "__main__":
    main()
