"""Data model and input validation for keyword overlap detection."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple

EXACT = "exact"
PHRASE = "phrase"
BROAD = "broad"
OTHER = "OTHER"

MATCH_TYPES = (EXACT, PHRASE, BROAD)
NEGATIVE_MATCH_TYPES = (EXACT, PHRASE)


@dataclass(frozen=True)
class Keyword:
    match_type: str
    tokens: Tuple[str, ...]


@dataclass(frozen=True)
class AdGroup:
    positive: Keyword
    negatives: Tuple[Keyword, ...] = ()


def as_keyword(value: Any) -> Keyword:
    """Normalize a Keyword / dict / (match_type, tokens) pair into a Keyword."""
    if isinstance(value, Keyword):
        return value
    if isinstance(value, dict):
        return Keyword(value["match_type"], tuple(value["tokens"]))
    match_type, tokens = value
    return Keyword(match_type, tuple(tokens))


def as_ad_group(value: Any) -> AdGroup:
    """Normalize an AdGroup / dict into an AdGroup."""
    if isinstance(value, AdGroup):
        return value
    if isinstance(value, dict):
        return AdGroup(
            positive=as_keyword(value["positive"]),
            negatives=tuple(as_keyword(k) for k in value.get("negatives", ())),
        )
    positive, negatives = value
    return AdGroup(as_keyword(positive), tuple(as_keyword(k) for k in negatives))


def validate_keyword(keyword: Keyword, *, allow_broad: bool) -> None:
    """Raise ValueError if the keyword is malformed."""
    allowed = MATCH_TYPES if allow_broad else NEGATIVE_MATCH_TYPES
    if keyword.match_type not in allowed:
        raise ValueError(
            "unsupported match_type %r (allowed: %s)"
            % (keyword.match_type, ", ".join(allowed))
        )
    if not keyword.tokens:
        raise ValueError("keyword tokens must be a non-empty sequence")
    for token in keyword.tokens:
        if not isinstance(token, str) or not token:
            raise ValueError("keyword tokens must be non-empty strings")
        if token == OTHER:
            raise ValueError("%r is reserved and must not appear in configs" % OTHER)
