"""
Label every resolved citation edge with a student, into a side table

Nothing writes citation.intent, so a relabel never destroys the labels already in the graph
Progress is one committed key, so an interrupted run resumes from the row after it
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from typing import cast

from ._common import (
    ARXIVKG_PG_DSN,
    INTENTS,
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

# citation sentences are short, and 128 tokens covers about 99% of them
INFER_SEQ_LEN: int = 128

DEFAULT_TABLE: str = "citation_intent_v2"

# one keyset page, sized so a commit lands every few seconds
DEFAULT_CHUNK: int = 200_000


def ensure_table(conn: psycopg.Connection[tuple[object, ...]], table: str) -> None:
    """
    Create the target table and its progress row idempotently
    """
    ident = sql.Identifier(table)
    with conn.cursor() as cur:
        _ = cur.execute(
            sql.SQL(
                "CREATE TABLE IF NOT EXISTS {t} ("
                "  citing_id INT NOT NULL,"
                "  ordinal INT NOT NULL,"
                "  intent TEXT NOT NULL,"
                "  intent_score REAL NOT NULL,"
                "  PRIMARY KEY (citing_id, ordinal)"
                ")"
            ).format(t=ident)
        )
        _ = cur.execute(
            sql.SQL(
                "CREATE TABLE IF NOT EXISTS {p} ("
                "  table_name TEXT PRIMARY KEY,"
                "  citing_id INT NOT NULL,"
                "  ordinal INT NOT NULL,"
                "  n_done BIGINT NOT NULL DEFAULT 0"
                ")"
            ).format(p=sql.Identifier(f"{table}_progress"))
        )
    conn.commit()


def read_progress(conn: psycopg.Connection[tuple[object, ...]], table: str) -> tuple[int, int, int]:
    """
    The last committed key and how many rows are behind it
    """
    with conn.cursor() as cur:
        _ = cur.execute(
            sql.SQL("SELECT citing_id, ordinal, n_done FROM {p} WHERE table_name = %s").format(
                p=sql.Identifier(f"{table}_progress")
            ),
            (table,),
        )
        row = cur.fetchone()
    return cast(tuple[int, int, int], row) if row else (-1, -1, 0)


def write_progress(
    conn: psycopg.Connection[tuple[object, ...]],
    table: str,
    key: tuple[int, int],
    n_done: int,
) -> None:
    """
    Record the key of the last row committed to the target
    """
    with conn.cursor() as cur:
        _ = cur.execute(
            sql.SQL(
                "INSERT INTO {p} (table_name, citing_id, ordinal, n_done) VALUES (%s,%s,%s,%s) "
                "ON CONFLICT (table_name) DO UPDATE SET citing_id = EXCLUDED.citing_id, "
                "ordinal = EXCLUDED.ordinal, n_done = EXCLUDED.n_done"
            ).format(p=sql.Identifier(f"{table}_progress")),
            (table, key[0], key[1], n_done),
        )
    conn.commit()


def count_edges(conn: psycopg.Connection[tuple[object, ...]]) -> int:
    """
    How many resolved edges carry a sentence to classify
    """
    with conn.cursor() as cur:
        _ = cur.execute(
            "SELECT count(*) FROM citation WHERE cited_id IS NOT NULL AND sentence IS NOT NULL"
        )
        row = cur.fetchone()
    return int(cast(int, row[0])) if row else 0


def page(
    conn: psycopg.Connection[tuple[object, ...]],
    after: tuple[int, int],
    chunk: int,
) -> list[tuple[int, int, str, str]]:
    """
    One keyset page of edges, ordered so the last row is a resumable checkpoint
    """
    with conn.cursor() as cur:
        _ = cur.execute(
            "SELECT citing_id, ordinal, COALESCE(section,''), sentence FROM citation "
            "WHERE (citing_id, ordinal) > (%s, %s) "
            "  AND cited_id IS NOT NULL AND sentence IS NOT NULL "
            "ORDER BY citing_id, ordinal LIMIT %s",
            (after[0], after[1], chunk),
        )
        return cast(list[tuple[int, int, str, str]], cur.fetchall())


def run(suffix: str, table: str, batch_size: int, chunk: int, limit: int | None) -> None:
    """
    Classify every edge with the chosen student and copy the labels into the target table
    """
    student_dir = MODELS_DIR / f"student-{suffix}"
    ckpt = student_dir / "best.pt"
    if not ckpt.exists():
        raise FileNotFoundError(f"checkpoint not found: {ckpt}")
    model_tag = f"distilbert-{suffix}"

    print(f"loading tokenizer ({MODEL_NAME})", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    print(f"loading checkpoint {ckpt}", flush=True)
    model = load_student(ckpt, DEVICE)

    read_conn = psycopg.connect(ARXIVKG_PG_DSN)
    write_conn = psycopg.connect(ARXIVKG_PG_DSN)
    ensure_table(write_conn, table)
    last_cid, last_ord, n_done = read_progress(write_conn, table)
    total = count_edges(read_conn)
    print(f"edges to label: {total:,} (resuming after {last_cid}/{last_ord}, {n_done:,} done)")
    print(f"target: {table}  model={model_tag}  bs={batch_size}  chunk={chunk:,}", flush=True)

    dist: Counter[str] = Counter()
    t_start = time.time()
    copy_sql = sql.SQL("COPY {t} (citing_id, ordinal, intent, intent_score) FROM STDIN").format(
        t=sql.Identifier(table)
    )

    while True:
        rows = page(read_conn, (last_cid, last_ord), chunk)
        if not rows:
            break
        out: list[tuple[int, int, str, float]] = []
        for start in range(0, len(rows), batch_size):
            part = rows[start : start + batch_size]
            enc = tokenizer(
                [r[2] or "(unknown)" for r in part],
                [r[3] for r in part],
                max_length=INFER_SEQ_LEN,
                padding="max_length",
                truncation=True,
                return_tensors="pt",
            )
            input_ids = enc["input_ids"].to(DEVICE, non_blocking=True)
            attention_mask = enc["attention_mask"].to(DEVICE, non_blocking=True)
            with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
                probs = model(input_ids, attention_mask).float().softmax(dim=-1)
                scores, preds = probs.max(dim=-1)
            for r, pi, si in zip(part, preds.cpu().tolist(), scores.cpu().tolist(), strict=True):
                name = INTENTS[int(pi)]
                out.append((r[0], r[1], name, float(si)))
                dist[name] += 1
        with write_conn.cursor() as wcur, wcur.copy(copy_sql) as cp:
            for row in out:
                cp.write_row(row)
        write_conn.commit()
        last_cid, last_ord = rows[-1][0], rows[-1][1]
        n_done += len(rows)
        write_progress(write_conn, table, (last_cid, last_ord), n_done)
        elapsed = time.time() - t_start
        rate = sum(dist.values()) / elapsed if elapsed > 0 else 0.0
        print(
            f"  {n_done:,}/{total:,} ({n_done / max(total, 1):.1%})  {rate:.0f} edge/s  "
            f"eta={(total - n_done) / max(rate, 1e-6) / 3600:.2f} h",
            flush=True,
        )
        if limit is not None and n_done >= limit:
            break

    elapsed = time.time() - t_start
    print(f"\nDONE. {n_done:,} edges in {elapsed / 60:.1f} min", flush=True)
    summary = {
        "model_tag": model_tag,
        "table": table,
        "n_labeled": n_done,
        "elapsed_s": elapsed,
        "intent_distribution": dict(dist),
    }
    _ = (student_dir / f"relabel_{table}.json").write_text(json.dumps(summary, indent=2))
    read_conn.close()
    write_conn.close()


def main() -> None:
    """
    Parse the relabel arguments and run
    """
    ap = argparse.ArgumentParser(description="label every citation edge into a side table")
    _ = ap.add_argument("--suffix", type=str, default="v4")
    _ = ap.add_argument("--table", type=str, default=DEFAULT_TABLE)
    _ = ap.add_argument("--batch-size", type=int, default=512)
    _ = ap.add_argument("--chunk", type=int, default=DEFAULT_CHUNK)
    _ = ap.add_argument("--limit", type=int, default=None)
    ns = ap.parse_args()
    run(
        suffix=str(ns.suffix),  # pyright: ignore[reportAny]
        table=str(ns.table),  # pyright: ignore[reportAny]
        batch_size=int(ns.batch_size),  # pyright: ignore[reportAny]
        chunk=int(ns.chunk),  # pyright: ignore[reportAny]
        limit=None if ns.limit is None else int(ns.limit),  # pyright: ignore[reportAny]
    )


if __name__ == "__main__":
    main()
