"""Cross-ad-group keyword overlap detection.

Determines whether two ad groups can both accept a common search term and
produces the shortest concrete witness term for auditing.
"""
from .model import (
    BROAD,
    EXACT,
    OTHER,
    PHRASE,
    AdGroup,
    Keyword,
    as_ad_group,
    as_keyword,
)
from .search import find_overlap

__all__ = [
    "BROAD",
    "EXACT",
    "OTHER",
    "PHRASE",
    "AdGroup",
    "Keyword",
    "as_ad_group",
    "as_keyword",
    "find_overlap",
]
