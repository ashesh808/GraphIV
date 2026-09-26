"""
Build and cache the pool, edges and reader grades for every survey in the 60-survey battery

Selection arms are swept later over these frozen pools, so this runs the LLM exactly once
"""

from __future__ import annotations

import json
import pickle
import time
import traceback
from typing import Any

from .._boot import REPO
from .survey_bench import build_pool

CACHE = REPO / "experiments" / "_harness" / "pools"
BATTERY = REPO / "experiments" / "02-retrieval" / "02-01-benchmarks" / "cache" / "battery60.json"


def main() -> None:
    """
    Retrieve and grade each survey, pickling the frozen pool for the arm sweep
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    battery: list[dict[str, Any]] = json.loads(
        (BATTERY).read_text()
    )  # pyright: ignore[reportExplicitAny]
    for i, s in enumerate(battery, 1):
        aid = str(s["arxiv_id"])
        dst = CACHE / f"{aid}.pkl"
        if dst.exists():
            print(f"[{i}/{len(battery)}] {aid} cached", flush=True)
            continue
        t0 = time.time()
        try:
            pool, edges, grades, fr, q, m = build_pool(s, "standard")
        except Exception:  # noqa: BLE001
            print(f"[{i}/{len(battery)}] {aid} FAILED\n{traceback.format_exc()}", flush=True)
            continue
        with dst.open("wb") as fh:
            pickle.dump(
                {
                    "pool": pool,
                    "edges": edges,
                    "grades": grades,
                    "fr": fr,
                    "qrels": q.mentions,
                    "qrels_raw": q.n_raw,
                    "m": m,
                    "meta": s,
                },
                fh,
            )
        print(
            f"[{i}/{len(battery)}] {aid} {time.time() - t0:6.1f}s "
            f"pool={len(pool)} edges={len(edges)} gold={len(q.mentions)}",
            flush=True,
        )


if __name__ == "__main__":
    main()
