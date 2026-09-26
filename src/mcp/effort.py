"""
Three presets, since the caller decides how hard to push and every cap here is what that costs

The floor is already a document and the two above it buy reading, which is where the time goes
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Effort:
    """
    What one preset turns on, which is also what it costs
    """

    name: str
    budget: str
    areas: int = 3
    read: int = 200
    keep: int = 40
    magnets: int = 20
    lineages: int = 5
    disputes: int = 20
    successors: int = 25
    full_text: int = 0
    compose: bool = True
    retrieves: int = 6


LEVELS = {
    "quick": Effort(
        "quick", "about a minute", areas=2, read=60, keep=15, full_text=0, compose=False
    ),
    "standard": Effort("standard", "two to four minutes", areas=3, read=200, keep=40, full_text=12),
    "deep": Effort(
        "deep",
        "as long as the caller keeps going",
        areas=4,
        read=400,
        keep=60,
        magnets=30,
        lineages=10,
        disputes=40,
        successors=50,
        full_text=30,
        retrieves=12,
    ),
}


def level(name: str) -> Effort:
    """
    One preset by name

    Args:
        name: quick, standard or deep.

    Returns:
        The preset, falling back to standard for a name nothing defines.
    """
    return LEVELS.get(name.strip().lower(), LEVELS["standard"])
