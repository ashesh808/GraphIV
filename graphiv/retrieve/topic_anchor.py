"""
Anchor the pool to its home topic leaf, read off the top seeds' membership

The query is a 768-d vector while the tree lives in UMAP-50, so it cannot be placed directly
Reading the leaf off the seeds is a join on arxiv id, which needs no UMAP transform
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from graphiv.core.settings import TOPIC_TREE_DB

# Default tree = the canonical rebuilt artifact (phase-5 output, global-config path)
REBUILT = TOPIC_TREE_DB


class TopicTree:
    """
    Leaf/path lookups over a topic-tree SQLite (rebuilt or strat-3 schema)
    """

    db: Path
    kind: str

    def __init__(self, db: Path | None = None) -> None:
        self.db = db or REBUILT
        # the two tree schemas are told apart by which table is present
        conn = sqlite3.connect(self.db)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        self.kind = "rebuilt" if "paper_topic" in tables else "strat3"

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db)

    def leaves_of(self, arxiv_ids: list[str]) -> dict[str, tuple[str, str]]:
        """
        arxiv_id -> (leaf_key, path)

        For strat3, leaf = 'g1/g2/g3', path = 'g1/g2'.
        """
        if not arxiv_ids:
            return {}
        conn = self._conn()
        out: dict[str, tuple[str, str]] = {}
        qmarks = ",".join("?" * len(arxiv_ids))
        if self.kind == "rebuilt":
            rows = conn.execute(
                f"SELECT arxiv_id, leaf_id, path FROM paper_topic " f"WHERE arxiv_id IN ({qmarks})",
                arxiv_ids,
            ).fetchall()
            for aid, leaf, path in rows:
                out[aid] = (str(leaf), str(path))
        else:
            rows = conn.execute(
                f"SELECT id, group1_id, group2_id, group3_id FROM cluster_assignment "
                f"WHERE id IN ({qmarks})",
                arxiv_ids,
            ).fetchall()
            for aid, g1, g2, g3 in rows:
                out[aid] = (f"{g1}/{g2}/{g3}", f"{g1}/{g2}")
        conn.close()
        return out

    def members(self, leaf_key: str, limit: int = 2000) -> list[str]:
        """
        All arxiv_ids in a leaf (for niche-drill)
        """
        conn = self._conn()
        if self.kind == "rebuilt":
            rows = conn.execute(
                "SELECT arxiv_id FROM paper_topic WHERE leaf_id=? LIMIT ?",
                (int(leaf_key), limit),
            ).fetchall()
        else:
            g1, g2, g3 = leaf_key.split("/")
            rows = conn.execute(
                "SELECT id FROM cluster_assignment WHERE group1_id=? AND group2_id=? "
                "AND group3_id=? LIMIT ?",
                (g1, g2, g3, limit),
            ).fetchall()
        conn.close()
        return [r[0] for r in rows]


def dominant_leaf(
    tree: TopicTree, seeds: list[tuple[str, float]], topk: int = 30
) -> tuple[str | None, str | None]:
    """
    Similarity-weighted vote for the home (leaf, parent-path) over the top seeds
    """
    top = sorted(seeds, key=lambda x: x[1], reverse=True)[:topk]
    lk = tree.leaves_of([a for a, _ in top])
    leaf_w: dict[str, float] = {}
    path_w: dict[str, float] = {}
    for aid, sc in top:
        if aid in lk:
            leaf, path = lk[aid]
            leaf_w[leaf] = leaf_w.get(leaf, 0.0) + sc
            path_w[path] = path_w.get(path, 0.0) + sc
    leaf = max(leaf_w, key=lambda k: leaf_w[k]) if leaf_w else None
    path = max(path_w, key=lambda k: path_w[k]) if path_w else None
    return leaf, path


def anchor_keep(
    tree: TopicTree,
    arxiv_ids: list[str],
    dom_leaf: str | None,
    dom_path: str | None,
    use_siblings: bool = True,
) -> set[str]:
    """
    Subset of `arxiv_ids` in the home leaf (or, if use_siblings, same parent path)
    """
    if dom_leaf is None:
        return set(arxiv_ids)
    lk = tree.leaves_of(arxiv_ids)
    keep: set[str] = set()
    for aid in arxiv_ids:
        if aid not in lk:
            continue
        leaf, path = lk[aid]
        if leaf == dom_leaf or (use_siblings and dom_path is not None and path == dom_path):
            keep.add(aid)
    return keep
