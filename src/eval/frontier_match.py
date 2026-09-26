"""
Given a topic as one review left it, find what the next review on it added

The cap is the later review's date, so every answer exists and the question is whether it ranks
"""

from __future__ import annotations

from src.eval.match import Match


class FrontierMatch(Match):
    """
    Two reviews of one leaf written months apart, scored on what the later one added
    """

    name: str = "FrontierMatch"
    headline: str = "1000"
