"""One-lever ablation driver: sweep a set of conditions over a set of gold topics, evaluate
each run with the shared instruments, aggregate across topics, and write the paper artifacts
(metrics_raw.json, metrics.json, metrics.md, ablation.png). Each experiment's run.py just
declares its conditions + which metrics to tabulate/plot.

TWO-PHASE to avoid model thrash on a single GPU: (1) GENERATE every (topic x condition) run +
objective metrics (phase-6 uses the Code generator + nomic); (2) EVALUATE the cached reports in
model-grouped batches — all judge + faithfulness + pairwise calls together (Gemma-4-26B loaded
once), then all vision caption checks together (Vision loaded once). This collapses eval-time
26B model loads from ~2/run to ~2 total. Shared `out_root` (`shared_runs=True`) lets identical
deep cells dedup across experiments via the runner cache.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ._boot import REPO as _REPO
from .metrics import load_run, metric_vector, write_table
from .runner import run_phase6
from .topics import TOPICS, recall
from .viz import bar_chart

# shared run store (committed, browsable): identical cells dedup across experiments 9-12; the
# detailed reports live here, surfaced via experiments/showcase/deep-levers-index.md
DEEP_RUNS = _REPO / "experiments" / "showcase" / "runs"


def run_experiment(
    *,
    results_dir: Path,
    topic_keys: list[str],
    conditions: list[tuple[str, dict[str, Any]]],
    label_key: str,
    table_cols: list[str],
    plot_metrics: list[tuple[str, str]],
    title: str,
    do_judge: bool = False,
    do_faith: bool = False,
    do_vision: bool = False,
    pairwise: tuple[str, str] | None = None,
    shared_runs: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run every (topic x condition), evaluate batched-by-model, aggregate. Returns (raw, agg)."""
    results_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = DEEP_RUNS if shared_runs else results_dir / "runs"
    raw_path = results_dir / "metrics_raw.json"

    def _flush() -> None:
        _ = raw_path.write_text(json.dumps(rows, indent=1), encoding="utf-8")

    # ---- PHASE 1: generate every cell + objective metrics (no judge/vision model) ----
    rows: list[dict[str, Any]] = []
    handles: list[tuple[dict[str, Any], Path, str, str]] = []  # row, out_dir, tk, label
    for tk in topic_keys:
        topic = TOPICS[tk]
        for label, kwargs in conditions:
            print(f"\n[exp] GEN topic={tk} {label_key}={label}", flush=True)
            meta, out_dir = run_phase6(topic.query, runs_dir, **kwargs)
            _, report = load_run(out_dir)
            row = metric_vector(meta, report)
            row.update(
                recall([lm["arxiv_id"] for lm in meta.get("landmarks", [])], topic)
            )
            row["topic"] = tk
            row[label_key] = label
            rows.append(row)
            handles.append((row, out_dir, tk, label))
            _flush()
            print(
                f"[exp] -> frontier={row.get('frontier_count')} 2026={row.get('n_2026')} "
                f"edges={row.get('n_edges')} grounded={row.get('grounded')} "
                f"recall={row.get('landmark_recall')}",
                flush=True,
            )

    # ---- PHASE 2a: judge + faithfulness, batched (Gemma-4-26B loaded once) ----
    if do_judge or do_faith:
        from .faithfulness import faithfulness
        from .judge import judge_report

        for row, out_dir, tk, _ in handles:
            _, report = load_run(out_dir)
            if do_judge:
                canon = list(TOPICS[tk].canonical)
                j = judge_report(TOPICS[tk].query, report, canon)
                for k in ("grounding", "coverage", "lineage", "coherence", "overall"):
                    row[f"j_{k}"] = j[k]
                row["j_critique"] = j["critique"]
            if do_faith:
                f = faithfulness(report)
                row["faithfulness"] = f["faithfulness"]
                row["faith_sampled"] = f["sampled"]
            _flush()

    # ---- PHASE 2b: pairwise top-vs-baseline preference (same Gemma-4-26B) ----
    pair_summary: dict[str, Any] = {}
    if pairwise is not None:
        from .judge import judge_pairwise

        top_l, base_l = pairwise
        by: dict[str, dict[str, Path]] = {}
        for _, out_dir, tk, label in handles:
            by.setdefault(tk, {})[label] = out_dir
        verdicts: list[dict[str, str]] = []
        for tk, d in by.items():
            if top_l not in d or base_l not in d:
                continue
            _, ra = load_run(d[top_l])
            _, rb = load_run(d[base_l])
            v = judge_pairwise(TOPICS[tk].query, ra, rb, list(TOPICS[tk].canonical))
            verdicts.append(v)
        for ax in ("grounding", "coverage", "lineage", "overall"):
            wins = sum(1 for v in verdicts if v[ax] == "A")
            losses = sum(1 for v in verdicts if v[ax] == "B")
            n = len(verdicts)
            pair_summary[ax] = {
                "top_wins": wins,
                "baseline_wins": losses,
                "ties": n - wins - losses,
                "n": n,
                "win_rate": round(wins / n, 2) if n else None,
            }
        pair_summary["compare"] = f"{top_l} (A) vs {base_l} (B)"
        _ = (results_dir / "pairwise.json").write_text(
            json.dumps(pair_summary, indent=1), encoding="utf-8"
        )
        print(f"[exp] pairwise {top_l} vs {base_l}: {pair_summary}", flush=True)

    # ---- PHASE 2c: vision caption faithfulness, batched (Vision loaded once) ----
    if do_vision:
        from .vision_check import caption_faithfulness

        for row, out_dir, _, _ in handles:
            meta_v, _ = load_run(out_dir)
            figs = meta_v.get("figures") or {}
            vc = (
                caption_faithfulness(out_dir, figs)
                if figs
                else {"checked": 0, "caption_faithfulness": 0.0}
            )
            row["fig_checked"] = vc["checked"]
            row["caption_faithfulness"] = vc["caption_faithfulness"]
            _flush()

    # ---- aggregate (+ gold-only recall over gold-bearing topics) ----
    from .evaluate import aggregate

    agg_keys = [c for c in table_cols if c not in (label_key, "n_topics")]
    agg = aggregate(rows, label_key, agg_keys)
    gold_keys = {tk for tk in topic_keys if TOPICS[tk].canonical}
    if gold_keys:
        gold_rows = [r for r in rows if r["topic"] in gold_keys]
        gold_agg = aggregate(gold_rows, label_key, ["landmark_recall", "spine_recall"])
        gmap = {str(g[label_key]): g for g in gold_agg}
        for a in agg:
            g = gmap.get(str(a[label_key]), {})
            a["gold_recall"] = g.get("landmark_recall")
            a["gold_spine_recall"] = g.get("spine_recall")

    _ = (results_dir / "metrics.json").write_text(
        json.dumps(agg, indent=1), encoding="utf-8"
    )
    write_table(agg, table_cols, results_dir / "metrics.md")
    bar_chart(agg, label_key, plot_metrics, results_dir / "ablation.png", title)
    print(f"\n[exp] done -> {results_dir}/metrics.md + ablation.png", flush=True)
    return rows, agg
