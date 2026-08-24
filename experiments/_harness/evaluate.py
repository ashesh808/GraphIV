"""
Tie the instruments together: turn one phase-6 run into a full metric row
And aggregate rows across topics

Keeps each experiment's run.py short and uniform.
"""

from __future__ import annotations

from pathlib import Path
from statistics import mean
from typing import Any

from .metrics import load_run, metric_vector
from .topics import GoldTopic, recall


def eval_run(
    meta: dict[str, Any],
    out_dir: Path,
    topic: GoldTopic | None = None,
    *,
    do_judge: bool = False,
    do_faith: bool = False,
    do_vision: bool = False,
) -> dict[str, Any]:
    """
    Metric vector (+ optional independent judge + faithfulness + vision check + recall)
    """
    _, report = load_run(out_dir)
    row = metric_vector(meta, report)
    if do_vision:
        from .vision_check import caption_faithfulness

        figs = meta.get("figures") or {}
        vc = (
            caption_faithfulness(out_dir, figs)
            if figs
            else {"checked": 0, "caption_faithfulness": 0.0}
        )
        row["fig_checked"] = vc["checked"]
        row["caption_faithfulness"] = vc["caption_faithfulness"]
    if topic is not None:
        row.update(recall([lm["arxiv_id"] for lm in meta.get("landmarks", [])], topic))
    if do_judge:
        from .judge import judge_report

        canon = list(topic.canonical) if topic else []
        j = judge_report(str(meta["question"]), report, canon)
        for k in ("grounding", "coverage", "lineage", "coherence", "overall"):
            row[f"j_{k}"] = j[k]
        row["j_critique"] = j["critique"]
    if do_faith:
        from .faithfulness import faithfulness

        f = faithfulness(report)
        row["faithfulness"] = f["faithfulness"]
        row["faith_sampled"] = f["sampled"]
    return row


def aggregate(rows: list[dict[str, Any]], group_key: str, keep: list[str]) -> list[dict[str, Any]]:
    """
    Mean each numeric metric in `keep` per `group_key` value (across topics)
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        groups.setdefault(str(r[group_key]), []).append(r)
    out: list[dict[str, Any]] = []
    for g, rs in groups.items():
        agg: dict[str, Any] = {group_key: g, "n_topics": len(rs)}
        for k in keep:
            vals = [float(r[k]) for r in rs if isinstance(r.get(k), (int, float))]
            agg[k] = round(mean(vals), 2) if vals else None
        out.append(agg)
    return out
