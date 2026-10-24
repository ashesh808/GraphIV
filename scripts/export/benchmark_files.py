"""
The published benchmark files: the schema, the topic-grouped split, and reading a split back

A split is assigned per parent topic, so no topic sits on both sides of a train and test comparison
"""

from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.eval.cases import Sample

SPLITS = ("train", "val", "test")
# the one seed every published version is split with
SPLIT_SEED = 69420
FOLDERS = {
    "SurveyMatch": "surveymatch",
    "FrontierMatch": "frontiermatch",
    "ConsensusMatch": "consensusmatch",
    "PrecisionMatch": "surveymatch",
}
HEADLINE_K = {"SurveyMatch": 1000, "FrontierMatch": 1000, "ConsensusMatch": 100}

SCHEMA = pa.schema(
    [
        ("case_id", pa.string()),
        ("split", pa.string()),
        ("query_text", pa.string()),
        ("query_drafter", pa.string()),
        ("date_max", pa.date32()),
        ("anchors", pa.list_(pa.string())),
        ("anchor_titles", pa.list_(pa.string())),
        ("anchor_dates", pa.list_(pa.date32())),
        ("anchor_survey_probability", pa.list_(pa.float32())),
        ("citations", pa.list_(pa.string())),
        ("n_citations", pa.int32()),
        ("headline_k", pa.int32()),
        ("topic_l0", pa.int32()),
        ("topic_l1", pa.int32()),
        ("topic_l2", pa.int32()),
        ("topic_l0_name", pa.string()),
        ("topic_l1_name", pa.string()),
        ("topic_l2_name", pa.string()),
        ("split_group", pa.string()),
        ("gap_days", pa.int32()),
        ("cosine", pa.float32()),
    ]
)


def get_split_group(leaf: list[int]) -> str:
    """
    The unit a split is assigned by, which is a case's parent topic

    Args:
        leaf: The three tree levels.

    Returns:
        The parent as `level_0.level_1`.
    """
    return f"{leaf[0]}.{leaf[1]}"


def assign_splits(samples: list[Sample], ratios: tuple[float, float, float]) -> list[str]:
    """
    One split per sample, filled a whole parent topic at a time to the given shares

    Topics are taken in seeded hash order and each goes to the split furthest under its share,
    so the shares land close to the target and a topic never straddles two splits.

    Args:
        samples: The mined samples.
        ratios: The train, val and test shares.

    Returns:
        The split of each sample, in the same order.
    """
    sizes = Counter(get_split_group(s.leaf) for s in samples)
    order = sorted(sizes, key=lambda g: hashlib.sha1(f"{SPLIT_SEED}:{g}".encode()).hexdigest())
    total = sum(sizes.values())
    filled = dict.fromkeys(SPLITS, 0)
    chosen: dict[str, str] = {}
    for group in order:
        split = max(SPLITS, key=lambda s: ratios[SPLITS.index(s)] * total - filled[s])
        chosen[group] = split
        filled[split] += sizes[group]
    return [chosen[get_split_group(s.leaf)] for s in samples]


def write_split(rows: list[dict[str, object]], path: Path) -> None:
    """
    One split of one benchmark as a Parquet file

    Args:
        rows: The cases, one dict per row keyed by the schema's columns.
        path: Where the file lands.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), path)


def read_cases(root: Path, metric: str, split: str, limit: int = 0) -> list[Sample]:
    """
    One split of a published benchmark as the samples a run scores

    Args:
        root: The benchmark release, graphiv-benchmarks-<cutoff>.
        metric: SurveyMatch, FrontierMatch, ConsensusMatch or PrecisionMatch.
        split: train, val or test.
        limit: The most cases to read, every case when zero.

    Returns:
        The samples, their query already written.
    """
    rows = pq.read_table(root / FOLDERS[metric] / f"{split}.parquet").to_pylist()
    rows = rows[:limit] if limit else rows
    return [
        Sample(
            metric=metric,
            sample_id=str(r["case_id"]),
            anchors=list(r["anchors"]),
            titles=list(r["anchor_titles"]),
            abstracts=[],
            leaf=[int(r["topic_l0"]), int(r["topic_l1"]), int(r["topic_l2"])],
            cutoff=r["date_max"].isoformat(),
            key=list(r["citations"]),
            query=str(r["query_text"]),
            extra={k: float(r[k]) for k in ("gap_days", "cosine") if r[k] is not None},
        )
        for r in rows
    ]
