"""Per-ad-group acceptance automaton over search-term token sequences."""
from __future__ import annotations

from typing import Hashable, List, Optional, Sequence, Tuple

from .model import BROAD, EXACT, PHRASE, AdGroup, Keyword


def _kmp_table(pattern: Tuple[str, ...]) -> List[int]:
    table = [0] * len(pattern)
    matched = 0
    for i in range(1, len(pattern)):
        while matched and pattern[i] != pattern[matched]:
            matched = table[matched - 1]
        if pattern[i] == pattern[matched]:
            matched += 1
        table[i] = matched
    return table


def _kmp_step(pattern: Tuple[str, ...], table: List[int], state: int, token: str) -> int:
    while state and token != pattern[state]:
        state = table[state - 1]
    if token == pattern[state]:
        state += 1
    return state


class GroupAutomaton:
    """Tracks whether the token sequence consumed so far is accepted by one group.

    A group accepts a search term iff the term matches the group's positive
    keyword and matches none of the group-level or account-level negatives.

    State layout: (positive_state, (neg_state, ...)) where
      - exact positive / exact negative: matched prefix length, or None once
        the sequence can never equal the configured token list again;
      - phrase positive: (found: bool, kmp length); phrase negative: kmp length
        (reaching the pattern length kills the whole path);
      - broad positive: frozenset of configured tokens seen so far.
    """

    def __init__(self, group: AdGroup, account_negatives: Sequence[Keyword]) -> None:
        positive = group.positive
        self._pos_kind = positive.match_type
        self._pos_tokens = positive.tokens
        self._pos_table = (
            _kmp_table(positive.tokens) if positive.match_type == PHRASE else None
        )
        self._pos_needed = (
            frozenset(positive.tokens) if positive.match_type == BROAD else None
        )
        self._negatives: List[Tuple[str, Tuple[str, ...], Optional[List[int]]]] = []
        for keyword in tuple(group.negatives) + tuple(account_negatives):
            table = _kmp_table(keyword.tokens) if keyword.match_type == PHRASE else None
            self._negatives.append((keyword.match_type, keyword.tokens, table))

    def initial_state(self) -> Hashable:
        if self._pos_kind == EXACT:
            pos_state: Hashable = 0
        elif self._pos_kind == PHRASE:
            pos_state = (False, 0)
        else:
            pos_state = frozenset()
        return (pos_state, tuple(0 for _ in self._negatives))

    def step(self, state: Hashable, token: str) -> Optional[Hashable]:
        """Advance the automaton by one token; None means the path is dead."""
        pos_state, neg_states = state

        if self._pos_kind == EXACT:
            if pos_state is None:
                return None
            if pos_state < len(self._pos_tokens) and token == self._pos_tokens[pos_state]:
                pos_state += 1
            else:
                return None
        elif self._pos_kind == PHRASE:
            found, kmp_len = pos_state
            if not found:
                kmp_len = _kmp_step(self._pos_tokens, self._pos_table, kmp_len, token)
                if kmp_len == len(self._pos_tokens):
                    found, kmp_len = True, 0
            pos_state = (found, kmp_len)
        else:
            if token in self._pos_needed:
                pos_state = pos_state | {token}

        new_neg_states = []
        for (kind, tokens, table), neg_state in zip(self._negatives, neg_states):
            if kind == EXACT:
                if neg_state is not None:
                    if neg_state < len(tokens) and token == tokens[neg_state]:
                        neg_state += 1
                    else:
                        neg_state = None
            else:
                neg_state = _kmp_step(tokens, table, neg_state, token)
                if neg_state == len(tokens):
                    return None
            new_neg_states.append(neg_state)
        return (pos_state, tuple(new_neg_states))

    def is_accepting(self, state: Hashable) -> bool:
        pos_state, neg_states = state
        if self._pos_kind == EXACT:
            if pos_state != len(self._pos_tokens):
                return False
        elif self._pos_kind == PHRASE:
            if not pos_state[0]:
                return False
        else:
            if pos_state != self._pos_needed:
                return False
        for (kind, tokens, _), neg_state in zip(self._negatives, neg_states):
            if kind == EXACT and neg_state == len(tokens):
                return False
        return True
