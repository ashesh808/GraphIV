"""
Drive the endpoint for one experiment condition and return its run record

It routes on max_rounds, so a condition picks the single pass or the deep loop by config
Output lands under the experiment's own results directory, never the live endpoint's
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from graphiv.generate import loop as deep_loop
from graphiv.generate import pipeline as pipeline


def _cache_key(question: str, cfg: dict[str, Any]) -> str:
    """
    Stable short hash of the full (question + config) so identical cells compute once
    """
    blob = json.dumps({"q": question, **cfg}, sort_keys=True)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def run_phase6(
    question: str,
    out_root: Path,
    *,
    effort: str = "standard",
    rank: str = "ppr",
    recency: float = 0.4,
    no_cluster: bool = False,
    no_graph: bool = False,
    no_frontier_pull: bool = False,
    max_rounds: int = 1,
    critique_k: int = 8,
    figures: bool = True,
    deep: bool = False,
    embed_mode: str = "asym",
    use_hyde: bool = False,
    no_grade: bool = False,
    fuse: bool = True,
    cache: bool = True,
) -> tuple[dict[str, Any], Path]:
    """
    Run one condition

    Returns (run.json meta, output dir).

        Uses the deep judge-loop when `max_rounds > 1` OR `deep=True` (the latter lets an experiment
        run the loop at max_rounds=1 to isolate it from gap expansion, keeping compose and critique
        Otherwise the single-pass path runs. On a cache hit, meaning the same question and config
        a valid dir) the LLM call is skipped and the prior `run.json` is loaded.
    """
    out_root.mkdir(parents=True, exist_ok=True)
    cfg: dict[str, Any] = {
        "effort": effort,
        "rank": rank,
        "recency": recency,
        "no_cluster": no_cluster,
        "no_graph": no_graph,
        "no_frontier_pull": no_frontier_pull,
        "max_rounds": max_rounds,
        "critique_k": critique_k,
        "figures": figures,
        "deep": deep,
        "embed_mode": embed_mode,
        "use_hyde": use_hyde,
        "no_grade": no_grade,
        "fuse": fuse,
    }
    manifest = out_root / "_cache.json"
    key = _cache_key(question, cfg)
    if cache and manifest.exists():
        m: dict[str, str] = json.loads(manifest.read_text())  # pyright: ignore[reportAny]
        hit = m.get(key)
        if hit:
            d = Path(hit)
            if (d / "run.json").exists() and (d / "report.md").exists():
                cached: dict[str, Any] = json.loads((d / "run.json").read_text())
                print(f"[runner] cache hit {key} -> {d}", flush=True)
                return cached, d

    if deep or max_rounds > 1:
        meta = deep_loop.run_deep(
            question,
            effort,
            rank,
            no_cluster,
            no_graph,
            recency,
            max_rounds,
            critique_k,
            figures,
            no_frontier_pull,
            out_root,
            embed_mode,
            use_hyde,
            no_grade=no_grade,
            fuse=fuse,
        )
    else:
        meta = pipeline.run(
            question,
            effort,
            rank,
            no_cluster,
            no_graph,
            recency,
            no_frontier_pull,
            embed_mode,
            use_hyde,
            no_grade=no_grade,
            fuse=fuse,
        )
    out_dir = _resolve_out_dir(meta, out_root)
    if cache:
        m2: dict[str, str] = json.loads(manifest.read_text()) if manifest.exists() else {}
        m2[key] = str(out_dir)
        _ = manifest.write_text(json.dumps(m2, indent=0), encoding="utf-8")
    return meta, out_dir


def _resolve_out_dir(meta: dict[str, Any], out_root: Path) -> Path:
    """
    The endpoint writes to <root>/<slug>/<cfg>; the deep path honors out_root, single-pass

        writes to the live OUT root. Relocate a single-pass result into out_root so every cell of an
        experiment lands in the same store (keeps the run dirs colocated + browsable).
    """
    import shutil

    slug = pipeline._slug(str(meta["question"]))  # pyright: ignore[reportPrivateUsage]
    cfg = str(meta["config"])
    cand = out_root / slug / cfg
    if cand.exists():
        return cand
    live = pipeline.OUT / slug / cfg  # single-pass path ignores out_root
    if live.exists() and out_root.resolve() != pipeline.OUT.resolve():
        cand.parent.mkdir(parents=True, exist_ok=True)
        _ = shutil.move(str(live), str(cand))
        return cand
    return live
