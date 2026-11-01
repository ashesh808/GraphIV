"""
Run the trained student over every citation that resolved to a paper

Only rows with a target are labeled, since an unresolved reference has no cited work to reason about
The stage column is the queue, so --relabel just resets it and the same loop drains it again
"""

from __future__ import annotations

import argparse
import queue
import threading
import time
from pathlib import Path
from typing import Any

import psycopg
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from src.core.config import load_config
from src.core.paths import OFFLINE_CONFIG

INTENTS = ("uses", "extends", "compares", "motivates", "background", "critiques")
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

"""
Rows come back in citation_id order from a watermark, so the fetcher can run a chunk ahead of
the model without handing out the rows still in flight.
"""
QUEUE = """
SELECT citation_id, COALESCE(section, ''), sentence
FROM citations
WHERE stage = 0 AND target_id IS NOT NULL AND sentence IS NOT NULL AND citation_id > %s
ORDER BY citation_id
LIMIT %s
"""


def attention_kind() -> str:
    """
    The fastest attention backend that actually imports on this machine

    Returns:
        Either `flash_attention_2` or `sdpa`.
    """
    try:
        import flash_attn  # noqa: F401, PLC0415

        return "flash_attention_2"
    except ImportError:
        return "sdpa"


class CitationLabeler:
    """
    The trained student and the queue it drains
    """

    def __init__(self, labeler_path: str, model_name: str, max_seq: int) -> None:
        """
        Args:
            labeler_path: the citation_labeler data directory holding best.pt and tokenizer/.
            model_name: the backbone the checkpoint was trained on.
            max_seq: token budget per citation.
        """
        root = Path(labeler_path)
        self.max_seq = max_seq
        self.tok: Any = AutoTokenizer.from_pretrained(
            root / "tokenizer"
        )  # pyright: ignore[reportExplicitAny]
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name, num_labels=len(INTENTS), attn_implementation=attention_kind()
        )
        _ = model.load_state_dict(torch.load(root / "best.pt", weights_only=True))
        self.model = model.to(DEVICE).eval()

    def label_one(self, section: str, sentence: str) -> tuple[str, float]:
        """
        Label a single citation

        Args:
            section: the section heading the citation sits under.
            sentence: the sentence carrying the citation.

        Returns:
            The intent and its softmax score.
        """
        got = self.label_batch([(section, sentence)])
        return got[0]

    def label_batch(self, items: list[tuple[str, str]]) -> list[tuple[str, float]]:
        """
        Label a batch as (section, sentence) pairs

        Args:
            items: the citations to label.

        Returns:
            One (intent, score) per input, in input order.
        """
        enc = self.tok(
            [s or "(unknown)" for s, _ in items],
            [t for _, t in items],
            max_length=self.max_seq,
            padding=True,
            truncation=True,
            return_tensors="pt",
        ).to(DEVICE)
        with torch.no_grad():
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=DEVICE.type == "cuda"):
                logits = self.model(**enc).logits
        probs = torch.softmax(logits.float(), dim=-1)
        score, idx = probs.max(dim=-1)
        return [(INTENTS[i], float(s)) for i, s in zip(idx.tolist(), score.tolist(), strict=True)]

    def _fetch(
        self, pg_dest: str, chunk: int, sink: queue.Queue[list[tuple[int, str, str]]]
    ) -> None:
        """
        Read chunks ahead of the model and hand them over, ending with an empty one

        Args:
            pg_dest: libpq connection string.
            chunk: rows per fetch.
            sink: the handover, one chunk deep so the reader stays a chunk ahead and no further.
        """
        mark = 0
        with psycopg.connect(pg_dest) as conn:
            while True:
                rows: list[tuple[int, str, str]] = conn.execute(QUEUE, (mark, chunk)).fetchall()
                sink.put(rows)
                if not rows:
                    return
                mark = rows[-1][0]

    def label(self, pg_dest: str, batch: int, relabel: bool = False, chunk: int = 16384) -> int:
        """
        Drain the queue, sorting each chunk by length before it reaches the model

        Sorting matters more than batch size here: a random batch pads every row up to its
        longest, which is 3.9x the tokens the rows actually carry, and sorting cuts that to 1.3x.

        Args:
            pg_dest: libpq connection string.
            batch: citations per forward pass.
            relabel: reset every resolved row to stage 0 first.
            chunk: rows fetched and sorted at once.

        Returns:
            How many citations were labeled.
        """
        with psycopg.connect(pg_dest, autocommit=True) as conn:
            if relabel:
                n = conn.execute(
                    "UPDATE citations SET stage = 0 WHERE target_id IS NOT NULL AND stage <> 0"
                ).rowcount
                print(f"[label] reset {n:,} rows to stage 0", flush=True)

            row = conn.execute(
                "SELECT count(*) FROM citations WHERE stage = 0 AND target_id IS NOT NULL"
            ).fetchone()
            todo = int(row[0]) if row else 0
            print(f"[label] {todo:,} citations to label on {DEVICE}", flush=True)

            _ = conn.execute(
                "CREATE TEMP TABLE stg (citation_id bigint PRIMARY KEY, intent text, score real)"
            )

            sink: queue.Queue[list[tuple[int, str, str]]] = queue.Queue(maxsize=1)
            reader = threading.Thread(target=self._fetch, args=(pg_dest, chunk, sink), daemon=True)
            reader.start()

            done, rounds, t0 = 0, 0, time.time()
            while True:
                rows = sink.get()
                if not rows:
                    break

                """
                Character length stands in for token length, which saves tokenizing twice and
                orders the chunk just as well.
                """
                rows.sort(key=lambda r: len(r[1]) + len(r[2]))
                got: list[tuple[str, float]] = []
                for i in range(0, len(rows), batch):
                    got.extend(self.label_batch([(r[1], r[2]) for r in rows[i : i + batch]]))

                _ = conn.execute("TRUNCATE stg")
                with conn.cursor().copy("COPY stg (citation_id, intent, score) FROM STDIN") as cp:
                    for (cid, _s, _t), (intent, score) in zip(rows, got, strict=True):
                        cp.write_row((cid, intent, score))
                _ = conn.execute(
                    "UPDATE citations c SET intent = s.intent, intent_score = s.score, stage = 1"
                    " FROM stg s WHERE c.citation_id = s.citation_id"
                )
                done += len(rows)
                rounds += 1
                # a 73M row update bloats the heap, so reclaim into free space as we go
                if rounds % 8 == 0:
                    _ = conn.execute("VACUUM citations")
                rate = done / max(1e-6, time.time() - t0)
                left = (todo - done) / max(1.0, rate) / 3600
                print(
                    f"[label] {done:,}/{todo:,}  ({rate:,.0f}/s, {left:.1f} h left)",
                    flush=True,
                )
        return done


def main() -> None:
    """
    Read the config, then label every resolved citation
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--config_path", default=str(OFFLINE_CONFIG))
    _ = ap.add_argument("--relabel", action="store_true", help="redo the whole table")
    args = ap.parse_args()

    cfg = load_config(str(args.config_path))
    cl = cfg["citation_labeler"]
    labeler = CitationLabeler(
        labeler_path=str(cl["LABELER_PATH"]),
        model_name=str(cl["LABELER_MODEL"]),
        max_seq=int(cl["LABELER_MAX_SEQ"]),
    )
    _ = labeler.label(
        str(cfg["database"]["PG_DEST"]),
        batch=int(cl["LABELER_BATCH"]),
        relabel=bool(args.relabel),  # pyright: ignore[reportAny]
    )


if __name__ == "__main__":
    main()
