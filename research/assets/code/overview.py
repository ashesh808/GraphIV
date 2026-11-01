"""
The overview BoundedField's and LeyLine's figures open on: the steps, the formulas, a toy graph

Every piece is placed in inches from the page's top left, like the rest of a card
"""

from __future__ import annotations

from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch
from style import INK, MUTED, OUTLINE, Page, tint

# a toy graph paper's radius, in inches
NODE = 0.16
# the light rule parting a table's rows and columns
RULE = tint(OUTLINE, 0.55)
# a table's header height and the room between a cell's edge and its text
HEADER, PAD = 0.32, 0.1
# one term of a table: its name, its formula and its description
TERM = tuple[str, str, str]


def steps(page: Page, top: float, boxes: list[tuple[str, str]], hue: str) -> float:
    """
    The method as a row of boxes left to right, each its name over one line of what it does

    Args:
        page: The page.
        top: Top edge.
        boxes: Each step's name and its line.
        hue: The component's color.

    Returns:
        The row's bottom edge.
    """
    gap, high = 0.45, 0.68
    width = (page.right - 0.5 - gap * (len(boxes) - 1)) / len(boxes)
    for i, (name, line) in enumerate(boxes):
        x = 0.5 + i * (width + gap)
        page.ax.add_patch(
            FancyBboxPatch(
                (x, top),
                width,
                high,
                boxstyle="round,pad=0,rounding_size=0.08",
                facecolor=tint(hue, 0.1),
                edgecolor=hue,
                linewidth=1.3,
                zorder=3,
            )
        )
        middle = x + width / 2
        page.ax.text(
            middle, top + 0.29, name, ha="center", fontsize=12, fontweight="semibold", zorder=4
        )
        page.ax.text(middle, top + 0.53, line, ha="center", fontsize=10, color=MUTED, zorder=4)
        if i:
            page.arrow((x - gap + 0.06, top + high / 2), (x - 0.06, top + high / 2))
    return top + high


def rule(page: Page, left: float, right: float, y: float, heavy: bool = False) -> None:
    """
    A horizontal rule across a table, heavier where it bounds the table or its header

    Args:
        page: The page.
        left: Left end.
        right: Right end.
        y: Its height.
        heavy: Whether it bounds the table or its header rather than parting two rows.
    """
    page.ax.plot(
        [left, right],
        [y, y],
        color=OUTLINE if heavy else RULE,
        linewidth=1.0 if heavy else 0.6,
        solid_capstyle="butt",
        zorder=2,
    )


def divide(page: Page, x: float, top: float, bottom: float) -> None:
    """
    A vertical rule between two columns of a table

    Args:
        page: The page.
        x: Where it sits.
        top: Top end.
        bottom: Bottom end.
    """
    page.ax.plot([x, x], [top, bottom], color=RULE, linewidth=0.6, solid_capstyle="butt", zorder=2)


def grid(
    page: Page,
    span: tuple[float, float],
    edges: tuple[float, float, float],
    rows: list[float],
    columns: list[float],
) -> None:
    """
    The rules of a table drawn by hand: its bounds, its header, its rows and its columns

    Args:
        page: The page.
        span: Its left and right ends.
        edges: Its top, the bottom of its header and its bottom.
        rows: Where one row ends and the next begins.
        columns: Where one column ends and the next begins.
    """
    left, right = span
    top, header, bottom = edges
    for y, heavy in ((top, True), (header, True), (bottom, True), *((y, False) for y in rows)):
        rule(page, left, right, y, heavy)
    for x in columns:
        divide(page, x, top, bottom)


def terms(
    page: Page, x: float, top: float, widths: tuple[float, float, float], rows: list[TERM]
) -> float:
    """
    A ruled table of terms: the name, the formula centered in its column, and what it computes

    Args:
        page: The page.
        x: Left edge.
        top: Top edge.
        widths: The three columns' widths.
        rows: Each term's name, its formula in mathtext and its description.

    Returns:
        The table's bottom edge.
    """
    renderer = page.fig.canvas.get_renderer()  # pyright: ignore[reportAttributeAccessIssue]
    edges = (x, x + widths[0], x + widths[0] + widths[1], x + sum(widths))
    middle = (edges[1] + edges[2]) / 2
    for k, head in enumerate(("Term", "Formula", "Description")):
        page.ax.text(
            middle if k == 1 else edges[k] + PAD,
            top + HEADER / 2,
            head,
            fontsize=10.5,
            fontweight="semibold",
            ha="center" if k == 1 else "left",
            va="center",
        )
    y, parts = top + HEADER, []
    for name, formula, description in rows:
        lines = page.wrapped(description, widths[2] - 2 * PAD, 10)
        probe = page.ax.text(0, 0, formula, fontsize=12.5)
        tall = probe.get_window_extent(renderer).height / page.fig.dpi
        probe.remove()
        high = max(0.19 * len(lines), tall, 0.2) + 0.16
        center = y + high / 2
        page.ax.text(
            edges[0] + PAD, center, name, fontsize=10.5, fontweight="semibold", va="center"
        )
        page.ax.text(middle, center, formula, fontsize=12.5, ha="center", va="center")
        for j, line in enumerate(lines):
            offset = 0.19 * (j - (len(lines) - 1) / 2)
            page.ax.text(
                edges[2] + PAD, center + offset, line, fontsize=10, color=MUTED, va="center"
            )
        y += high
        parts.append(y)
    grid(page, (x, edges[-1]), (top, top + HEADER, y), parts[:-1], list(edges[1:-1]))
    return y


def meanings(page: Page, top: float, lead: str, lines: list[str], hue: str) -> float:
    """
    One sentence leading into numbered consequences, laid side by side between vertical rules

    Args:
        page: The page.
        top: The lead's baseline.
        lead: The sentence the consequences follow from.
        lines: The consequences.
        hue: The color of their numbers.

    Returns:
        The last line's baseline.
    """
    page.ax.text(0.5, top, lead, fontsize=11, fontweight="medium", va="baseline")
    gap = 0.4
    width = (page.right - 0.5 - gap * (len(lines) - 1)) / len(lines)
    bottom = top
    for i, line in enumerate(lines):
        x = 0.5 + i * (width + gap)
        page.ax.text(
            x, top + 0.38, str(i + 1), fontsize=10.5, color=hue, fontweight="bold", va="baseline"
        )
        for j, piece in enumerate(page.wrapped(line, width - 0.25, 10.5)):
            y = top + 0.38 + 0.21 * j
            page.ax.text(x + 0.22, y, piece, fontsize=10.5, color=MUTED, va="baseline")
            bottom = max(bottom, y)
    for i in range(1, len(lines)):
        divide(page, 0.5 + i * (width + gap) - gap / 2, top + 0.17, bottom + 0.08)
    return bottom


def node(
    page: Page,
    xy: tuple[float, float],
    fill: str,
    edge: str,
    radius: float = NODE,
    dashed: bool = False,
) -> None:
    """
    One paper of a toy graph

    Args:
        page: The page.
        xy: Its center.
        fill: Its fill.
        edge: Its outline.
        radius: Its radius.
        dashed: Whether the outline is dashed, for a paper outside the graph.
    """
    page.ax.add_patch(
        Circle(
            xy,
            radius,
            facecolor=fill,
            edgecolor=edge,
            linewidth=1.4,
            linestyle=(0, (2.5, 2)) if dashed else "-",
            zorder=5,
        )
    )


def cite(
    page: Page,
    citing: tuple[float, float],
    cited: tuple[float, float],
    color: str = MUTED,
    radii: tuple[float, float] = (NODE, NODE),
    bend: float = 0.0,
    dashed: bool = False,
) -> None:
    """
    One citation of a toy graph, an arrow from the citing paper to the paper it cites

    Args:
        page: The page.
        citing: The citing paper's center.
        cited: The cited paper's center.
        color: The arrow's color.
        radii: Both papers' radii, so the arrow meets their edges.
        bend: Its curvature, 0 for a straight arrow.
        dashed: Whether it is dashed.
    """
    page.ax.add_patch(
        FancyArrowPatch(
            citing,
            cited,
            arrowstyle="-|>",
            mutation_scale=11,
            color=color,
            linewidth=1.4,
            linestyle=(0, (3, 2)) if dashed else "-",
            connectionstyle=f"arc3,rad={bend}",
            shrinkA=radii[0] * 72 + 1,
            shrinkB=radii[1] * 72 + 1,
            zorder=4,
        )
    )


def timeline(page: Page, left: float, right: float, y: float) -> None:
    """
    The axis under a toy graph, older to the left and newer to the right

    Args:
        page: The page.
        left: Its left end.
        right: Its right end.
        y: Its height.
    """
    page.ax.add_patch(
        FancyArrowPatch(
            (left, y),
            (right, y),
            arrowstyle="-|>",
            mutation_scale=11,
            color=OUTLINE,
            linewidth=1.2,
            zorder=2,
        )
    )
    page.ax.text(left, y + 0.25, "older", fontsize=10, color=MUTED, va="baseline")
    page.ax.text(right, y + 0.25, "newer", fontsize=10, color=MUTED, ha="right", va="baseline")


def label(page: Page, xy: tuple[float, float], text: str, below: bool = True) -> None:
    """
    A toy graph paper's term, centered under it or over it

    Args:
        page: The page.
        xy: The paper's center.
        text: What it is.
        below: Whether the label sits under the paper rather than over it.
    """
    y = xy[1] + 0.38 if below else xy[1] - 0.25
    page.ax.text(xy[0], y, text, fontsize=10.5, ha="center", va="baseline", color=INK, zorder=6)
