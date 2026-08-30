"""
Embed every stage 2 abstract, then reduce the whole corpus to the vectors clustering reads

UMAP is refit on every run and the whole corpus is reduced again, since a refit moves every vector
The document is `Title: ...\\nAbstract: ...` because the existing corpus vectors were built that way
"""

from __future__ import annotations

import argparse
import json
import math
import tomllib
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import psycopg
from numpy.typing import NDArray


def parse_vector(raw: str) -> list[float]:
    """
    Decode the `[a,b,c]` text form pgvector returns without its own adapter

    Args:
        raw: the column value as text.

    Returns:
        The vector as plain floats.
    """
    return [float(x) for x in raw.strip("[]").split(",")]


class Embedder:
    """
    The embedding endpoint, plus the two passes that fill the vector columns
    """

    def __init__(
        self, base_url: str, embedder_name: str, max_seq: int, prefix: str, parallel: int = 1
    ) -> None:
        """
        Args:
            base_url: the llama-server root serving the embedding model.
            embedder_name: model name the endpoint answers to.
            max_seq: token budget per document, including the two special tokens.
            prefix: the asymmetric document prompt.
            parallel: batches in flight against the endpoint at once.
        """
        self.base_url = base_url.rstrip("/")
        self.name = embedder_name
        self.max_seq = max_seq
        self.prefix = prefix
        self.parallel = parallel

    def _post(
        self, path: str, payload: dict[str, Any]
    ) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.load(r)  # pyright: ignore[reportAny]

    def truncate(self, text: str) -> str:
        """
        Cut a document to the model's window using the server's own tokenizer

        Args:
            text: the prefixed document.

        Returns:
            The text, shortened only when it does not fit.
        """
        toks: list[int] = self._post("/tokenize", {"content": text, "add_special": False})["tokens"]
        if len(toks) <= self.max_seq - 2:
            return text
        return self._post("/detokenize", {"tokens": toks[: self.max_seq - 2]})["content"]

    def embed(self, text: str) -> list[list[float]]:
        """
        Embed one document and return its L2-normalized vector in a single-item list

        Args:
            text: the composed document, without the prompt prefix.

        Returns:
            One vector.
        """
        return self.embed_many([text])

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a batch of documents through one endpoint call

        Args:
            texts: composed documents, without the prompt prefix.

        Returns:
            One L2-normalized vector per input, in input order.
        """
        inputs = [self.truncate(self.prefix + t) for t in texts]
        payload = self._post("/v1/embeddings", {"model": self.name, "input": inputs})
        ordered: list[dict[str, Any]] = sorted(  # pyright: ignore[reportExplicitAny]
            payload["data"], key=lambda d: int(d["index"])  # pyright: ignore[reportAny]
        )
        out: list[list[float]] = []
        for row in ordered:
            vec = [float(x) for x in row["embedding"]]  # pyright: ignore[reportAny]
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            out.append([x / norm for x in vec])
        return out

    def embed_to_db(self, pg_dest: str, batch: int) -> int:
        """
        Embed every stage 2 paper and advance it to stage 3

        Args:
            pg_dest: libpq connection string.
            batch: documents per endpoint call.

        Returns:
            How many papers were embedded.
        """
        with psycopg.connect(pg_dest) as conn:
            rows: list[tuple[str, str, str]] = conn.execute(
                "SELECT arxiv_id, title, abstract FROM papers WHERE stage = 2"
            ).fetchall()
        print(f"[stage3] {len(rows):,} papers to embed", flush=True)
        if not rows:
            return 0

        done = 0
        with psycopg.connect(pg_dest, autocommit=True) as conn:
            _ = conn.execute("CREATE TEMP TABLE t_emb (arxiv_id text PRIMARY KEY, v text)")
            chunks = [rows[i : i + batch] for i in range(0, len(rows), batch)]
            """
            Batches are independent, so `parallel` of them are in flight at once.
            The COPY stays on the single connection, so writes are serialized behind the fetches.
            """
            with ThreadPoolExecutor(max_workers=self.parallel) as pool:
                for group in range(0, len(chunks), self.parallel):
                    wave = chunks[group : group + self.parallel]
                    docs = [
                        [f"Title: {t or ''}\nAbstract: {a or ''}" for _, t, a in c] for c in wave
                    ]
                    for chunk, vecs in zip(wave, pool.map(self.embed_many, docs), strict=True):
                        with conn.cursor().copy("COPY t_emb (arxiv_id, v) FROM STDIN") as cp:
                            for (arxiv_id, _t, _a), v in zip(chunk, vecs, strict=True):
                                cp.write_row(
                                    (arxiv_id, "[" + ",".join(f"{x:.5g}" for x in v) + "]")
                                )
                        done += len(chunk)
                    """
                    Each wave lands before the next starts, so a kill costs one wave rather
                    than the whole pass.
                    """
                    _ = conn.execute(
                        "UPDATE papers p SET embed_full = t.v::halfvec, stage = 3"
                        " FROM t_emb t WHERE p.arxiv_id = t.arxiv_id"
                    )
                    _ = conn.execute("TRUNCATE t_emb")
                    print(f"[stage3]   {done:,}/{len(rows):,}", flush=True)
        return done

    def fit_umap(self, pg_dest: str, sample: int, path: str, dim: int, seed: int) -> None:
        """
        Fit the reducer on a sample of the full vectors, save it and drop every reduced vector

        Refuses to run while papers are still waiting to be embedded, since fitting on a partial
        corpus produces a valid-looking model whose neighborhoods are wrong.
        The refit moves every vector, so the old reductions are cleared and `umap_to_db` redoes
        the whole corpus rather than only the delta.

        Args:
            pg_dest: libpq connection string.
            sample: how many vectors to fit on.
            path: where the fitted model is saved.
            dim: output dimensionality.
            seed: fixes the projection trees and the layout sgd, at the cost of one core.

        Raises:
            SystemExit: if any paper is still at stage 2.
        """
        import umap  # noqa: PLC0415

        with psycopg.connect(pg_dest) as conn:
            row = conn.execute("SELECT count(*) FROM papers WHERE stage = 2").fetchone()
            waiting = int(row[0]) if row else 0
            if waiting:
                raise SystemExit(f"{waiting:,} papers still at stage 2, embed them before fitting")
            rows: list[tuple[str]] = conn.execute(
                "SELECT embed_full::text FROM papers WHERE embed_full IS NOT NULL"
                " ORDER BY random() LIMIT %s",
                (sample,),
            ).fetchall()

        train = np.asarray([parse_vector(r[0]) for r in rows], dtype=np.float32)
        print(f"[stage3] fitting umap on {train.shape[0]:,} vectors", flush=True)
        model = umap.UMAP(n_components=dim, metric="cosine", random_state=seed)
        _ = model.fit(train)
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = joblib.dump(model, target)
        print(f"[stage3] saved {target}", flush=True)

        """
        The model lands before the column is cleared, so a kill leaves a queue that matches it.
        """
        with psycopg.connect(pg_dest) as conn:
            cleared = conn.execute("UPDATE papers SET embed_umap = NULL").rowcount
            conn.commit()
        print(f"[stage3] cleared {cleared:,} reduced vectors", flush=True)

    def umap_to_db(self, pg_dest: str, batch: int, path: str) -> int:
        """
        Transform every full vector that has no reduced vector yet

        Args:
            pg_dest: libpq connection string.
            batch: rows per transform call.
            path: the fitted model.

        Returns:
            How many papers were reduced.
        """
        model: Any = joblib.load(path)  # pyright: ignore[reportExplicitAny, reportAny]
        done = 0
        while True:
            with psycopg.connect(pg_dest) as conn:
                rows: list[tuple[str, str]] = conn.execute(
                    "SELECT arxiv_id, embed_full::text FROM papers"
                    " WHERE embed_full IS NOT NULL AND embed_umap IS NULL LIMIT %s",
                    (batch,),
                ).fetchall()
                if not rows:
                    break
                block = np.asarray([parse_vector(r[1]) for r in rows], dtype=np.float32)
                reduced: NDArray[np.float32] = model.transform(block)  # pyright: ignore[reportAny]
                _ = conn.execute("CREATE TEMP TABLE u (arxiv_id text PRIMARY KEY, v text)")
                with conn.cursor().copy("COPY u (arxiv_id, v) FROM STDIN") as cp:
                    for (arxiv_id, _raw), v in zip(rows, reduced, strict=True):
                        cp.write_row((arxiv_id, "[" + ",".join(f"{x:.6g}" for x in v) + "]"))
                _ = conn.execute(
                    "UPDATE papers p SET embed_umap = u.v::vector"
                    " FROM u WHERE p.arxiv_id = u.arxiv_id"
                )
                conn.commit()
            done += len(rows)
            print(f"[stage3]   reduced {done:,}", flush=True)
        return done


def main() -> None:
    """
    Read the config, then embed, fit the reducer and reduce
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--config_path", default="config.toml")
    args = ap.parse_args()

    cfg = tomllib.loads(
        Path(str(args.config_path)).read_text(encoding="utf-8")
    )  # pyright: ignore[reportAny]
    ep, um = cfg["endpoints"], cfg["umap"]
    dsn = str(cfg["database"]["PG_DEST"])
    emb = Embedder(
        base_url=str(ep["EMBED_API"]),
        embedder_name=str(ep["EMBED_NAME"]),
        max_seq=int(ep["EMBED_MAX_SEQ"]),
        prefix=str(ep["EMBED_PREFIX"]),
        parallel=int(ep["EMBED_PARALLEL"]),
    )
    _ = emb.embed_to_db(dsn, batch=int(ep["EMBED_BATCH"]))
    emb.fit_umap(
        dsn,
        int(um["UMAP_SAMPLE"]),
        str(um["UMAP_MODEL_PATH"]),
        int(um["UMAP_DIM"]),
        int(um["UMAP_SEED"]),
    )
    _ = emb.umap_to_db(dsn, int(um["UMAP_BATCH"]), str(um["UMAP_MODEL_PATH"]))


if __name__ == "__main__":
    main()
