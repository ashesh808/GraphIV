"""
Export every paper with its pdf, html and embedding as Parquet, with the two classifiers beside it

Citation sentences stay out, since they are the papers' own text and most licenses withhold it
A citation is kept only when both its ends are exported, so every id it names has a row in papers
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
import tomllib
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any, LiteralString

import numpy as np
import psycopg
import pyarrow as pa
import pyarrow.parquet as pq
import torch
from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer

# the order stage1_label_citation.py trained with, since a checkpoint stores indices and not names
INTENTS = ("uses", "extends", "compares", "motivates", "background", "critiques")
SURVEY = ("other", "survey")
BATCH = 50_000
# rows a file, chosen so each lands at a few hundred MB
PER_FILE = {"papers": 500_000, "topics": 5_000_000, "citations": 20_000_000}

# a paper reaches stage 3 only through a pdf, an html and an embedding
PAPERS: LiteralString = """
SELECT arxiv_id, title, abstract, date, primary_category, authors, surnames, latest_version,
       doi, journal_ref, survey_probability, embed_full::text
FROM papers WHERE stage >= 3 ORDER BY arxiv_id
"""
TOPICS: LiteralString = """
SELECT t.arxiv_id, t.level_0, t.level_1, t.level_2, n0.name, n1.name, n2.name
FROM topic_tree t
JOIN papers p ON p.arxiv_id = t.arxiv_id AND p.stage >= 3
LEFT JOIN topic_names n0
  ON n0.level_0 = t.level_0 AND n0.level_1 IS NULL AND n0.level_2 IS NULL
LEFT JOIN topic_names n1
  ON n1.level_0 = t.level_0 AND n1.level_1 = t.level_1 AND n1.level_2 IS NULL
LEFT JOIN topic_names n2
  ON n2.level_0 = t.level_0 AND n2.level_1 = t.level_1 AND n2.level_2 = t.level_2
ORDER BY t.arxiv_id
"""
CITATIONS: LiteralString = """
SELECT c.source_id, c.target_id, c.section, c.resolved_by, c.intent, c.intent_score
FROM citations c
JOIN papers s ON s.arxiv_id = c.source_id AND s.stage >= 3
JOIN papers t ON t.arxiv_id = c.target_id AND t.stage >= 3
WHERE c.target_id IS NOT NULL
ORDER BY c.source_id, c.citation_id
"""
QUERIES: dict[str, LiteralString] = {
    "papers": PAPERS,
    "topics": TOPICS,
    "citations": CITATIONS,
}
SCHEMAS = {
    "papers": pa.schema(
        [
            ("arxiv_id", pa.string()),
            ("title", pa.string()),
            ("abstract", pa.string()),
            ("date", pa.date32()),
            ("primary_category", pa.string()),
            ("authors", pa.string()),
            ("surnames", pa.list_(pa.string())),
            ("latest_version", pa.string()),
            ("doi", pa.string()),
            ("journal_ref", pa.string()),
            ("survey_probability", pa.float32()),
        ]
    ),
    "topics": pa.schema(
        [
            ("arxiv_id", pa.string()),
            ("level_0", pa.int16()),
            ("level_1", pa.int16()),
            ("level_2", pa.int16()),
            ("name_0", pa.string()),
            ("name_1", pa.string()),
            ("name_2", pa.string()),
        ]
    ),
    "citations": pa.schema(
        [
            ("source_id", pa.string()),
            ("target_id", pa.string()),
            ("section", pa.string()),
            ("resolved_by", pa.string()),
            ("intent", pa.string()),
            ("intent_score", pa.float32()),
        ]
    ),
}


class Shards:
    """
    One table as numbered Parquet files of at most a fixed row count, one row group per batch
    """

    def __init__(self, root: Path, name: str) -> None:
        """
        Args:
            root: The export directory.
            name: The table, which names both its directory and its files.
        """
        self.root = root / name
        self.root.mkdir(parents=True, exist_ok=True)
        self.name = name
        self.writer: pq.ParquetWriter | None = None
        self.files = 0
        self.held = 0
        self.rows = 0

    def write(self, table: pa.Table) -> None:
        """
        Appends a batch, opening the next file once the current one is full

        Content defined chunking keeps unchanged rows byte identical between two exports

        Args:
            table: The batch.
        """
        if self.writer is None or self.held >= PER_FILE[self.name]:
            self.close()
            path = self.root / f"{self.name}-{self.files:05d}.parquet"
            self.writer = pq.ParquetWriter(
                path,
                table.schema,
                compression="zstd",
                compression_level=6,
                use_content_defined_chunking=True,
            )
            self.files += 1
            self.held = 0
        self.writer.write_table(table)
        self.held += table.num_rows
        self.rows += table.num_rows

    def close(self) -> None:
        """
        Finishes the open file, if any
        """
        if self.writer is not None:
            self.writer.close()
            self.writer = None


def batches(
    conn: psycopg.Connection, name: str, sql: LiteralString
) -> Iterator[list[tuple[Any, ...]]]:
    """
    A query's rows in batches from a server side cursor, so no table is held whole

    Args:
        conn: A connection inside the export's one transaction.
        name: The table, which names the cursor.
        sql: The query.

    Returns:
        The batches, in the query's order.
    """
    with conn.cursor(name=f"export_{name}") as cur:
        cur.itersize = BATCH
        _ = cur.execute(sql)
        while rows := cur.fetchmany(BATCH):
            yield rows


def papers_table(rows: list[tuple[Any, ...]]) -> pa.Table:
    """
    One batch of papers, the embedding parsed out of its text form into float16

    Args:
        rows: Rows in the order PAPERS selects them.

    Returns:
        The batch.
    """
    cols = list(zip(*rows, strict=True))
    schema = SCHEMAS["papers"]
    out = {f.name: pa.array(cols[i], type=f.type) for i, f in enumerate(schema)}
    vectors = np.stack([np.fromstring(v[1:-1], dtype=np.float32, sep=",") for v in cols[-1]])
    flat = pa.array(vectors.astype(np.float16).ravel())
    out["embedding"] = pa.FixedSizeListArray.from_arrays(flat, vectors.shape[1])
    return pa.table(out)


def plain_table(name: str, rows: list[tuple[Any, ...]]) -> pa.Table:
    """
    One batch of a table whose columns map straight onto its schema

    Args:
        name: topics or citations.
        rows: Rows in the order its query selects them.

    Returns:
        The batch.
    """
    cols = list(zip(*rows, strict=True))
    schema = SCHEMAS[name]
    return pa.table({f.name: pa.array(cols[i], type=f.type) for i, f in enumerate(schema)})


def classifier(
    base: str, checkpoint: Path, labels: tuple[str, ...], tokenizer: str, max_len: int, out: Path
) -> str:
    """
    Writes one trained checkpoint as a model that from_pretrained loads with no other file

    Only the base's config is read, since the checkpoint replaces every weight it would bring

    Args:
        base: The hub model the checkpoint was trained from.
        checkpoint: The state dict the stage loads.
        labels: The class names, in index order.
        tokenizer: Where the tokenizer the stage uses lives, a hub id or a directory.
        max_len: The token budget the stage truncates to.
        out: The directory to write.

    Returns:
        The sha256 of the weights written.
    """
    config = AutoConfig.from_pretrained(
        base,
        num_labels=len(labels),
        id2label=dict(enumerate(labels)),
        label2id={name: i for i, name in enumerate(labels)},
    )
    model = AutoModelForSequenceClassification.from_config(config)
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    _ = model.load_state_dict(state)
    model.save_pretrained(out)
    AutoTokenizer.from_pretrained(tokenizer, model_max_length=max_len).save_pretrained(out)
    return hashlib.sha256((out / "model.safetensors").read_bytes()).hexdigest()


def export(cfg: dict[str, Any], target: Path) -> None:
    """
    Writes the three tables and both classifiers under target, replacing it only once all landed

    Args:
        cfg: The parsed config.
        target: The export directory, graphiv-<date>.
    """
    part = target.with_name(f"{target.name}.part")
    shutil.rmtree(part, ignore_errors=True)
    part.mkdir(parents=True)
    clock = time.time()
    done, landed = 0, False
    try:
        with psycopg.connect(str(cfg["database"]["PG_DEST"])) as conn:
            # one snapshot for all three, so a stage writing meanwhile cannot split them
            conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
            conn.read_only = True
            row = conn.execute("SELECT count(*) FROM papers WHERE stage >= 3").fetchone()
            papers = int(row[0]) if row else 0
            row = conn.execute(
                "SELECT c.reltuples * (1 - s.null_frac) FROM pg_class c JOIN pg_stats s"
                " ON s.tablename = c.relname AND s.attname = 'target_id'"
                " WHERE c.relname = 'citations'"
            ).fetchone()
            total = 2 * papers + int(row[0] if row else 0)
            print(f"[export] {papers:,} papers into {target}", flush=True)
            counts: dict[str, int] = {}
            for name, sql in QUERIES.items():
                if name == "citations":
                    # a cursor plans for its first rows, which walks the source index across 55 GB
                    _ = conn.execute("SET LOCAL cursor_tuple_fraction = 1.0")
                    print("[citations] sorting the resolved citations", flush=True)
                shards = Shards(part, name)
                for rows in batches(conn, name, sql):
                    table = papers_table(rows) if name == "papers" else plain_table(name, rows)
                    shards.write(table)
                    done += len(rows)
                    print(f"[{name}] {done:,}/{max(total, done):,} rows", flush=True)
                shards.close()
                counts[name] = shards.rows
        print("[classifiers] citation intent and survey", flush=True)
        cl = cfg["citation_labeler"]
        survey = Path(str(cfg["survey"]["MODEL_PATH"]))
        recipe = tomllib.loads((survey / "hyperparam.toml").read_text(encoding="utf-8"))
        weights = {
            "citation_intent": classifier(
                str(cl["LABELER_MODEL"]),
                Path(str(cl["LABELER_PATH"])) / "best.pt",
                INTENTS,
                str(Path(str(cl["LABELER_PATH"])) / "tokenizer"),
                int(cl["LABELER_MAX_SEQ"]),
                part / "classifiers" / "citation_intent",
            ),
            "survey": classifier(
                str(recipe["model"]["NAME"]),
                survey / "model.pt",
                SURVEY,
                str(recipe["model"]["NAME"]),
                int(recipe["model"]["MAX_LEN"]),
                part / "classifiers" / "survey",
            ),
        }
        manifest = {
            "written": date.today().isoformat(),
            "rows": counts,
            "classifiers": weights,
        }
        _ = (part / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        landed = True
    finally:
        if not landed:
            shutil.rmtree(part, ignore_errors=True)
    shutil.rmtree(target, ignore_errors=True)
    _ = part.replace(target)
    print(f"[export] {done:,}/{done:,} rows", flush=True)
    print(
        f"[export] wrote {target}: {counts['papers']:,} papers, {counts['topics']:,} topics,"
        f" {counts['citations']:,} citations, in {time.time() - clock:.0f} s",
        flush=True,
    )


def main() -> None:
    """
    Read the config, then export to graphiv-<date>/ under EXPORT_PATH
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--config_path", default="config.toml")
    args = ap.parse_args()

    cfg = tomllib.loads(
        Path(str(args.config_path)).read_text(encoding="utf-8")
    )  # pyright: ignore[reportAny]
    root = Path(str(cfg["export"]["EXPORT_PATH"]))
    export(cfg, root / f"graphiv-{date.today().isoformat()}")


if __name__ == "__main__":
    main()
