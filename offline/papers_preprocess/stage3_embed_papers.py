"""
Embed the title and abstract of every stage 2 paper into embed_full

The document is `Title: ...\\nAbstract: ...` because the existing corpus vectors were built that way
"""

from __future__ import annotations

import argparse
import json
import math
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import psycopg

from src.core.config import load_config
from src.core.paths import OFFLINE_CONFIG


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


def main() -> None:
    """
    Read the config, then embed every paper waiting at stage 2
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--config_path", default=str(OFFLINE_CONFIG))
    args = ap.parse_args()

    cfg = load_config(str(args.config_path))
    ep = cfg["endpoints"]
    dsn = str(cfg["database"]["PG_DEST"])
    emb = Embedder(
        base_url=str(ep["EMBED_API"]),
        embedder_name=str(ep["EMBED_NAME"]),
        max_seq=int(ep["EMBED_MAX_SEQ"]),
        prefix=str(ep["EMBED_PREFIX"]),
        parallel=int(ep["EMBED_PARALLEL"]),
    )
    _ = emb.embed_to_db(dsn, batch=int(ep["EMBED_BATCH"]))


if __name__ == "__main__":
    main()
