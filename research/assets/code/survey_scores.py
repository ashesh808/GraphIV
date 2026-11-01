"""
Scores the survey labeler for its two figures from the store, and caches what it finds

Held-out scores are the store's own survey_probability for those papers, cached in survey.json
The three-family agreement counts are the 2026-09-15 labeling check, which no file keeps
"""

from __future__ import annotations

import csv
import json
import re
import tomllib
from pathlib import Path
from typing import Any

import external_types
import numpy as np
import psycopg
from sklearn.metrics import average_precision_score, precision_recall_curve
from style import DATA

from src.core.config import load_config

CACHE = DATA / "survey.json"

# the title words the positive candidate pile was drawn on, as in train_distilbert.py
REVIEW_WORDS = re.compile(
    r"survey|review|overview|tutorial|taxonom|state of the art|systematic"
    r"|advances in|progress in|perspectives on|landscape",
    re.I,
)
# the threshold the store's own counts and the manager's dashboard use
THRESHOLD = 0.5
GRID = np.linspace(0.0, 1.0, 201)
TRIALS = 1000
# how many of Gemma 4, Qwen 3.6 and GLM 4.7 called each of 376 papers a review
AGREEMENT = {0: 179, 1: 9, 2: 21, 3: 167}
# papers scored and seconds taken by stage4 on a delta, from the manager's measured rates
RATE = (48_895, 229)
SPEED = round(RATE[0] / RATE[1])


def read_labels(path: Path) -> dict[str, np.ndarray]:
    """
    The labeled papers with their pile and split

    Args:
        path: is_survey.csv.

    Returns:
        Ids, labels, whether the title carries a review word, and whether the row trained.
    """
    csv.field_size_limit(1 << 24)
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    truthy = ("1", "True", "true")
    return {
        "ids": np.array([r["arxiv_id"] for r in rows]),
        "y": np.array([r["is_survey"] in truthy for r in rows]),
        "word": np.array([REVIEW_WORDS.search(r["title"] or "") is not None for r in rows]),
        "train": np.array([r["train"] in truthy for r in rows]),
    }


def weighted_curve(y: np.ndarray, p: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, float]:
    """
    Precision on a fixed recall grid and the average precision, each row weighted

    Args:
        y: Labels.
        p: Scores.
        w: How many real papers each row stands for.

    Returns:
        Precision at each recall in GRID, and the average precision.
    """
    precision, recall, _ = precision_recall_curve(y, p, sample_weight=w)
    # the curve comes back with recall descending, and np.interp needs it ascending
    return np.interp(GRID, recall[::-1], precision[::-1]), float(
        average_precision_score(y, p, sample_weight=w)
    )


def share(w: np.ndarray, mask: np.ndarray, within: np.ndarray) -> float:
    """
    The weighted share of one set of papers that also falls in another

    Args:
        w: How many real papers each row stands for.
        mask: The papers counted.
        within: The papers counted out of.

    Returns:
        The share, so precision when within is what was flagged and recall when it is the reviews.
    """
    return float((w * (mask & within)).sum() / (w * within).sum())


def sample(config: Path) -> dict[str, Any]:
    """
    The labeled papers, their pile weights, and the store's score for each

    Args:
        config: The config naming the store and the survey model's directory.

    Returns:
        The labels, the weights, the scores, the held-out mask and the pile sizes.
    """
    cfg = load_config(config)
    root = Path(str(cfg["survey"]["MODEL_PATH"]))
    piles = tomllib.loads((root / "hyperparam.toml").read_text(encoding="utf-8"))["class_weight"]
    rows = read_labels(root / "is_survey.csv")
    with psycopg.connect(str(cfg["database"]["PG_DEST"])) as conn:
        stored = dict(
            conn.execute(
                "SELECT arxiv_id, survey_probability FROM papers WHERE arxiv_id = ANY(%s)",
                (rows["ids"].tolist(),),
            ).fetchall()
        )
    p = np.array([stored.get(i, np.nan) for i in rows["ids"]], dtype=float)
    word = rows["word"]
    w = np.where(
        word, int(piles["POS_CANDIDATE"]) / word.sum(), int(piles["NEG_CANDIDATE"]) / (~word).sum()
    )
    return {**rows, "p": p, "w": w, "held": ~rows["train"] & ~np.isnan(p), "piles": piles}


def score(rows: dict[str, Any]) -> dict[str, Any]:
    """
    The labeler's curves and operating point on the held-out papers, beside the title filter

    Args:
        rows: What sample returns.

    Returns:
        The curves, the operating point, the title filter, the piles and the three areas.
    """
    y, word, w, held, piles = rows["y"], rows["word"], rows["w"], rows["held"], rows["piles"]
    yt, pt, wt, wordt = y[held], rows["p"][held], w[held], word[held]

    curve, area = weighted_curve(yt, pt, wt)
    rng = np.random.default_rng(0)
    # resample within each pile and label, so every trial keeps the held-out set's make-up
    cells = [np.flatnonzero((wordt == a) & (yt == b)) for a in (True, False) for b in (True, False)]
    band = np.empty((TRIALS, len(GRID)))
    for trial in range(TRIALS):
        pick = np.concatenate([rng.choice(c, len(c)) for c in cells])
        band[trial], _ = weighted_curve(yt[pick], pt[pick], wt[pick])
    stress = []
    pos, neg = np.flatnonzero(yt), np.flatnonzero(~yt)
    # a fresh generator on the trainer's seed, so the draws repeat train_distilbert.py's
    rng = np.random.default_rng(0)
    for _ in range(TRIALS):
        pick = np.concatenate([rng.choice(neg, 5000), rng.choice(pos, 50)])
        stress.append(average_precision_score(yt[pick], pt[pick]))

    flagged = pt >= THRESHOLD
    return {
        "held": int(held.sum()),
        "curve": curve.tolist(),
        "sd": band.std(axis=0, ddof=1).tolist(),
        "areas": {
            "sampled": float(average_precision_score(yt, pt)),
            "weighted": area,
            "stress": float(np.mean(stress)),
            "stress_sd": float(np.std(stress, ddof=1)),
        },
        "model": {
            "precision": share(wt, yt, flagged),
            "recall": share(wt, flagged, yt),
            "recall_word": float(flagged[yt & wordt].mean()),
            "recall_plain": float(flagged[yt & ~wordt].mean()),
        },
        "title": {
            "precision": share(wt, yt, wordt),
            "recall": share(wt, wordt, yt),
        },
        "positives": {"word": int((yt & wordt).sum()), "plain": int((yt & ~wordt).sum())},
        "piles": {
            "word": [int(word.sum()), int(y[word].sum()), int(piles["POS_CANDIDATE"])],
            "plain": [int((~word).sum()), int(y[~word].sum()), int(piles["NEG_CANDIDATE"])],
        },
        "plain_share": float((w * (y & ~word)).sum() / (w * y).sum()),
        "trained": int(rows["train"].sum()),
    }


def compare(rows: dict[str, Any]) -> dict[str, Any]:
    """
    Semantic Scholar's and OpenAlex's own review types on the held-out papers, scored as a filter

    A paper either service does not resolve or type counts as not flagged, as it would in use

    Args:
        rows: What sample returns.

    Returns:
        Each service's precision, recall and coverage, and the date its types were fetched.
    """
    held = rows["held"]
    ids, yt, wt = rows["ids"][held].tolist(), rows["y"][held], rows["w"][held]
    fetched = external_types.load(ids)
    scholar = [fetched["semantic_scholar"].get(i) for i in ids]
    openalex = [fetched["openalex"].get(i) for i in ids]
    out: dict[str, Any] = {"fetched": fetched["fetched"]}
    for name, flags, known in (
        ("Semantic Scholar", ["Review" in (t or []) for t in scholar], [bool(t) for t in scholar]),
        ("OpenAlex", [t == "review" for t in openalex], [t is not None for t in openalex]),
    ):
        flag = np.array(flags)
        out[name] = {
            "precision": share(wt, yt, flag),
            "recall": share(wt, flag, yt),
            "typed": float(np.mean(known)),
        }
    return out


def load(config: Path) -> dict[str, Any]:
    """
    Scores the held-out papers on whatever the cache does not hold yet

    Args:
        config: The config naming the store and the survey model's directory.

    Returns:
        What score and compare return, together.
    """
    data = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.is_file() else {}
    if "curve" in data and "sources" in data:
        return data
    rows = sample(config)
    if "curve" not in data:
        data.update(score(rows))
    if "sources" not in data:
        data["sources"] = compare(rows)
    _ = CACHE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data
