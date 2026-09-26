"""
Writes the run directory a benchmark leaves behind, and the figure that compares its recipes

One directory per recipe holds the settings that produced it, so a directory replays on its own
The figure sits above them, since comparing the recipes is what it is for
"""

from __future__ import annotations

import json
import logging
import statistics as stats
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from src.eval.match import Score

LOG = logging.getLogger(__name__)

# titles carry arbitrary latex, and matplotlib reads a dollar sign as the start of mathtext
plt.rcParams["text.parse_math"] = False


def write_run(
    out: Path, recipe: dict[str, Any], settings: dict[str, Any], scores: list[Score]
) -> None:
    """
    Writes one recipe's directory, the settings beside the scores that came out of them

    Args:
        out: The recipe directory.
        recipe: The parsed recipe file.
        settings: The benchmark settings this run used.
        scores: One score per sample.
    """
    out.mkdir(parents=True, exist_ok=True)
    lines = [
        "# The run that produced scores.jsonl, written back so this directory replays alone",
        "",
        _as_toml({"benchmark": settings}),
        "",
        "# The recipe, copied verbatim from retrieval_recipes",
        "",
        _as_toml(recipe),
    ]
    _ = (out / "config.toml").write_text("\n".join(lines), encoding="utf-8")
    with (out / "scores.jsonl").open("w", encoding="utf-8") as handle:
        for score in scores:
            _ = handle.write(json.dumps(score.as_row()) + "\n")
    LOG.info("wrote %d scores to %s", len(scores), out)


def _as_toml(data: dict[str, Any], prefix: str = "") -> str:
    """
    A nested dict as toml, which is enough for what a run writes back

    Args:
        data: The values.
        prefix: The table this dict sits under.

    Returns:
        The toml text.
    """
    scalars: list[str] = []
    tables: list[str] = []
    for key, value in data.items():
        if isinstance(value, dict):
            tables.append(f"[{prefix}{key}]\n" + _as_toml(dict(value), f"{prefix}{key}."))
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            for item in value:  # pyright: ignore[reportUnknownVariableType]
                tables.append(
                    f"[[{prefix}{key}]]\n" + _as_toml(dict(item), "")
                )  # pyright: ignore[reportUnknownArgumentType]
        else:
            scalars.append(f"{key} = {json.dumps(value)}")
    return "\n".join(scalars + [""] + tables).strip() + "\n"


def plot_comparison(
    path: Path, metric: str, budget: str, by_recipe: dict[str, list[Score]]
) -> None:
    """
    One horizontal box per recipe over the per-sample scores

    Args:
        path: Where to write the figure.
        metric: The benchmark name, which titles the figure.
        budget: Which budget the headline reports.
        by_recipe: One list of scores per recipe, in the order they should be drawn.
    """
    names = list(by_recipe)
    values = [[s.recall.get(budget, 0.0) for s in by_recipe[n]] for n in names]
    best = max(range(len(names)), key=lambda i: stats.mean(values[i]) if values[i] else 0.0)
    mean = stats.mean(values[best]) if values[best] else 0.0
    spread = stats.pstdev(values[best]) if len(values[best]) > 1 else 0.0
    cases = len(values[best])

    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    figure, axis = plt.subplots(figsize=(9, 1.1 + 0.7 * len(names)))
    boxes = axis.boxplot(values[::-1], vert=False, widths=0.6, patch_artist=True, showfliers=False)
    for i, patch in enumerate(boxes["boxes"]):
        patch.set_facecolor(colors[(len(names) - 1 - i) % len(colors)])
        patch.set_alpha(0.55)
    for whisker in boxes["medians"]:
        whisker.set_color("black")

    labels = [
        f"{name}\n{stats.mean(row) if row else 0.0:.3f}"
        for name, row in zip(names, values, strict=True)
    ]
    axis.set_yticklabels(labels[::-1])
    axis.set_xlabel(
        f"recall at {budget}" if metric != "PrecisionMatch" else f"on topic share at {budget}"
    )
    axis.set_xlim(0, 1)
    axis.set_title(f"{metric} score ({cases} cases): {mean:.3f} ± {spread:.3f}")
    axis.grid(axis="x", alpha=0.3)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
    LOG.info("wrote %s", path)
