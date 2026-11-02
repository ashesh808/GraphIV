"""Bounded Arrow-batch reads of the published GraphIV Parquet release."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from src.storage.blobs import file_sha256, validate_blob_name

TABLES = ("papers", "citations", "topics")
INTENTS = frozenset({"uses", "extends", "compares", "motivates", "background", "critiques"})


class ParquetSource:
    """Validate a local HF snapshot and stream it without a JSONL expansion."""

    def __init__(
        self,
        root: Path,
        *,
        repository: str = "kkuroma/GraphIV",
        revision: str = "GraphIV-2026-10-01",
        commit: str = "",
        source_manifest: Path | None = None,
        batch_size: int = 2048,
    ) -> None:
        import pyarrow as pa
        import pyarrow.parquet as pq

        if batch_size < 1:
            raise ValueError("The Parquet batch size must be positive")
        self.root = Path(root)
        self.repository = repository
        self.revision = revision
        self.commit = commit
        self.batch_size = batch_size
        self.files = {table: sorted((self.root / table).glob("*.parquet")) for table in TABLES}
        if any(not files for files in self.files.values()):
            raise ValueError(
                "A published snapshot needs papers, citations, and topics Parquet files"
            )
        self.expected_rows = {table: 0 for table in TABLES}
        self.decoded_rows = {table: 0 for table in TABLES}
        self.file_metadata: list[dict[str, Any]] = []
        self.embedding_dimension: int | None = None
        self.embedding_dtype = ""
        for table, files in self.files.items():
            for path in files:
                parquet = pq.ParquetFile(path)
                rows = parquet.metadata.num_rows
                schema = parquet.schema_arrow
                required = {
                    "papers": {"arxiv_id", "title", "abstract", "date", "embedding"},
                    "citations": {"source_id", "target_id", "intent", "intent_score"},
                    "topics": {
                        "arxiv_id",
                        "level_0",
                        "level_1",
                        "level_2",
                        "name_0",
                        "name_1",
                        "name_2",
                    },
                }[table]
                if not required.issubset(schema.names):
                    raise ValueError(f"{path.name} is missing published {table} columns")
                if table == "papers":
                    embedding = schema.field("embedding").type
                    if not pa.types.is_fixed_size_list(embedding):
                        raise ValueError("Published embeddings must be fixed-size Arrow lists")
                    if not pa.types.is_float16(embedding.value_type):
                        raise ValueError("Published GraphIV embeddings must retain float16 values")
                    if self.embedding_dimension not in {None, embedding.list_size}:
                        raise ValueError("Paper shards have inconsistent embedding dimensions")
                    self.embedding_dimension = embedding.list_size
                    self.embedding_dtype = "float16"
                self.expected_rows[table] += rows
                self.file_metadata.append(
                    {
                        "path": f"{table}/{path.name}",
                        "size": path.stat().st_size,
                        "rows": rows,
                    }
                )
        if source_manifest is not None:
            self._verify_source_manifest(Path(source_manifest))
        if not self.commit and re.fullmatch(r"[a-f0-9]{40}", self.root.name):
            self.commit = self.root.name

    def _verify_source_manifest(self, path: Path) -> None:
        declared = json.loads(path.read_text())
        if not isinstance(declared, dict) or not isinstance(declared.get("files"), list):
            raise ValueError("The source manifest needs a files list")
        expected = {}
        for item in declared["files"]:
            if not isinstance(item, dict):
                raise ValueError("The source manifest has an invalid file entry")
            name = validate_blob_name(item.get("path", item.get("name")))
            if name.split("/")[0] not in TABLES or not name.endswith(".parquet"):
                continue
            if name in expected:
                raise ValueError("The source manifest repeats a Parquet path")
            expected[name] = item
        actual = {item["path"]: item for item in self.file_metadata}
        if set(actual) != set(expected):
            raise ValueError("The local Parquet files do not match the complete source manifest")
        for name, item in actual.items():
            entry = expected[name]
            if entry.get("size") != item["size"]:
                raise ValueError(f"The source file size does not match: {name}")
            digest = entry.get("sha256")
            if digest:
                if file_sha256(self.root / name) != digest:
                    raise ValueError(f"The source file checksum does not match: {name}")
                item["sha256"] = digest
        declared_commit = str(declared.get("commit", declared.get("revision", "")))
        if re.fullmatch(r"[a-f0-9]{40}", declared_commit):
            if self.commit and self.commit != declared_commit:
                raise ValueError("The requested commit disagrees with the source manifest")
            self.commit = declared_commit
        if declared.get("repository") not in (None, self.repository):
            raise ValueError("The source repository disagrees with the source manifest")

    def _batches(self, table: str) -> Iterator[Any]:
        import pyarrow.parquet as pq

        for path in self.files[table]:
            yield from pq.ParquetFile(path).iter_batches(
                batch_size=self.batch_size, use_threads=False
            )

    def paper_rows(self) -> Iterator[dict[str, Any]]:
        """Yield document records with lossless Arrow float16 embedding views."""
        for batch in self._batches("papers"):
            columns = {name: batch.column(index) for index, name in enumerate(batch.schema.names)}
            embeddings = columns.pop("embedding")
            metadata = {name: column.to_pylist() for name, column in columns.items()}
            for row in range(batch.num_rows):
                item = {name: values[row] for name, values in metadata.items()}
                scalar = embeddings[row]
                if not scalar.is_valid:
                    raise ValueError("Published embedded papers cannot have null embeddings")
                item["embed_full"] = scalar.values.to_numpy(zero_copy_only=False)
                item["stage"] = 3
                self.decoded_rows["papers"] += 1
                yield item

    def citation_rows(self) -> Iterator[dict[str, Any]]:
        """Retain every occurrence and confidence while leaving unpublished sentences absent."""
        ordinal = 0
        for batch in self._batches("citations"):
            columns = batch.to_pydict()
            for row in range(batch.num_rows):
                ordinal += 1
                item = {name: values[row] for name, values in columns.items()}
                intent = item.get("intent")
                score = item.get("intent_score")
                if intent is not None and intent not in INTENTS:
                    raise ValueError("A published citation has an unknown intent label")
                if score is not None and (
                    not math.isfinite(float(score)) or not 0 <= float(score) <= 1
                ):
                    raise ValueError("A published citation has an invalid intent confidence")
                item.update(
                    citation_id=ordinal, stage=1 if intent is not None else 0, sentence=None
                )
                self.decoded_rows["citations"] += 1
                yield item

    def topic_rows(self) -> Iterator[dict[str, Any]]:
        """Reconstruct completed and incomplete topic-tree rows from flattened columns."""
        for batch in self._batches("topics"):
            columns = batch.to_pydict()
            for row in range(batch.num_rows):
                item = {name: values[row] for name, values in columns.items()}
                levels = [item.get(f"level_{level}") for level in range(3)]
                item["stage"] = int(all(level is not None for level in levels))
                self.decoded_rows["topics"] += 1
                yield item

    def topic_name_rows(self) -> Iterator[dict[str, Any]]:
        """Deduplicate the small set of flattened hierarchy names without collecting papers."""
        seen: dict[tuple[int, int | None, int | None], str] = {}
        for batch in self._batches("topics"):
            columns = batch.to_pydict()
            for row in range(batch.num_rows):
                values = [columns[f"level_{level}"][row] for level in range(3)]
                for level in range(3):
                    name = columns[f"name_{level}"][row]
                    if name is None or any(value is None for value in values[: level + 1]):
                        continue
                    key = (
                        values[0],
                        values[1] if level >= 1 else None,
                        values[2] if level >= 2 else None,
                    )
                    if key in seen:
                        if seen[key] != name:
                            raise ValueError(
                                "Published topic names disagree for the same hierarchy ID"
                            )
                        continue
                    seen[key] = name
                    yield {"level_0": key[0], "level_1": key[1], "level_2": key[2], "name": name}

    def provenance(self) -> dict[str, Any]:
        """Describe the pinned input files, row counts, and published evidence limitations."""
        return {
            "repository": self.repository,
            "revision": self.revision,
            "commit": self.commit,
            "format": "parquet",
            "files": self.file_metadata,
            "rows": self.expected_rows,
            "embedding_dtype": self.embedding_dtype,
            "citation_sentences": "not published; no JIT extraction performed",
        }

    def verify_counts(self) -> None:
        """Require each primary input stream to consume every footer-declared row."""
        if self.decoded_rows != self.expected_rows:
            raise ValueError("Decoded Parquet row counts do not match the complete source footers")
