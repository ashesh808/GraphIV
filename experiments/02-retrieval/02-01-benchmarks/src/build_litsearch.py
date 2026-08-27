"""
Flatten LitSearch's S2ORC corpus into one table of id, arxiv id, title, abstract and edges

The shards carry externalids.arxiv for the whole corpus, not only the 574 gold papers
Abstract spans sit inside the full text, so every document embeds the way ours do
"""

from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any, cast

import pandas as pd  # pyright: ignore[reportMissingTypeStubs]

BASE = Path("/mnt/Vault-Storage/research/arxiv/benchmarks/litsearch")


def span(content: dict[str, Any], key: str) -> str:  # pyright: ignore[reportExplicitAny]
    """
    The text under the first annotation span of `key`, empty when absent
    """
    raw = cast(dict[str, Any], content.get("annotations", {})).get(
        key
    )  # pyright: ignore[reportExplicitAny]
    if not raw:
        return ""
    try:
        sp: list[dict[str, Any]] = json.loads(str(raw))  # pyright: ignore[reportExplicitAny]
    except ValueError:
        return ""
    if not sp:
        return ""
    txt = str(content.get("text", ""))
    return " ".join(txt[int(sp[0]["start"]) : int(sp[0]["end"])].split())


def main() -> None:
    """
    Write corpus.parquet and edges.parquet next to the raw shards
    """
    rows: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    for f in sorted(glob.glob(str(BASE / "corpus_s2orc" / "*.parquet"))):
        df = cast(Any, pd).read_parquet(f)  # pyright: ignore[reportExplicitAny]
        for r in df.itertuples(index=False):  # pyright: ignore[reportAny]
            ext = (
                cast(dict[str, Any], r.externalids) or {}
            )  # pyright: ignore[reportExplicitAny, reportAny]
            c = (
                cast(dict[str, Any], r.content) or {}
            )  # pyright: ignore[reportExplicitAny, reportAny]
            rows.append(
                {
                    "corpusid": int(r.corpusid),  # pyright: ignore[reportAny]
                    "arxiv_id": str(ext.get("arxiv") or ""),
                    "year": int(r.year) if r.year == r.year else 0,  # pyright: ignore[reportAny]
                    "title": span(c, "title"),
                    "abstract": span(c, "abstract"),
                }
            )
        print(f"  {Path(f).name}: {len(rows)} cumulative", flush=True)
    corpus = (
        cast(Any, pd).DataFrame(rows).drop_duplicates("corpusid")
    )  # pyright: ignore[reportExplicitAny]

    clean = cast(Any, pd).read_parquet(BASE / "corpus_clean")  # pyright: ignore[reportExplicitAny]
    have = set(corpus["corpusid"].tolist())  # pyright: ignore[reportAny]
    edges: list[dict[str, int]] = []
    for r in clean.itertuples(index=False):  # pyright: ignore[reportAny]
        src = int(r.corpusid)  # pyright: ignore[reportAny]
        cits = r.citations if r.citations is not None else []  # pyright: ignore[reportAny]
        for d in list(cits):
            if int(d) in have:
                edges.append({"src": src, "dst": int(d)})
    edf = cast(Any, pd).DataFrame(edges)  # pyright: ignore[reportExplicitAny]

    corpus.to_parquet(BASE / "corpus.parquet")
    edf.to_parquet(BASE / "edges.parquet")
    n_ax = int((corpus["arxiv_id"] != "").sum())  # pyright: ignore[reportAny]
    n_ab = int((corpus["abstract"] != "").sum())  # pyright: ignore[reportAny]
    print(f"\ncorpus {len(corpus)} docs")
    print(f"  with an arXiv id : {n_ax} ({n_ax / len(corpus):.1%})")
    print(f"  with an abstract : {n_ab} ({n_ab / len(corpus):.1%})")
    print(f"edges {len(edf)} (both ends in corpus)")


if __name__ == "__main__":
    main()
