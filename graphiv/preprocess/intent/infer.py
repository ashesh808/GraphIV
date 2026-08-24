"""
Run the trained student over the full citation corpus and write the labels back

Rows stream from a server-side cursor, so the 173M-row table never lands in memory
Updates batch through a staging table, since a row-at-a-time update would take days
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import cast

from ._common import (
    ARXIVKG_PG_DSN,
    INTENTS,
    MAX_SEQ_LEN,
    MODEL_NAME,
    MODELS_DIR,
    pin_hf_cache,
)

pin_hf_cache()

import psycopg  # noqa: E402
import torch  # noqa: E402
from psycopg import sql  # noqa: E402
from transformers import AutoTokenizer  # noqa: E402

from .model import load_student  # noqa: E402

DEVICE: torch.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
INFER_SEQ_LEN: int = 128  # citation sentences are short; 128 covers ~99%

# ---------------------------------------------------------------------------
# Schema helpers


def ensure_columns(conn: psycopg.Connection[tuple[object, ...]]) -> None:
    """
    Create the staging table idempotently
    """
    with conn.cursor() as cur:
        _ = cur.execute(
            sql.SQL(
                "CREATE UNLOGGED TABLE IF NOT EXISTS label_staging ("
                "  citing_id INT NOT NULL,"
                "  ordinal   INT NOT NULL,"
                "  intent    TEXT NOT NULL,"
                "  intent_score REAL NOT NULL"
                ")"
            )
        )
        _ = cur.execute(sql.SQL("TRUNCATE label_staging"))
    conn.commit()


def count_remaining(conn: psycopg.Connection[tuple[object, ...]]) -> int:
    """
    How many usable citations still have no intent label
    """
    with conn.cursor() as cur:
        _ = cur.execute(
            sql.SQL(
                "SELECT COUNT(*) FROM citation "
                "WHERE cited_id IS NOT NULL "
                "  AND sentence IS NOT NULL "
                "  AND length(sentence) BETWEEN 30 AND 1000 "
                "  AND intent IS NULL"
            )
        )
        row = cur.fetchone()
    return int(cast(int, row[0])) if row else 0


def flush_staging(conn: psycopg.Connection[tuple[object, ...]], model_tag: str) -> int:
    """
    UPDATE citation FROM label_staging, return rows affected, then truncate
    """
    with conn.cursor() as cur:
        _ = cur.execute(
            sql.SQL(
                "UPDATE citation c "
                "SET intent = s.intent,"
                "    intent_score = s.intent_score,"
                "    intent_model = {tag} "
                "FROM label_staging s "
                "WHERE c.citing_id = s.citing_id AND c.ordinal = s.ordinal"
            ).format(tag=sql.Literal(model_tag))
        )
        n = cur.rowcount
        _ = cur.execute(sql.SQL("TRUNCATE label_staging"))
    conn.commit()
    return n


# ---------------------------------------------------------------------------
# Inference loop


def run(
    out_suffix: str,
    batch_size: int,
    commit_every: int,
    limit: int | None,
) -> None:
    """
    Label the whole corpus with the trained student and write the results back
    """
    student_dir = MODELS_DIR / f"student-{out_suffix}"
    ckpt = student_dir / "best.pt"
    if not ckpt.exists():
        raise FileNotFoundError(f"checkpoint not found: {ckpt}")
    model_tag = f"distilbert-{out_suffix}"

    print(f"loading tokenizer ({MODEL_NAME})", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    print(f"loading checkpoint {ckpt}", flush=True)
    model = load_student(ckpt, DEVICE)

    print("connecting to Postgres (read + write connections) ...", flush=True)
    read_conn = psycopg.connect(ARXIVKG_PG_DSN)
    write_conn = psycopg.connect(ARXIVKG_PG_DSN)
    ensure_columns(write_conn)
    n_remaining = count_remaining(write_conn)
    print(f"rows to label: {n_remaining:,}", flush=True)
    if limit is not None:
        print(f"  (capped by --limit {limit:,})", flush=True)

    intent_dist: Counter[str] = Counter()
    n_done = 0
    n_committed_total = 0
    n_in_staging = 0
    write_buf: list[tuple[int, int, str, float]] = []
    t_start = time.time()

    print(
        f"streaming citations (model={model_tag}, bs={batch_size}, "
        f"seq_len={INFER_SEQ_LEN}) ...",
        flush=True,
    )

    with read_conn.cursor(name="cit_infer_stream") as cur:
        cur.itersize = batch_size * 8
        _ = cur.execute(
            sql.SQL(
                "SELECT citing_id, ordinal, COALESCE(section,''), sentence "
                "FROM citation "
                "WHERE cited_id IS NOT NULL "
                "  AND sentence IS NOT NULL "
                "  AND length(sentence) BETWEEN 30 AND 1000 "
                "  AND intent IS NULL"
            )
        )

        batch_meta: list[tuple[int, int]] = []
        batch_sections: list[str] = []
        batch_sentences: list[str] = []

        def process_batch() -> None:
            nonlocal n_done, n_in_staging
            if not batch_meta:
                return
            enc = tokenizer(
                batch_sections,
                batch_sentences,
                max_length=INFER_SEQ_LEN,
                padding="max_length",
                truncation=True,
                return_tensors="pt",
            )
            input_ids = enc["input_ids"].to(DEVICE, non_blocking=True)
            attention_mask = enc["attention_mask"].to(DEVICE, non_blocking=True)
            with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
                intent_logits = model(input_ids, attention_mask)
                intent_probs = intent_logits.float().softmax(dim=-1)
                intent_scores, intent_pred = intent_probs.max(dim=-1)
            intent_pred_cpu = intent_pred.cpu().tolist()
            intent_score_cpu = intent_scores.cpu().tolist()
            for (cid, ord_), ipi, isi in zip(
                batch_meta, intent_pred_cpu, intent_score_cpu, strict=False
            ):
                intent_name = INTENTS[int(ipi)]
                write_buf.append((cid, ord_, intent_name, float(isi)))
                intent_dist[intent_name] += 1
            n_done += len(batch_meta)
            n_in_staging += len(batch_meta)
            batch_meta.clear()
            batch_sections.clear()
            batch_sentences.clear()

        def write_to_staging() -> None:
            nonlocal write_buf, n_in_staging
            if not write_buf:
                return
            with write_conn.cursor() as wcur:
                with wcur.copy(
                    sql.SQL(
                        "COPY label_staging (citing_id, ordinal, intent, intent_score) "
                        "FROM STDIN"
                    )
                ) as cp:
                    for row in write_buf:
                        cp.write_row(row)
            write_buf = []

        def commit_chunk() -> None:
            nonlocal n_committed_total, n_in_staging
            write_to_staging()
            if n_in_staging == 0:
                return
            n_updated = flush_staging(write_conn, model_tag)
            n_committed_total += n_updated
            elapsed = time.time() - t_start
            rate = n_done / elapsed if elapsed > 0 else 0
            eta = (
                ((n_remaining if limit is None else min(limit, n_remaining)) - n_done)
                / max(rate, 1e-6)
                / 3600
            )
            print(
                f"  committed {n_updated:,}  total_done={n_done:,}  "
                f"total_in_db={n_committed_total:,}  rate={rate:.0f} cit/s  "
                f"eta={eta:.2f} h",
                flush=True,
            )
            n_in_staging = 0

        for row in cur:
            cid, ord_, section, sentence = cast(tuple[int, int, str, str], row)
            batch_meta.append((cid, ord_))
            batch_sections.append(section or "(unknown)")
            batch_sentences.append(sentence)
            if len(batch_meta) >= batch_size:
                process_batch()
            if n_in_staging >= commit_every:
                commit_chunk()
            if limit is not None and n_done >= limit:
                break

        process_batch()
        commit_chunk()

    elapsed = time.time() - t_start
    print(
        f"\nDONE. {n_done:,} citations labeled in {elapsed / 60:.1f} min "
        f"({n_done / max(elapsed, 1):.0f} cit/s). "
        f"Total rows updated in PG: {n_committed_total:,}",
        flush=True,
    )
    summary = {
        "model_tag": model_tag,
        "n_labeled": n_done,
        "elapsed_s": elapsed,
        "intent_distribution": dict(intent_dist),
    }
    (student_dir / "infer_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"summary -> {student_dir / 'infer_summary.json'}", flush=True)
    read_conn.close()
    write_conn.close()


def main() -> None:
    """
    Parse the inference arguments and run
    """
    parser = argparse.ArgumentParser()
    _ = parser.add_argument(
        "--suffix", type=str, default="v1"
    )  # pyright: ignore[reportUnusedCallResult]
    _ = parser.add_argument(
        "--batch-size", type=int, default=512
    )  # pyright: ignore[reportUnusedCallResult]
    _ = parser.add_argument(
        "--commit-every", type=int, default=1_000_000
    )  # pyright: ignore[reportUnusedCallResult]
    _ = parser.add_argument(  # pyright: ignore[reportUnusedCallResult]
        "--limit", type=int, default=None, help="Stop after N rows (debugging)."
    )
    args = parser.parse_args()
    suffix: str = args.suffix  # pyright: ignore[reportAny]
    batch_size: int = int(args.batch_size)  # pyright: ignore[reportAny]
    commit_every: int = int(args.commit_every)  # pyright: ignore[reportAny]
    limit: int | None = (
        int(args.limit) if args.limit is not None else None  # pyright: ignore[reportAny]
    )
    _ = MAX_SEQ_LEN  # imported for future use (training max), suppress unused warning
    _ = Path  # same
    run(suffix, batch_size, commit_every, limit)


if __name__ == "__main__":
    main()
