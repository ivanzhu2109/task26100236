"""Breadth-first search for the shortest jointly accepted search term."""
from __future__ import annotations

from collections import deque
from typing import Any, Optional, Sequence, Tuple

from .automaton import GroupAutomaton
from .model import OTHER, as_ad_group, as_keyword, validate_keyword


def _alphabet(*groups_and_negatives: Any) -> Tuple[str, ...]:
    tokens = set()
    for item in groups_and_negatives:
        tokens.update(item.tokens)
    return tuple(sorted(tokens)) + (OTHER,)


def find_overlap(
    left: Any,
    right: Any,
    account_negatives: Sequence[Any] = (),
) -> Optional[Tuple[str, ...]]:
    """Return the shortest, then lexicographically smallest, search term
    accepted by both ad groups, or None if no such term exists.

    The witness is a tuple of tokens drawn from every token appearing in the
    input plus the reserved token OTHER (any word absent from the configs),
    which sorts after all ordinary tokens.
    """
    left_group = as_ad_group(left)
    right_group = as_ad_group(right)
    negatives = tuple(as_keyword(k) for k in account_negatives)

    validate_keyword(left_group.positive, allow_broad=True)
    validate_keyword(right_group.positive, allow_broad=True)
    for keyword in left_group.negatives + right_group.negatives + negatives:
        validate_keyword(keyword, allow_broad=False)

    left_auto = GroupAutomaton(left_group, negatives)
    right_auto = GroupAutomaton(right_group, negatives)
    alphabet = _alphabet(
        left_group.positive,
        right_group.positive,
        *left_group.negatives,
        *right_group.negatives,
        *negatives,
    )

    initial = (left_auto.initial_state(), right_auto.initial_state())
    visited = {initial}
    queue = deque(((initial, ()),))
    while queue:
        (left_state, right_state), path = queue.popleft()
        for token in alphabet:
            next_left = left_auto.step(left_state, token)
            if next_left is None:
                continue
            next_right = right_auto.step(right_state, token)
            if next_right is None:
                continue
            combined = (next_left, next_right)
            if combined in visited:
                continue
            visited.add(combined)
            candidate = path + (token,)
            if left_auto.is_accepting(next_left) and right_auto.is_accepting(next_right):
                return candidate
            queue.append((combined, candidate))
    return None
