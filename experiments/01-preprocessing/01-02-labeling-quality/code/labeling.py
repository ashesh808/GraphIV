"""Labeling-quality compute + figures + tables (experiment 02).

Two halves, no LLM (reads frozen training artifacts): teacher prompt evolution (v1->v6 char growth)
and the distilled DistilBERT student's held-out PRF for both heads (intent 6-way, polarity 3-way),
from data/models/student-v*/test_report.json. File reads are instant, so --use-cache is a no-op here;
a summary is still written to cache/ for uniformity.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]
_REPO = _HERE.parents[4]
sys.path.insert(0, str(_REPO / "experiments"))
from _harness.theme import BARS, ON_SURFACE, SECONDARY, apply_theme  # noqa: E402  # fmt: skip

CACHE = _EXP / "cache"
RESULTS = _EXP / "results"
MODELS = _REPO / "data" / "models"
PROMPTS = _REPO / ".legacy" / "scratchpad" / "intent" / "prompts"
INTENTS = ["uses", "extends", "compares", "motivates", "background", "critiques"]
POLARITIES = ["positive", "neutral", "negative"]
SHIPPED = "v3"  # latest student used for the corpus-wide inference pass


def _load(v: str) -> dict[str, Any]:
    p = MODELS / f"student-{v}" / "test_report.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _confusion(
    matrix: list[list[int]], labels: list[str], title: str, out: Path
) -> None:
    apply_theme()
    m = np.array(matrix, dtype=float)
    row = m.sum(axis=1, keepdims=True)
    norm = np.divide(m, row, out=np.zeros_like(m), where=row > 0)
    fig, ax = plt.subplots(figsize=(6.2, 5.4))
    im = ax.imshow(norm, cmap="magma", vmin=0, vmax=1)
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=9)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("predicted")
    ax.set_ylabel("true")
    ax.set_title(title)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(
                j,
                i,
                f"{norm[i, j]:.2f}",
                ha="center",
                va="center",
                color="white" if norm[i, j] < 0.6 else "black",
                fontsize=8,
            )
    _ = fig.colorbar(im, ax=ax, fraction=0.046, label="row-normalized")
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def _f1_bars(
    per_class: dict[str, float], order: list[str], title: str, out: Path
) -> None:
    apply_theme()
    vals = [per_class.get(k, 0.0) for k in order]
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    bars = ax.bar(
        range(len(order)), vals, color=[BARS[i % len(BARS)] for i in range(len(order))]
    )
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(order, rotation=25, ha="right", fontsize=9)
    ax.set_ylabel("F1")
    ax.set_ylim(0, 1)
    ax.set_title(title)
    for b, v in zip(bars, vals):
        ax.text(
            b.get_x() + b.get_width() / 2,
            v,
            f"{v:.2f}",
            ha="center",
            va="bottom",
            fontsize=8,
            color=ON_SURFACE,
        )
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def _prompt_growth(out: Path) -> list[tuple[str, int]]:
    apply_theme()
    sizes = [
        (f"v{i}", len((PROMPTS / f"v{i}.txt").read_text(encoding="utf-8")))
        for i in range(1, 7)
        if (PROMPTS / f"v{i}.txt").exists()
    ]
    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    _ = ax.plot(
        [s[0] for s in sizes],
        [s[1] for s in sizes],
        marker="o",
        color=SECONDARY,
        linewidth=2,
    )
    ax.set_ylabel("prompt size (chars)")
    ax.set_title("Teacher prompt evolution (6 triage rounds)")
    ax.grid(True)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return sizes


def tables(rep: dict[str, Any], comp: list[tuple[str, float, float, float]]) -> None:
    f1 = rep["intent_per_class_f1"]
    md = [
        f"Shipped student-{SHIPPED} (held-out test, n={rep['n_test']:,}): "
        f"intent acc **{rep['intent_acc']:.3f}** / macro-F1 **{rep['intent_macro_f1']:.3f}**, "
        f"polarity acc **{rep['polarity_acc']:.3f}**.",
        "",
        "| student | intent acc | intent macro-F1 | polarity acc |",
        "|---|--:|--:|--:|",
    ]
    for v, ia, imf, pa in comp:
        md.append(f"| student-{v} | {ia:.3f} | {imf:.3f} | {pa:.3f} |")
    md += ["", "| intent | F1 |", "|---|--:|"]
    for k in INTENTS:
        md.append(f"| {k} | {f1.get(k, 0):.3f} |")
    _ = (RESULTS / "metrics.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    macros = [
        f"\\newcommand{{\\IntentAcc}}{{{rep['intent_acc']:.3f}}}",
        f"\\newcommand{{\\IntentMacroF}}{{{rep['intent_macro_f1']:.3f}}}",
        f"\\newcommand{{\\PolarityAcc}}{{{rep['polarity_acc']:.3f}}}",
        f"\\newcommand{{\\NTest}}{{{rep['n_test']:,}}}",
    ]
    _ = (RESULTS / "macros.tex").write_text("\n".join(macros) + "\n", encoding="utf-8")

    tab = [
        "\\begin{tabular}{lrrr}",
        "\\toprule",
        "student & intent acc & intent macro-F1 & polarity acc \\\\",
        "\\midrule",
    ]
    for v, ia, imf, pa in comp:
        tab.append(f"student-{v} & {ia:.3f} & {imf:.3f} & {pa:.3f} \\\\")
    tab += ["\\bottomrule", "\\end{tabular}"]
    _ = (RESULTS / "table.tex").write_text("\n".join(tab) + "\n", encoding="utf-8")


def run(use_cache: bool) -> None:
    _ = use_cache  # file reads are instant; flag kept for uniformity
    RESULTS.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    rep = _load(SHIPPED)
    if not rep:
        raise SystemExit(f"no test_report for student-{SHIPPED}")
    _confusion(
        rep["intent_confusion"],
        INTENTS,
        f"Intent confusion (student-{SHIPPED}, held-out test)",
        RESULTS / "intent_confusion.png",
    )
    _confusion(
        rep["polarity_confusion"],
        POLARITIES,
        f"Polarity confusion (student-{SHIPPED})",
        RESULTS / "polarity_confusion.png",
    )
    _f1_bars(
        rep["intent_per_class_f1"],
        INTENTS,
        "Intent per-class F1 (rare relational intents lag)",
        RESULTS / "intent_f1.png",
    )
    _f1_bars(
        rep["polarity_per_class_f1"],
        POLARITIES,
        "Polarity per-class F1",
        RESULTS / "polarity_f1.png",
    )
    sizes = _prompt_growth(RESULTS / "prompt_growth.png")

    versions = [v for v in ("v1", "v2", "v3") if _load(v)]
    comp = [
        (
            v,
            _load(v)["intent_acc"],
            _load(v)["intent_macro_f1"],
            _load(v)["polarity_acc"],
        )
        for v in versions
    ]
    tables(rep, comp)
    summary = {
        "shipped": SHIPPED,
        "n_test": rep["n_test"],
        "intent_acc": rep["intent_acc"],
        "intent_macro_f1": rep["intent_macro_f1"],
        "polarity_acc": rep["polarity_acc"],
        "polarity_macro_f1": rep["polarity_macro_f1"],
        "intent_per_class_f1": rep["intent_per_class_f1"],
        "prompt_sizes": sizes,
    }
    _ = (CACHE / "summary.json").write_text(
        json.dumps(summary, indent=1), encoding="utf-8"
    )
    print(
        f"[02-labeling] student-{SHIPPED} intent macro-F1 {rep['intent_macro_f1']:.3f}; "
        f"wrote 5 figures + tables",
        flush=True,
    )
