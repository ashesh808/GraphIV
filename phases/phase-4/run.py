"""Phase-4 entry point — build the Neo4j graph store + vector index (preprocessing).

Sequence: export CSVs -> [sudo offline neo4j-admin bulk import] -> attach embeddings -> vector
index. Idempotent: each step probes its artifact and skips if already built (use --include-force
to rebuild). The bulk-import step needs sudo + a stopped DB, so it is printed as a manual step.
    uv run python phases/phase-4/run.py [--set-only {export,emb_map,attach,index}]
                                        [--include-force] [--dry-run]
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "components"))
sys.path.insert(0, str(_HERE.parent))

from _framework import print_config, resolve  # noqa: E402

from _common import (  # noqa: E402
    EDGES_CSV,
    EMB_IDS_NPY,
    EMB_ROWS,
    NEO4J_DB,
    NODES_CSV,
    VECTOR_INDEX,
    neo4j_driver,
)

STEPS = ("export", "emb_map", "attach", "index")


def _emb_count() -> int:
    """Count Paper nodes that already carry an embedding (attach idempotency probe)."""
    with neo4j_driver() as drv, drv.session(database=NEO4J_DB) as s:
        rec = s.run(
            "MATCH (p:Paper) WHERE p.embedding IS NOT NULL RETURN count(p) AS n"
        ).single()
    return int(rec["n"]) if rec else 0


def _index_online() -> bool:
    """True if the vector index exists and is ONLINE (index idempotency probe)."""
    with neo4j_driver() as drv, drv.session(database=NEO4J_DB) as s:
        rec = s.run(
            "SHOW INDEXES YIELD name, state WHERE name = $n RETURN state",
            n=VECTOR_INDEX,
        ).single()
    return rec is not None and rec["state"] == "ONLINE"


def _state() -> dict[str, bool]:
    """Per-step done/not-done, probing files (export/emb_map) and Neo4j (attach/index)."""
    csvs_done = (
        NODES_CSV.exists()
        and EDGES_CSV.exists()
        and NODES_CSV.stat().st_size > 0
        and EDGES_CSV.stat().st_size > 0
    )
    try:
        attached = _emb_count() >= int(EMB_ROWS * 0.9)
        indexed = _index_online()
    except Exception as e:  # noqa: BLE001 — Neo4j down -> report as not-done
        print(f"[phase-4] (neo4j unreachable: {e})")
        attached = indexed = False
    return {
        "export": csvs_done,
        "emb_map": EMB_IDS_NPY.exists(),
        "attach": attached,
        "index": indexed,
    }


def main() -> None:
    r = resolve(_HERE, sys.argv[1:], required=("only", "force", "emb_model"))
    print_config("phase-4", r)
    force = bool(r.config["force"])
    only: str = r.config["only"]
    todo = STEPS if only == "all" else (only,)
    if only != "all" and only not in STEPS:
        raise SystemExit(f"--set-only must be one of {('all', *STEPS)}")

    state = _state()
    print(
        "[phase-4] artifact state:",
        {s: ("built" if state[s] else "missing") for s in STEPS},
    )

    plan = [s for s in todo if force or not state[s]]
    skip = [s for s in todo if s not in plan]
    if skip:
        print(f"[phase-4] skip (already built): {skip}")
    print(f"[phase-4] would run: {plan or '(nothing — all built)'}")

    if r.dry_run or not plan:
        return

    # Imports deferred so --dry-run never touches Postgres / GPU / Neo4j drivers.
    for step in plan:
        if step == "export":
            from export_csv import export_all

            export_all()
        elif step == "emb_map":
            from build_emb_map import main as freeze_emb_ids

            freeze_emb_ids()
            print(
                "[phase-4] NEXT (manual, sudo): stop neo4j, run the offline bulk import"
            )
            print(
                "[phase-4]   (neo4j-admin database import; see kg_rag/import_neo4j.sh)"
            )
        elif step == "attach":
            from attach_embeddings import main as attach

            attach()
        elif step == "index":
            from create_index import main as create_vector_index

            create_vector_index()


if __name__ == "__main__":
    main()
