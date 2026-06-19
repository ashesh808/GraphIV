"""Step 5 — build the native Neo4j vector index over Paper.embedding.

Creates an HNSW cosine index (768D) and polls until it reports ONLINE. The
population pass over ~2.83M vectors is the long part of the pipeline; progress
is logged so a monitor can watch it.
"""

from __future__ import annotations

import time
from typing import LiteralString, cast

from _common import NEO4J_DB, VECTOR_INDEX, neo4j_driver

CREATE = f"""
CREATE VECTOR INDEX {VECTOR_INDEX} IF NOT EXISTS
FOR (p:Paper) ON (p.embedding)
OPTIONS {{ indexConfig: {{
  `vector.dimensions`: 768,
  `vector.similarity_function`: 'cosine'
}} }}
"""

STATUS = (
    "SHOW INDEXES YIELD name, type, state, populationPercent "
    f"WHERE name = '{VECTOR_INDEX}' "
    "RETURN state, populationPercent"
)


def main() -> None:
    with neo4j_driver() as drv, drv.session(database=NEO4J_DB) as session:
        rec = session.run(
            "MATCH (p:Paper) WHERE p.embedding IS NOT NULL RETURN count(p) AS n"
        ).single()
        n_emb = int(rec["n"]) if rec else 0
        print(f"[index] {n_emb:,} nodes have an embedding", flush=True)

        # Drop any prior (possibly stalled) index so we always build fresh.
        # cast: queries interpolate the internal index name, not user input.
        print(f"[index] dropping any existing '{VECTOR_INDEX}' ...", flush=True)
        drop = cast(LiteralString, f"DROP INDEX {VECTOR_INDEX} IF EXISTS")
        session.run(drop).consume()
        print(f"[index] creating vector index '{VECTOR_INDEX}' ...", flush=True)
        session.run(cast(LiteralString, CREATE)).consume()

        t0 = time.time()
        while True:
            rec = session.run(cast(LiteralString, STATUS)).single()
            if rec is None:
                print("[index] index not found yet ...", flush=True)
            else:
                state = rec["state"]
                pct = rec["populationPercent"]
                elapsed = time.time() - t0
                print(
                    f"[index] state={state} populated={pct:.1f}% ({elapsed:,.0f}s)",
                    flush=True,
                )
                if state == "ONLINE":
                    print("[index] ONLINE", flush=True)
                    break
                if state == "FAILED":
                    raise SystemExit("[index] index FAILED — check neo4j logs")
            time.sleep(30)
