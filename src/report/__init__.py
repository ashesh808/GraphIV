"""
The document a researcher reads, and the three things it is assembled out of

The prose belongs to whoever called this, and everything else here is evidence they can check
"""

from src.report.fulltext import FullText, read_paper
from src.report.ground import Grounded, check, linkify
from src.report.render import Draft, Section, document
from src.report.table import Design, Method, design, extract, merge, repair

__all__ = [
    "Design",
    "Draft",
    "FullText",
    "Grounded",
    "Method",
    "Section",
    "check",
    "design",
    "document",
    "extract",
    "linkify",
    "merge",
    "read_paper",
    "repair",
]
