"""
Reproduce LitSearch's published BM25 numbers before any of ours are allowed to count

Their index is a dict keyed by document text, so duplicate texts collapse
The retrievable universe is therefore smaller than the corpus, which this replicates
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any, cast

import nltk
import numpy as np
import pandas as pd  # pyright: ignore[reportMissingTypeStubs]
from rank_bm25 import BM25Okapi  # pyright: ignore[reportMissingTypeStubs]

B = Path("/mnt/Vault-Storage/research/arxiv/benchmarks/litsearch")
CACHE = B / "bm25_index.pkl"


def kv_pairs() -> tuple[list[str], list[int]]:
    """
    Their `create_kv_pairs`: a dict from title+abstract text to corpusid, so last wins
    """
    c = cast(Any, pd).read_parquet(
        B / "corpus_clean", columns=["corpusid", "title", "abstract"]
    )  # pyright: ignore[reportExplicitAny]
    kv: dict[str, int] = {}
    for cid, t, a in zip(
        c["corpusid"], c["title"], c["abstract"], strict=True
    ):  # pyright: ignore[reportAny]
        kv[f"Title: {t}\nAbstract: {a}"] = int(cid)  # pyright: ignore[reportAny]
    return list(kv), list(kv.values())


def encode(texts: list[str]) -> list[list[str]]:
    """
    Their `_encode_batch`: lowercase, word_tokenize, drop stopwords, Porter stem
    """
    stop = set(nltk.corpus.stopwords.words("english"))
    stem = nltk.stem.PorterStemmer().stem
    out: list[list[str]] = []
    for i, t in enumerate(texts):
        toks = nltk.word_tokenize(t.lower())
        out.append([stem(x) for x in toks if x not in stop])
        if i % 5000 == 0:
            print(f"  encoded {i}/{len(texts)}", flush=True)
    return out


def main() -> None:
    """
    Build the index, run the 597 queries and print recall against the published table
    """
    if CACHE.exists():
        with CACHE.open("rb") as fh:
            enc, ids = cast(
                tuple[list[list[str]], list[int]], pickle.load(fh)
            )  # pyright: ignore[reportAny]
    else:
        texts, ids = kv_pairs()
        print(f"index keys: {len(texts)} distinct texts", flush=True)
        enc = encode(texts)
        with CACHE.open("wb") as fh:
            pickle.dump((enc, ids), fh)
    idx = BM25Okapi(enc)
    arr = np.array(ids)

    q = cast(Any, pd).read_parquet(B / "query")  # pyright: ignore[reportExplicitAny]
    print(
        f"queries {len(q)}; broad {(q['specificity'] == 0).sum()}, "
        f"specific {(q['specificity'] == 1).sum()}"
    )
    stop = set(nltk.corpus.stopwords.words("english"))
    stem = nltk.stem.PorterStemmer().stem
    rec: dict[tuple[int, int], list[float]] = {}
    for n, (query, spec, gold) in enumerate(
        zip(q["query"], q["specificity"], q["corpusids"], strict=True)  # pyright: ignore[reportAny]
    ):
        toks = [stem(x) for x in nltk.word_tokenize(str(query).lower()) if x not in stop]
        order = np.argsort(idx.get_scores(toks))[::-1]
        g = {int(x) for x in gold}  # pyright: ignore[reportAny]
        for k in (5, 20):
            got = {int(x) for x in arr[order[:k]]}
            rec.setdefault((int(spec), k), []).append(
                len(got & g) / len(g)
            )  # pyright: ignore[reportAny]
        if n % 50 == 0:
            print(f"  query {n}/{len(q)}", flush=True)

    print("\nOUR REPRODUCTION vs PUBLISHED (LitSearch table 3, BM25, title+abstract)\n")
    print(f"{'cell':<26} {'ours':>7} {'published':>10}")
    pub = {(1, 5): 50.0, (0, 20): 39.9}
    for (spec, k), v in sorted(rec.items()):
        name = f"{'specific' if spec else 'broad'} R@{k}"
        p = pub.get((spec, k))
        print(f"{name:<26} {100 * float(np.mean(v)):>7.1f} " f"{p if p is not None else '-':>10}")
    _ = (B / "bm25_recall.json").write_text(
        json.dumps({f"{s}_{k}": float(np.mean(v)) for (s, k), v in rec.items()})
    )


if __name__ == "__main__":
    main()
