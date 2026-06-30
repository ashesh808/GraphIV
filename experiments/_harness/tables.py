"""Shared writers for experiment result artifacts — DRYs the per-experiment metrics.md / booktabs
table.tex / macros.tex generation that was copy-pasted across the suite."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _esc(s: object) -> str:
    return str(s).replace("_", r"\_")


def metrics_md(rows: list[dict[str, Any]], cols: list[str], caption: str = "") -> str:
    """Markdown table (one dict per row, `cols` as the column keys) + optional italic caption."""
    out = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join("---" for _ in cols) + " |",
    ]
    for r in rows:
        out.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    if caption:
        out.append("\n_" + caption + "_")
    return "\n".join(out) + "\n"


def booktabs(rows: list[dict[str, Any]], cols: list[tuple[str, str]]) -> str:
    """LaTeX booktabs tabular. `cols` is [(row_key, header)]; col 0 is the label (value escaped)."""
    lines = [
        "\\begin{tabular}{" + "l" + "r" * (len(cols) - 1) + "}",
        "\\toprule",
        " & ".join(_esc(h) for _, h in cols) + " \\\\",
        "\\midrule",
    ]
    for r in rows:
        cells = [_esc(r[cols[0][0]])] + [str(r[k]) for k, _ in cols[1:]]
        lines.append(" & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    return "\n".join(lines) + "\n"


def macros(pairs: list[tuple[str, object]]) -> str:
    """`\\newcommand{\\name}{value}` lines (name must be letters-only for a valid control sequence)."""
    return "\n".join(f"\\newcommand{{\\{n}}}{{{v}}}" for n, v in pairs) + "\n"


def write(
    results_dir: Path,
    rows: list[dict[str, Any]],
    md_cols: list[str],
    tex_cols: list[tuple[str, str]],
    *,
    macro_pairs: list[tuple[str, object]] | None = None,
    caption: str = "",
) -> None:
    """Write metrics.md + table.tex (+ macros.tex if given) for an experiment's report."""
    _ = (results_dir / "metrics.md").write_text(
        metrics_md(rows, md_cols, caption), encoding="utf-8"
    )
    _ = (results_dir / "table.tex").write_text(
        booktabs(rows, tex_cols), encoding="utf-8"
    )
    if macro_pairs is not None:
        _ = (results_dir / "macros.tex").write_text(
            macros(macro_pairs), encoding="utf-8"
        )
