"""
The global plot theme, read from the project palette

Call apply_theme once before plotting, then use the exported color names
Dark is the default because the figures land in dark-surfaced reports
"""

from __future__ import annotations

import glob
import json
import os
from pathlib import Path
from typing import Any, cast

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

_THEME_JSON = Path(__file__).resolve().parents[2] / "theme.json"


def _theme(mode: str) -> dict[str, Any]:
    raw = cast(
        "dict[str, Any]",  # pyright: ignore[reportExplicitAny]
        json.loads(_THEME_JSON.read_text(encoding="utf-8")),
    )
    return cast("dict[str, Any]", raw[mode])  # pyright: ignore[reportExplicitAny]


_T = _theme("dark")
SURFACE: str = _T["mSurface"]
ON_SURFACE: str = _T["mOnSurface"]
SURFACE_VARIANT: str = _T["mSurfaceVariant"]
OUTLINE: str = _T["mOutline"]
PRIMARY: str = _T["mPrimary"]
SECONDARY: str = _T["mSecondary"]
TERTIARY: str = _T["mTertiary"]
_TERM: dict[str, str] = _T["terminal"]["normal"]
# series palette: Material accents + a few terminal hues, ordered for contrast
BARS: list[str] = [
    SECONDARY,
    TERTIARY,
    PRIMARY,
    _TERM["yellow"],
    _TERM["blue"],
    _TERM["cyan"],
    _T["mOnSurfaceVariant"],
]

_FONT_NAME = "Google Sans Flex"


def _register_font() -> str:
    """
    Register Google Sans Flex if its ttf is findable; return the usable family name
    """
    cands = [
        os.path.expanduser("~/.local/share/fonts/GoogleSansFlex-VariableFont.ttf"),
        *glob.glob(
            os.path.expanduser("~/.local/share/fonts/**/GoogleSansFlex*.ttf"),
            recursive=True,
        ),
        *glob.glob(
            "/nix/store/*google-fonts*/share/fonts/**/GoogleSansFlex*.ttf",
            recursive=True,
        ),
    ]
    for p in cands:
        if os.path.exists(p):
            font_manager.fontManager.addfont(p)
            return _FONT_NAME
    return "DejaVu Sans"


def apply_theme(mode: str = "dark") -> None:
    """
    Apply the global Material theme + Google Sans Flex to matplotlib rcParams (idempotent)
    """
    t = _theme(mode)
    fam = _register_font()
    plt.rcParams.update(
        {
            "font.family": fam,
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
