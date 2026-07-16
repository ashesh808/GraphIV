"""Migrate the three legacy stores into the single project Postgres+pgvector under ./data/pg.

Sources (read-only):
  - global Postgres `arxiv-citations` (paper + resolved citations)
  - SQLite data/metadata/arxiv.db            (corpus metadata -> paper_meta)
  - SQLite data/metadata/topic_tree_nomic.db (topic tree -> leaf + paper_topic)
  - nomic .npy + old arxiv_latest.db row order (embeddings -> paper_embedding)

Stages (idempotent; each TRUNCATEs its target then reloads, or skips if already populated):
  paper citation meta emb topic index check

    python phases/phase-4/components/migrate_pg.py --stage paper
    python phases/phase-4/components/migrate_pg.py --stage citation   # the long one (173M rows)
    python phases/phase-4/components/migrate_pg.py --stage all
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, LiteralString, cast

import numpy as np
import psycopg

REPO = Path(__file__).resolve().parents[3]
ARXIV_DB = REPO / "data" / "metadata" / "arxiv.db"
TOPIC_DB = REPO / "data" / "metadata" / "topic_tree_nomic.db"
OLD_SQLITE = Path("/mnt/Vault-Academics/the-great-arxiv-db/data/arxiv_latest.db")
NOMIC_NPY = Path(
    "/mnt/Vault-Academics/the-great-arxiv-db/data/embeddings/embeddings_nomic.npy"
)
NOMIC_MODEL = REPO / "model" / "nomic-embed-text-v2-moe"
NOMIC_PROMPT = "Instruct: classifying the research topic of a paper's abstract.\nQuery:"

SRC_DSN = "dbname=arxiv-citations host=/run/postgresql"
DST_DSN = f"host={REPO}/.pg port=5433 dbname=arxivkg"

# citation columns copied server-to-server (parse-scratch + dead intent_v3 deliberately excluded)
CIT_COLS = (
    "citing_id,ordinal,bib_local_id,cited_id,method,score,section,sentence,"
    "intent,intent_score,intent_model,polarity,polarity_score"
)


def log(msg: str) -> None:
    print(f"[migrate {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def arxiv_year(aid: str) -> int | None:
    """Year from a modern (YYMM.NNNNN) or legacy (archive/YYMMNNN) arxiv id."""
    m = re.match(r"^(\d{2})(\d{2})\.\d{4,5}", aid)
    if m:
        return 2000 + int(m.group(1))
    m = re.match(r"^[a-z-]+(?:\.[A-Za-z-]+)?/(\d{2})(\d{2})\d{3}", aid)
    if m:
        yy = int(m.group(1))
        return (1900 + yy) if yy >= 91 else (2000 + yy)
    return None


def _count(dsn: str, table: str) -> int:
    with psycopg.connect(dsn) as c:
        row = c.execute(cast(LiteralString, f"SELECT count(*) FROM {table}")).fetchone()
        return int(row[0]) if row else 0


# ---------------------------------------------------------------------------------------------
# paper + citation: server-to-server text COPY via psql (fastest; no Python row loop).
# ---------------------------------------------------------------------------------------------
def stage_paper(force: bool) -> None:
    if not force and _count(DST_DSN, "paper") > 0:
        log("paper already populated; skip (use --force)")
        return
    with psycopg.connect(DST_DSN, autocommit=True) as c:
        _ = c.execute("TRUNCATE paper")
    log("copying paper(id, arxiv_id) preserving ids ...")
    _pipe(
        src_sql="\\copy (SELECT id, arxiv_id FROM paper) TO STDOUT",
        dst_sql="\\copy paper (id, arxiv_id) FROM STDIN",
    )
    log(f"paper rows: {_count(DST_DSN, 'paper'):,}")


def stage_citation(force: bool) -> None:
    if not force and _count(DST_DSN, "citation") > 0:
        log("citation already populated; skip (use --force)")
        return
    with psycopg.connect(DST_DSN, autocommit=True) as c:
        _ = c.execute("TRUNCATE citation")
    log(
        "copying citation (slim cols, 173M rows) server-to-server; this is the long one ..."
    )
    t0 = time.time()
    _pipe(
        src_sql=f"\\copy (SELECT {CIT_COLS} FROM citation) TO STDOUT",
        dst_sql=f"\\copy citation ({CIT_COLS}) FROM STDIN",
    )
    log(f"citation rows: {_count(DST_DSN, 'citation'):,} in {time.time()-t0:.0f}s")


def _pipe(src_sql: str, dst_sql: str) -> None:
    src = subprocess.Popen(
        ["psql", SRC_DSN, "-v", "ON_ERROR_STOP=1", "-c", src_sql],
        stdout=subprocess.PIPE,
    )
    dst = subprocess.Popen(
        ["psql", DST_DSN, "-v", "ON_ERROR_STOP=1", "-c", dst_sql],
        stdin=src.stdout,
    )
    if src.stdout:
        src.stdout.close()  # let src receive SIGPIPE if dst dies
    dst_rc = dst.wait()
    src_rc = src.wait()
    if src_rc != 0 or dst_rc != 0:
        raise RuntimeError(f"psql pipe failed (src={src_rc} dst={dst_rc})")


# ---------------------------------------------------------------------------------------------
# paper_meta from SQLite arxiv.db.
# ---------------------------------------------------------------------------------------------
def stage_meta(force: bool) -> None:
    # Delta-aware: copies only publications missing from paper_meta (anti-join on
    # arxiv_id), so a re-run after a phase-0/1 seed refresh ingests just the new papers.
    # --force truncates and rebuilds the whole table.
    sc = sqlite3.connect(f"file:{ARXIV_DB}?mode=ro", uri=True)
    with psycopg.connect(DST_DSN, autocommit=True) as c:
        if force:
            _ = c.execute("TRUNCATE paper_meta")
        have: set[str] = {
            cast(str, r[0])
            for r in c.execute(
                "SELECT arxiv_id FROM paper_meta"
            )  # pyright: ignore[reportAny]
        }
    log(f"paper_meta has {len(have):,} rows; scanning SQLite for missing ...")
    log("building primary-category map ...")
    primary: dict[str, str] = {}
    for pid, cat in sc.execute(
        "SELECT publication_id, category FROM categories ORDER BY id"
    ):
        primary.setdefault(str(pid), str(cat))
    log(f"  {len(primary):,} categorized papers")
    with psycopg.connect(DST_DSN, autocommit=True) as c:
        n = 0
        with c.cursor().copy(
            "COPY paper_meta (arxiv_id, title, abstract, year, primary_category, authors)"
            " FROM STDIN"
        ) as cp:
            for pid, title, abstract, authors in sc.execute(
                "SELECT id, title, abstract, authors FROM publication"
            ):
                aid = str(pid)
                if aid in have:
                    continue
                cp.write_row(
                    [aid, title, abstract, arxiv_year(aid), primary.get(aid), authors]
                )
                n += 1
                if n % 500_000 == 0:
                    log(f"  paper_meta +{n:,}")
    sc.close()
    log(f"paper_meta rows: {_count(DST_DSN, 'paper_meta'):,} (+{n:,} new)")


# ---------------------------------------------------------------------------------------------
# paper_embedding from the nomic .npy (row-aligned to old arxiv_latest.db scan order).
# ---------------------------------------------------------------------------------------------
def _emb_ids() -> list[str]:
    sc = sqlite3.connect(f"file:{OLD_SQLITE}?mode=ro", uri=True)
    ids = [str(r[0]) for r in sc.execute("SELECT id FROM publication")]
    sc.close()
    return ids


def stage_emb(force: bool) -> None:
    if not force and _count(DST_DSN, "paper_embedding") > 0:
        log("paper_embedding already populated; skip")
        return
    log("loading nomic .npy (mmap) + reconstructing id order ...")
    emb: np.ndarray = np.load(NOMIC_NPY, mmap_mode="r")
    ids = _emb_ids()
    if len(ids) != emb.shape[0]:
        raise RuntimeError(f"emb/id mismatch: {len(ids)} ids vs {emb.shape[0]} vectors")
    log(f"  {emb.shape[0]:,} vectors x {emb.shape[1]}d")
    with psycopg.connect(DST_DSN, autocommit=True) as c:
        _ = c.execute("TRUNCATE paper_embedding")
        n = 0
        with c.cursor().copy(
            "COPY paper_embedding (arxiv_id, embedding) FROM STDIN"
        ) as cp:
            for i, aid in enumerate(ids):
                vec = emb[i].tolist()
                cp.write_row([aid, "[" + ",".join(repr(x) for x in vec) + "]"])
                n += 1
                if n % 250_000 == 0:
                    log(f"  paper_embedding {n:,}")
    log(f"paper_embedding rows: {_count(DST_DSN, 'paper_embedding'):,}")


# ---------------------------------------------------------------------------------------------
# leaf + paper_topic from topic_tree_nomic.db.
# ---------------------------------------------------------------------------------------------
def stage_topic(force: bool) -> None:
    if not force and _count(DST_DSN, "paper_topic") > 0:
        log("paper_topic already populated; skip")
        return
    sc = sqlite3.connect(f"file:{TOPIC_DB}?mode=ro", uri=True)
    with psycopg.connect(DST_DSN, autocommit=True) as c:
        _ = c.execute("TRUNCATE leaf")
        _ = c.execute("TRUNCATE paper_topic")
        with c.cursor().copy(
            "COPY leaf (leaf_id, size, depth, radius) FROM STDIN"
        ) as cp:
            for row in sc.execute("SELECT leaf_id, size, depth, radius FROM leaf"):
                cp.write_row(list(row))
        with c.cursor().copy(
            "COPY paper_topic (arxiv_id, leaf_id, path, depth) FROM STDIN"
        ) as cp:
            for row in sc.execute(
                "SELECT arxiv_id, leaf_id, path, depth FROM paper_topic"
            ):
                cp.write_row(list(row))
    sc.close()
    log(
        f"leaf={_count(DST_DSN, 'leaf'):,} paper_topic={_count(DST_DSN, 'paper_topic'):,}"
    )


# ---------------------------------------------------------------------------------------------
# indexes (after bulk load).
# ---------------------------------------------------------------------------------------------
def stage_index(_force: bool) -> None:
    stmts = [
        "CREATE INDEX IF NOT EXISTS citation_cited_idx ON citation(cited_id) WHERE cited_id IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS citation_citing_idx ON citation(citing_id)",
        "CREATE INDEX IF NOT EXISTS citation_intent_null_idx ON citation(citing_id, ordinal) WHERE intent IS NULL",
        "CREATE INDEX IF NOT EXISTS paper_emb_hnsw ON paper_embedding USING hnsw (embedding halfvec_cosine_ops)",
        "CREATE INDEX IF NOT EXISTS paper_meta_tsv_idx ON paper_meta USING gin (to_tsvector('english', coalesce(title, '')))",
    ]
    with psycopg.connect(DST_DSN, autocommit=True) as c:
        for s in stmts:
            log(f"index: {s.split('ON')[0].strip()} ...")
            t0 = time.time()
            _ = c.execute(cast(LiteralString, s))
            log(f"  done in {time.time()-t0:.0f}s")


# ---------------------------------------------------------------------------------------------
# alignment spot-check: recompute nomic on a sample, assert cosine ~ 1 vs the stored vector.
# ---------------------------------------------------------------------------------------------
def stage_check(_force: bool) -> None:
    import torch  # noqa: PLC0415
    from sentence_transformers import SentenceTransformer  # noqa: PLC0415

    sc = sqlite3.connect(f"file:{ARXIV_DB}?mode=ro", uri=True)
    with psycopg.connect(DST_DSN) as c:
        rows: list[tuple[str, Any]] = c.execute(
            "SELECT arxiv_id, embedding FROM paper_embedding ORDER BY random() LIMIT 20"
        ).fetchall()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(str(NOMIC_MODEL), trust_remote_code=True, device=dev)
    model.max_seq_length = 2048
    ok = 0
    for aid, stored in rows:
        r = sc.execute(
            "SELECT title, abstract FROM publication WHERE id=?", (aid,)
        ).fetchone()
        if not r:
            log(f"  {aid}: no metadata, skip")
            continue
        doc = f"Title: {r[0]}\nAbstract: {r[1] or ''}"
        v = model.encode([doc], prompt=NOMIC_PROMPT, normalize_embeddings=True)[0]
        sv = np.array([float(x) for x in stored.strip("[]").split(",")])
        cos = float(np.dot(v, sv) / (np.linalg.norm(v) * np.linalg.norm(sv)))
        flag = "OK" if cos > 0.95 else "*** LOW ***"
        log(f"  {aid}: cos={cos:.4f} {flag}")
        ok += cos > 0.95
    sc.close()
    log(f"alignment spot-check: {ok}/{len(rows)} above 0.95 cosine")


# ---------------------------------------------------------------------------------------------
# embed the post-.npy delta (e.g. 2026) so frontier_pull can reach the newest papers (resumable).
# The frozen .npy only covers pre-delta papers; without this, newer years have no vector and
# frontier_pull silently can't surface them.
# ---------------------------------------------------------------------------------------------
def stage_embed_delta(_force: bool) -> None:
    from embed_delta import run as _run  # noqa: PLC0415

    _run()


STAGES = {
    "paper": stage_paper,
    "citation": stage_citation,
    "meta": stage_meta,
    "emb": stage_emb,
    "embed_delta": stage_embed_delta,
    "topic": stage_topic,
    "index": stage_index,
    "check": stage_check,
}
ORDER = ["paper", "citation", "meta", "emb", "embed_delta", "topic", "index", "check"]


def main() -> None:
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--stage", default="all", choices=["all", *STAGES])
    _ = ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    stage: str = args.stage  # pyright: ignore[reportAny]
    force: bool = args.force  # pyright: ignore[reportAny]
    todo = ORDER if stage == "all" else [stage]
    for s in todo:
        log(f"=== stage: {s} ===")
        STAGES[s](force)
    log("done.")


if __name__ == "__main__":
    sys.exit(main())
