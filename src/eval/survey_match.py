"""
Given one review, find the papers it cited

Every resolved reference counts, so two thirds of a key is one author's own selection
The report carries the agreed subset beside the headline for that reason
"""

from __future__ import annotations

from src.eval.match import Match


class SurveyMatch(Match):
    """
    One review per sample, scored against its own bibliography
    """

    name: str = "SurveyMatch"
    headline: str = "1000"
