"""
Given a topic, find the papers every review of it cites

A key of eight saturates a thousand slots, so the headline budget is a hundred
"""

from __future__ import annotations

from src.eval.match import Match


class ConsensusMatch(Match):
    """
    Three reviews of one leaf written inside one span, scored on what all three cite
    """

    name: str = "ConsensusMatch"
    headline: str = "100"
