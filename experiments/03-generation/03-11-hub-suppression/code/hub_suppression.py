"""experiment 03-11 — hub suppression: stop generic globally-cited papers (Attention/BERT/Adam) from
dominating niche reviews. Regenerates the results table + figure from the committed sweep/oracle JSONs.

The heavy compute lives in two reference scripts (run them to reproduce structural.json / oracle.json):
  code/hub_sweep.py   — re-rank the pool under each data-derived signal; gold-recall + bg over 27 topics.
  code/hub_oracle.py  — an independent topic-conditioned specific/generic LLM judge (the ground truth).

    uv run python experiments/03-generation/03-11-hub-suppression/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]
sys.path.insert(0, str(_HERE.parents[3]))  # experiments/ (for _harness)

from _harness.viz import bar_chart  # noqa: E402

RESULTS = _EXP / "results"
ARMS = ("none", "lift", "pr_ratio", "pop_bg3", "pop_bg5", "pop_bg7", "pop_bg10")


def run(_use_cache: bool = True) -> None:
    struct_rows: list[dict[str, Any]] = json.loads(
        (RESULTS / "structural.json").read_text()
    )["rows"]
    orac_rows: list[dict[str, Any]] = json.loads((RESULTS / "oracle.json").read_text())
    struct = {r["arm"]: r for r in struct_rows}
    orac = {r["arm"]: r for r in orac_rows}
    rows = [
        {
            "arm": a,
            "gold_recall": struct[a]["gold_recall"],
            "generic_frac": orac[a]["generic_frac"],
            "specific_retained": orac[a]["specific_retained"],
            "bg_mean": struct[a]["bg_mean"],
        }
        for a in ARMS
    ]
    cols = ["arm", "gold_recall", "generic_frac", "specific_retained", "bg_mean"]
    md = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for r in rows:
        md.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    md.append(
        "\n_gold_recall must HOLD (tripwire); generic_frac DOWN + specific_retained UP per the "
        "independent oracle. pop_bg holds recall (s<=0.7) but is gentle; topic-blind pr_ratio moves "
        "the oracle most but costs recall -- no structural silver bullet, so the shipped fix is the "
        "compose guard (see report)._"
    )
    _ = (RESULTS / "metrics.md").write_text("\n".join(md) + "\n")
    bar_chart(
        rows,
        "arm",
        [
            ("gold_recall", "gold recall (hold)"),
            ("generic_frac", "oracle generic-frac (down)"),
            ("specific_retained", "oracle specific-retained (up)"),
        ],
        RESULTS / "ablation.png",
        title="Hub-suppression signal sweep -- recall vs oracle-specificity frontier (27 topics)",
    )
    show = [
        ("gold_recall", "gold rec."),
        ("generic_frac", "generic"),
        ("specific_retained", "specific ret."),
        ("bg_mean", "bg"),
    ]
    lines = [
        "\\begin{tabular}{lrrrr}",
        "\\toprule",
        "arm & " + " & ".join(c[1] for c in show) + " \\\\",
        "\\midrule",
    ]
    for r in rows:
        lines.append(
            r["arm"].replace("_", r"\_")
            + " & "
            + " & ".join(str(r[c[0]]) for c in show)
            + " \\\\"
        )
    lines += ["\\bottomrule", "\\end{tabular}"]
    _ = (RESULTS / "table.tex").write_text("\n".join(lines) + "\n")
    n, pb = struct["none"], struct["pop_bg7"]
    on, opb, opr = orac["none"], orac["pop_bg7"], orac["pr_ratio"]
    macros = [
        f"\\newcommand{{\\noneRecall}}{{{n['gold_recall']}}}",
        f"\\newcommand{{\\popRecall}}{{{pb['gold_recall']}}}",
        f"\\newcommand{{\\noneGeneric}}{{{on['generic_frac']}}}",
        f"\\newcommand{{\\popGeneric}}{{{opb['generic_frac']}}}",
        f"\\newcommand{{\\prGeneric}}{{{opr['generic_frac']}}}",
        f"\\newcommand{{\\prRecall}}{{{struct['pr_ratio']['gold_recall']}}}",
    ]
    _ = (RESULTS / "macros.tex").write_text("\n".join(macros) + "\n")
    print("\n".join(md), flush=True)


if __name__ == "__main__":
    run()
