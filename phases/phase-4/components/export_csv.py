"""Step 1 — export Neo4j bulk-import CSVs from Postgres + SQLite.

Nodes come from the current SQLite (`publication` + `categories`); edges come
from the resolved citations in Postgres, with citing/cited integer ids mapped
back to arxiv_id (the Neo4j node key) via an in-memory dict loaded once.

Outputs (in out/): nodes_header.csv, nodes.csv, edges_header.csv, edges.csv
"""

from __future__ import annotations

import csv
import sqlite3
import time

import psycopg

from _common import (
    EDGES_CSV,
    EDGES_HEADER,
    NODES_CSV,
    NODES_HEADER,
    OUT_DIR,
    PG_DSN,
    SQLITE_DB,
    arxiv_year,
)

NODE_HEADER = "arxiv_id:ID,title,year:int,primary_category"
EDGE_HEADER = ":START_ID,:END_ID,intent,polarity,intent_score:float,ordinal:int"


def _clean(text: str | None) -> str:
    """Collapse all whitespace (incl. embedded newlines/tabs) to single spaces.

    arXiv titles frequently contain hard line breaks; left in, csv.writer emits
    quoted multi-line fields that neo4j-admin rejects without --multiline-fields.
    """
    return " ".join((text or "").split())


def _primary_categories(conn: sqlite3.Connection) -> dict[str, str]:
    """publication_id -> 'cs.LG' (first-listed category, lowest categories.id)."""
    primary: dict[str, str] = {}
    cur = conn.execute(
        "SELECT publication_id, category, subcategory FROM categories ORDER BY id"
    )
    for pub_id, cat, sub in cur:
        if pub_id in primary:
            continue  # first row wins = primary category
        primary[pub_id] = f"{cat}.{sub}" if sub else cat
    return primary


def export_nodes() -> int:
    conn = sqlite3.connect(f"file:{SQLITE_DB}?mode=ro", uri=True)
    try:
        print("[nodes] loading primary categories ...", flush=True)
        primary = _primary_categories(conn)
        print(f"[nodes] {len(primary):,} papers have a category", flush=True)

        NODES_HEADER.write_text(NODE_HEADER + "\n")
        n = 0
        with NODES_CSV.open("w", newline="") as fh:
            w = csv.writer(fh)
            cur = conn.execute("SELECT id, title FROM publication")
            for arxiv_id, title in cur:
                yr = arxiv_year(arxiv_id)
                w.writerow(
                    [
                        arxiv_id,
                        _clean(title),
                        "" if yr is None else yr,
                        primary.get(arxiv_id, ""),
                    ]
                )
                n += 1
                if n % 500_000 == 0:
                    print(f"[nodes] {n:,}", flush=True)
        print(f"[nodes] wrote {n:,} -> {NODES_CSV}", flush=True)
        return n
    finally:
        conn.close()


def _load_id_map() -> dict[int, str]:
    """paper.id (int) -> arxiv_id, loaded once from Postgres."""
    print("[edges] loading paper id->arxiv_id map ...", flush=True)
    id_map: dict[int, str] = {}
    with psycopg.connect(PG_DSN) as conn, conn.cursor(name="paper_map") as cur:
        cur.itersize = 200_000
        cur.execute("SELECT id, arxiv_id FROM paper")
        for pid, axid in cur:
            id_map[pid] = axid
    print(f"[edges] id map: {len(id_map):,} papers", flush=True)
    return id_map


def export_edges() -> tuple[int, int]:
    id_map = _load_id_map()
    EDGES_HEADER.write_text(EDGE_HEADER + "\n")
    written = 0
    skipped = 0
    t0 = time.time()
    with (
        psycopg.connect(PG_DSN) as conn,
        conn.cursor(name="cit_stream") as cur,
        EDGES_CSV.open("w", newline="") as fh,
    ):
        w = csv.writer(fh)
        cur.itersize = 100_000
        cur.execute(
            "SELECT citing_id, cited_id, intent, polarity, intent_score, ordinal "
            "FROM citation WHERE cited_id IS NOT NULL"
        )
        for citing_id, cited_id, intent, polarity, intent_score, ordinal in cur:
            src = id_map.get(citing_id)
            dst = id_map.get(cited_id)
            if src is None or dst is None:
                skipped += 1
                continue
            w.writerow(
                [
                    src,
                    dst,
                    intent or "",
                    polarity or "",
                    "" if intent_score is None else intent_score,
                    ordinal,
                ]
            )
            written += 1
            if written % 5_000_000 == 0:
                rate = written / (time.time() - t0)
                print(f"[edges] {written:,} ({rate:,.0f}/s)", flush=True)
    print(f"[edges] wrote {written:,}, skipped {skipped:,} -> {EDGES_CSV}", flush=True)
    return written, skipped


def export_all() -> None:
    """Write nodes.csv + edges.csv for the neo4j-admin bulk import."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    n_nodes = export_nodes()
    n_edges, skipped = export_edges()
    print(
        f"\n[done] nodes={n_nodes:,} edges={n_edges:,} skipped_edges={skipped:,}",
        flush=True,
    )
