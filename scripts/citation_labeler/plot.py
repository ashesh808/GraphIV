"""
The project plot theme, read from theme.json at the repo root

Dark is the default, since the figures land in dark-surfaced reports
Agg is selected on import because every caller writes a file rather than opening a window
"""

from __future__ import annotations

import glob
import json
import os
from pathlib import Path
from typing import Any, cast

import matplotlib

matplotlib.use("Agg")
from matplotlib import font_manager  # noqa: E402
from matplotlib import pyplot as plt  # noqa: E402

THEME_PATH = Path(__file__).resolve().parents[2] / "theme.json"
FONT_NAME = "Google Sans Flex"


def palette(mode: str = "dark") -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
    """
    One half of theme.json

    Args:
        mode: either `dark` or `light`.

    Returns:
        The color table for that mode.
    """
    raw = cast(
        "dict[str, Any]",  # pyright: ignore[reportExplicitAny]
        json.loads(THEME_PATH.read_text(encoding="utf-8")),
    )
    return cast("dict[str, Any]", raw[mode])  # pyright: ignore[reportExplicitAny]


def _font() -> str:
    """
    Register the project font if its file is findable

    Returns:
        The family name matplotlib should use.
    """
    found = [
        os.path.expanduser("~/.local/share/fonts/GoogleSansFlex-VariableFont.ttf"),
        *glob.glob(
            os.path.expanduser("~/.local/share/fonts/**/GoogleSansFlex*.ttf"), recursive=True
        ),
        *glob.glob("/nix/store/*google-fonts*/share/fonts/**/GoogleSansFlex*.ttf", recursive=True),
    ]
    for path in found:
        if os.path.exists(path):
            font_manager.fontManager.addfont(path)
            return FONT_NAME
    return "DejaVu Sans"


def apply_theme(mode: str = "dark") -> None:
    """
    Push the palette into matplotlib rcParams, which is idempotent

    Args:
        mode: either `dark` or `light`.
    """
    t = palette(mode)
    plt.rcParams.update(
        {
            "font.family": _font(),
            "figure.facecolor": t["mSurface"],
            "savefig.facecolor": t["mSurface"],
            "axes.facecolor": t["mSurface"],
            "axes.edgecolor": t["mOutline"],
            "axes.labelcolor": t["mOnSurface"],
            "axes.titlecolor": t["mOnSurface"],
            "text.color": t["mOnSurface"],
            "xtick.color": t["mOnSurface"],
            "ytick.color": t["mOnSurface"],
            "grid.color": t["mOutline"],
            "grid.alpha": 0.3,
            "legend.facecolor": t["mSurfaceVariant"],
            "legend.edgecolor": t["mOutline"],
            "legend.labelcolor": t["mOnSurface"],
        }
    )


def series(mode: str = "dark") -> list[str]:
    """
    The categorical colors, ordered for contrast between neighbors

    Args:
        mode: either `dark` or `light`.

    Returns:
        One hex color per series.
    """
    t = palette(mode)
    term = cast("dict[str, str]", t["terminal"]["normal"])
    return [
        cast(str, t["mSecondary"]),
        cast(str, t["mTertiary"]),
        cast(str, t["mPrimary"]),
        term["yellow"],
        term["blue"],
        term["cyan"],
        cast(str, t["mOnSurfaceVariant"]),
    ]
