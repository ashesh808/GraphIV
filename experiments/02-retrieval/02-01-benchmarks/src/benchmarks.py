"""
Compared to an existing benchmark, how does GraphIV do, and does their task transfer

Six sections: reproduce their number, run ours on their task, define our task, run both on it
Nothing calls a model: every arm was scored once and this reads the cached scores
"""

from __future__ import annotations

import json
import statistics
from typing import Any

from _harness.report import tables
from _harness.report.paths import experiment, read_json
from _harness.report.viz import bar_chart

CACHE, RESULTS, REPO = experiment(__file__)

# a reference counts as gold once the survey mentions it this often
MENTION_FLOOR = 3

# the winning selector, named so the ORACLE row cannot be picked up by accident
JOINT_ARM = "agen_relw0.35_ley8_nores"

# the title regex plus the reference and citation floors, before any model saw a candidate
N_SQL_CANDIDATES = 1003
N_SCREEN_PASS = 122

# LitSearch table 3, title and abstract indexing
PUBLISHED = {
    "BM25": (50.0, 39.9),
    "GTR-T5-large": (39.6, 43.8),
    "Instructor-XL": (52.3, 56.5),
    "E5-large-v2": (56.2, 55.4),
    "GritLM-7B": (74.8, 70.8),
    "GPT-4 rerank over BM25": (68.0, 59.9),
    "GPT-4 rerank over GritLM": (79.2, 75.3),
}
OURS = {
    "dense": "ours, dense only",
    "grade only (reader rerank)": "ours, reader rerank",
    "graph only (citations-per-year)": "ours, graph only",
    "joint (graph + grade)": "ours, joint",
}


def _read(name: str) -> Any:  # pyright: ignore[reportExplicitAny, reportAny]
    return read_json(CACHE / name)


def section_1_reproduce() -> list[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    """
    Their BM25 through our harness, against the figure printed in their table 3
    """
    got: dict[str, float] = _read("bm25_recall.json")  # pyright: ignore[reportAny]
    pub = PUBLISHED["BM25"]
    return [
        {"cell": "specific R@5", "published": pub[0], "reproduced": round(got["1_5"] * 100, 1)},
        {"cell": "broad R@20", "published": pub[1], "reproduced": round(got["0_20"] * 100, 1)},
    ]


def section_2_ours_on_theirs() -> list[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    """
    Every published system and every channel of ours, on their corpus and their metric
    """
    got: dict[str, dict[str, float]] = _read("rerank_recall.json")  # pyright: ignore[reportAny]
    rows = [
        {"system": name, "specific R@5": s, "broad R@20": b, "source": "published"}
        for name, (s, b) in PUBLISHED.items()
    ]
    rows += [
        {
            "system": label,
            "specific R@5": round(got[key]["1_5"] * 100, 1),
            "broad R@20": round(got[key]["0_20"] * 100, 1),
            "source": "measured",
        }
        for key, label in OURS.items()
    ]
    rows.sort(key=lambda r: float(r["specific R@5"]))
    return rows


def section_4_our_task() -> list[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    """
    The two answer keys side by side, which is the whole reason the tasks do not transfer
    """
    kept: list[dict[str, Any]] = _read("battery60.json")  # pyright: ignore[reportExplicitAny]
    qrels: dict[str, Any] = _read("qrels.json")  # pyright: ignore[reportExplicitAny]
    gold = [sum(1 for n in v["qrels"].values() if int(n) >= MENTION_FLOOR) for v in qrels.values()]
    text = (CACHE / "litsearch_queries.jsonl").read_text(encoding="utf-8")
    ls = [json.loads(ln) for ln in text.splitlines() if ln.strip()]  # pyright: ignore[reportAny]
    lg = [len(q["corpusids"]) for q in ls]  # pyright: ignore[reportAny]
    return [
        {
            "task": "find this paper (LitSearch)",
            "questions": len(ls),
            "mean answers": round(statistics.mean(lg), 2),
            "one-answer share": f"{sum(1 for g in lg if g == 1) / len(lg):.0%}",
            "key written by": "the citing author",
        },
        {
            "task": "cover this field (ours)",
            "questions": len(kept),
            "mean answers": round(statistics.mean(gold), 1),
            "one-answer share": "0%",
            "key written by": "the survey author",
        },
    ]


def section_4_how_built() -> (
    tuple[list[dict[str, Any]], list[dict[str, Any]]]
):  # pyright: ignore[reportExplicitAny]
    """
    How 1003 keyword hits became 60 usable surveys, and why the key is mention count

        Survey references really are about 90 percent background, which looks like a usable
        signal until ordinary papers with the same categories and reference counts come back
        higher still, so citation intent is dropped and mention frequency replaces it.
    """
    kept: list[dict[str, Any]] = _read("battery60.json")  # pyright: ignore[reportExplicitAny]
    cand = _read("cand140.json")
    funnel = [
        {"stage": "title regex, 60+ refs, 20+ cites, 2022-2024", "surveys": N_SQL_CANDIDATES},
        {
            "stage": "sampled for the abstract screen",
            "surveys": len(cand),
        },  # pyright: ignore[reportAny]
        {"stage": "screen says it is a real review", "surveys": N_SCREEN_PASS},
        {"stage": "kept, spread over 17 archives", "surveys": len(kept)},
        {
            "stage": "held out, never tuned on",
            "surveys": sum(1 for x in kept if x["split"] == "test"),
        },
    ]
    rows: list[dict[str, Any]] = _read("intent_control.json")  # pyright: ignore[reportExplicitAny]
    intent = [
        {
            "arm": arm,
            "papers": sum(1 for r in rows if r["arm"] == arm),
            "median background %": round(
                statistics.median([float(r["bg"]) for r in rows if r["arm"] == arm]), 1
            ),
        }
        for arm in ("survey", "control")
    ]
    return funnel, intent


def section_5_theirs_on_ours() -> (
    tuple[list[dict[str, Any]], int, int]
):  # pyright: ignore[reportExplicitAny]
    """
    Flat retrieval the way their protocol does it, scored on our task, against our selector

        Their arms get the same slot budget and the same held-out surveys, so the only
        difference is that theirs have no citation graph and no reader behind them.
        Two ceilings are returned because the graph arms select out of a built pool, so
        they can never reach a gold paper the pool stage missed, while the flat arms can.
    """
    flat: dict[str, Any] = _read("flat.json")  # pyright: ignore[reportExplicitAny]
    qrels: dict[str, Any] = _read("qrels.json")  # pyright: ignore[reportExplicitAny]
    final: dict[str, Any] = _read("final_per_survey.json")  # pyright: ignore[reportExplicitAny]
    names = {"lexical_flat": "lexical only", "dense_flat": "dense only", "rrf_flat": "RRF of both"}
    found: dict[str, int] = {k: 0 for k in names}
    ceiling = 0
    for aid, rec in flat.items():
        if str(rec["split"]) != "test":
            continue
        q = qrels.get(aid)
        if q is None:
            continue
        gold = {k for k, n in q["qrels"].items() if int(n) >= MENTION_FLOOR}
        ceiling += len(gold)
        for arm in names:
            found[arm] += len(set(rec["ranked"][arm][: int(rec["m"])]) & gold)
    rows = [
        {"selector": names[a], "graph": "no", "reader": "no", "gold found": found[a]} for a in names
    ]
    per: dict[str, Any] = final["per_survey"]  # pyright: ignore[reportExplicitAny]
    for arm, label in (("ppr", "ours, ppr"), ("frontier", "ours, frontier")):
        if arm in per:
            rows.append(
                {
                    "selector": label,
                    "graph": "yes",
                    "reader": "yes",
                    "gold found": sum(int(x) for x in per[arm]["test"]),
                }
            )
    rows.append(
        {
            "selector": "ours, joint",
            "graph": "yes",
            "reader": "yes",
            "gold found": sum(int(x) for x in per[JOINT_ARM]["test"]),
        }
    )
    rows.sort(key=lambda r: int(r["gold found"]))
    return rows, ceiling, int(final["ceiling"]["test"])


def run() -> None:
    """
    Print the six sections in order and write the tables, macros and figures
    """
    RESULTS.mkdir(parents=True, exist_ok=True)
    repro = section_1_reproduce()
    theirs = section_2_ours_on_theirs()
    task = section_4_our_task()
    funnel, intent = section_4_how_built()
    ours, all_gold, in_pool = section_5_theirs_on_ours()
    gap = next(r for r in theirs if r["system"] == "ours, reader rerank")
    graph = next(r for r in theirs if r["system"] == "ours, graph only")
    payload = {
        "reproduce": repro,
        "ours_on_theirs": theirs,
        "task_shapes": task,
        "selection_funnel": funnel,
        "intent_control": intent,
        "on_our_task": ours,
        "test_gold_total": all_gold,
        "test_gold_in_pool": in_pool,
    }
    _ = (RESULTS / "metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tables.write(
        RESULTS,
        theirs,
        ["system", "specific R@5", "broad R@20", "source"],
        [("system", "system"), ("specific R@5", "spec R@5"), ("broad R@20", "broad R@20")],
        macro_pairs=[
            ("bmTwentyFiveSpec", repro[0]["reproduced"]),
            ("bmTwentyFiveBroad", repro[1]["reproduced"]),
            ("readerRerankSpec", gap["specific R@5"]),
            ("graphOnlySpec", graph["specific R@5"]),
            ("testGoldTotal", all_gold),
            ("testGoldInPool", in_pool),
        ],
        caption="LitSearch, title and abstract indexing; published rows from their table 3",
    )
    bar_chart(
        theirs,
        "system",
        [("specific R@5", "LitSearch specific R@5"), ("broad R@20", "LitSearch broad R@20")],
        RESULTS / "on_their_task.png",
    )
    bar_chart(
        ours,
        "selector",
        [("gold found", f"gold found on our task, 30 held-out surveys, {all_gold} gold")],
        RESULTS / "on_our_task.png",
    )
    print("\n1. reproduce their number")
    for r in repro:
        print(f"   {r['cell']}: published {r['published']}, ours {r['reproduced']}")
    print("\n2+3. our methods on their task")
    for r in theirs:
        print(f"   {r['system']:<28} {r['specific R@5']:>6} {r['broad R@20']:>6}  {r['source']}")
    print("\n4. our own task")
    for r in task:
        print("   " + "  ".join(f"{k}={v}" for k, v in r.items()))
    print("   how the 60 surveys were picked")
    for r in funnel:
        print(f"      {r['stage']:<44} {r['surveys']:>5}")
    print("   citation intent does not separate a survey from an ordinary paper")
    for r in intent:
        print(
            f"      {r['arm']:<10} {r['papers']:>3} papers, "
            f"{r['median background %']}% background"
        )
    print(
        f"\n5. both method families on our task, {all_gold} gold "
        f"({in_pool} of it reachable by a pool-then-select method)"
    )
    for r in ours:
        print(
            f"   {r['selector']:<16} graph={r['graph']:<3} reader={r['reader']:<3} "
            f"{r['gold found']:>4}"
        )
