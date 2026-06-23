"""Grouped bar charts for ablation results (ported from kg_rag_lab/viz_eval.py).

One subplot per metric, one bar per condition. Uses the global theme (theme.json Material palette +
Google Sans Flex). Saves a single PNG.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .theme import BARS as _BARS  # noqa: E402
from .theme import ON_SURFACE as _ON  # noqa: E402
from .theme import OUTLINE as _OUTLINE  # noqa: E402
from .theme import SURFACE as _SURFACE  # noqa: E402
from .theme import apply_theme  # noqa: E402


def bar_chart(
    rows: list[dict[str, Any]],
    label_key: str,
    metrics: list[tuple[str, str]],
    out_path: Path,
    title: str = "",
) -> None:
    """rows: per-condition metric dicts. metrics: list of (key, human_label) to plot."""
    apply_theme()
    labels = [str(r.get(label_key, i)) for i, r in enumerate(rows)]
    n = len(metrics)
    cols = min(2, n)
    rows_n = (n + cols - 1) // cols
    fig, axes = plt.subplots(
        rows_n, cols, figsize=(6.5 * cols, 4.0 * rows_n), facecolor=_SURFACE
    )
    axlist = (
        list(axes.flat) if hasattr(axes, "flat") else [axes]
    )  # pyright: ignore[reportAttributeAccessIssue]
    for ax, (key, human) in zip(axlist, metrics):
        vals = [float(r.get(key) or 0) for r in rows]
        bars = ax.bar(
            range(len(vals)), vals, color=_BARS[: len(vals)]
        )  # pyright: ignore[reportAny]
        ax.set_title(human, color=_ON, fontsize=11)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, color=_ON, fontsize=8, rotation=20, ha="right")
        ax.set_facecolor(_SURFACE)
        ax.tick_params(colors=_ON)
        for s in ax.spines.values():
            s.set_color(_OUTLINE)
        for b, v in zip(bars, vals):  # pyright: ignore[reportAny]
            ax.text(
                b.get_x() + b.get_width() / 2,
                v,
                f"{v:g}",
                ha="center",
                va="bottom",
                color=_ON,
                fontsize=8,
            )
    for ax in axlist[n:]:
        ax.axis("off")
    if title:
        _ = fig.suptitle(title, color=_ON, fontsize=13)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130, facecolor=_SURFACE)
    plt.close(fig)
