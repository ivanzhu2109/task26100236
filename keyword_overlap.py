"""跨广告组关键词重叠判定库。

判定两个广告组是否存在共同接纳的搜索词，并返回最短见证。
仅使用 Python 标准库。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence, Tuple

EXACT = "exact"
PHRASE = "phrase"
BROAD = "broad"
MATCH_TYPES = (EXACT, PHRASE, BROAD)

OTHER = "OTHER"


@dataclass(frozen=True)
class Keyword:
    """一条关键词配置：匹配类型 + 非空 token 序列。"""

    match_type: str
    tokens: Tuple[str, ...]

    def __init__(self, match_type: str, tokens: Sequence[str]) -> None:
        if match_type not in MATCH_TYPES:
            raise ValueError(f"unknown match_type: {match_type!r}")
        tokens = tuple(tokens)
        if not tokens:
            raise ValueError("tokens must be non-empty")
        if OTHER in tokens:
            raise ValueError(f"{OTHER!r} is reserved and must not appear in config")
        object.__setattr__(self, "match_type", match_type)
        object.__setattr__(self, "tokens", tokens)


@dataclass(frozen=True)
class AdGroup:
    """一个广告组：一条正向关键词 + 若干组级否词（仅 exact/phrase）。"""

    positive: Keyword
    negatives: Tuple[Keyword, ...] = field(default_factory=tuple)

    def __init__(self, positive: Keyword, negatives: Sequence[Keyword] = ()) -> None:
        negatives = tuple(negatives)
        for neg in negatives:
            if neg.match_type not in (EXACT, PHRASE):
                raise ValueError("negatives only support exact/phrase")
        object.__setattr__(self, "positive", positive)
        object.__setattr__(self, "negatives", negatives)


def _contains_slice(haystack: Tuple[str, ...], needle: Tuple[str, ...]) -> bool:
    """needle 是否作为连续片段出现在 haystack 中。"""
    n, m = len(haystack), len(needle)
    if m > n:
        return False
    first = needle[0]
    for i in range(n - m + 1):
        if haystack[i] == first and haystack[i : i + m] == needle:
            return True
    return False


def matches_positive(keyword: Keyword, term: Sequence[str]) -> bool:
    """搜索词是否命中正向关键词。"""
    term = tuple(term)
    if keyword.match_type == EXACT:
        return term == keyword.tokens
    if keyword.match_type == PHRASE:
        return _contains_slice(term, keyword.tokens)
    # broad：配置中每个不同 token 至少出现一次
    return set(keyword.tokens) <= set(term)


def matches_negative(keyword: Keyword, term: Sequence[str]) -> bool:
    """搜索词是否命中否词（仅 exact/phrase）。"""
    term = tuple(term)
    if keyword.match_type == EXACT:
        return term == keyword.tokens
    return _contains_slice(term, keyword.tokens)


def accepts(
    group: AdGroup,
    account_negatives: Sequence[Keyword],
    term: Sequence[str],
) -> bool:
    """搜索词是否被该组接纳：命中正向词，且不命中任何组级/账号级否词。"""
    term = tuple(term)
    if not term:
        return False
    if not matches_positive(group.positive, term):
        return False
    for neg in group.negatives:
        if matches_negative(neg, term):
            return False
    for neg in account_negatives:
        if matches_negative(neg, term):
            return False
    return True


class _AhoCorasick:
    """极简 Aho-Corasick 自动机，用于连续片段（phrase）匹配。"""

    def __init__(self, patterns: Sequence[Tuple[str, ...]]):
        self.goto: list[dict] = [{}]
        self.fail: list[int] = [0]
        self.out: list[list[int]] = [[]]
        for idx, pat in enumerate(patterns):
            node = 0
            for tok in pat:
                nxt = self.goto[node].get(tok)
                if nxt is None:
                    nxt = len(self.goto)
                    self.goto[node][tok] = nxt
                    self.goto.append({})
                    self.fail.append(0)
                    self.out.append([])
                node = nxt
            self.out[node].append(idx)
        # BFS 构建 fail 链接并合并输出
        from collections import deque

        queue = deque()
        for tok, nxt in self.goto[0].items():
            queue.append(nxt)
        while queue:
            node = queue.popleft()
            for tok, nxt in self.goto[node].items():
                queue.append(nxt)
                f = self.fail[node]
                while f and tok not in self.goto[f]:
                    f = self.fail[f]
                self.fail[nxt] = self.goto[f].get(tok, 0)
                self.out[nxt] = self.out[nxt] + self.out[self.fail[nxt]]

    def step(self, node: int, tok: str) -> int:
        while node and tok not in self.goto[node]:
            node = self.fail[node]
        return self.goto[node].get(tok, 0)


class _ExactTrie:
    """exact 否词的前缀树：跟踪当前搜索词是否仍可能是某条 exact 否词的前缀。"""

    DEAD = -1

    def __init__(self, sequences: Sequence[Tuple[str, ...]]):
        self.children: list[dict] = [{}]
        self.terminal: list[bool] = [False]
        for seq in sequences:
            node = 0
            for tok in seq:
                nxt = self.children[node].get(tok)
                if nxt is None:
                    nxt = len(self.children)
                    self.children[node][tok] = nxt
                    self.children.append({})
                    self.terminal.append(False)
                node = nxt
            self.terminal[node] = True

    def step(self, node: int, tok: str) -> int:
        if node == self.DEAD:
            return self.DEAD
        return self.children[node].get(tok, self.DEAD)


def find_overlap(
    left: AdGroup,
    right: AdGroup,
    account_negatives: Sequence[Keyword] = (),
) -> Optional[Tuple[str, ...]]:
    """返回两组共同接纳的最短搜索词（同长度取字典序最小），不存在返回 None。"""
    account_negatives = tuple(account_negatives)
    for neg in account_negatives:
        if neg.match_type not in (EXACT, PHRASE):
            raise ValueError("negatives only support exact/phrase")

    # exact 正向词：该组只可能接纳与其完全相等的搜索词，直接判定。
    for group, other in ((left, right), (right, left)):
        if group.positive.match_type == EXACT:
            term = group.positive.tokens
            if accepts(left, account_negatives, term) and accepts(
                right, account_negatives, term
            ):
                return term
            return None

    # 候选字母表：全部输入 token 按 ASCII 排序，保留 token OTHER 排最后。
    vocab = set()
    for kw in (left.positive, right.positive) + left.negatives + right.negatives + account_negatives:
        vocab.update(kw.tokens)
    alphabet = sorted(vocab) + [OTHER]

    # 汇总两组的正向需求与全部否词。
    phrase_patterns: list[Tuple[str, ...]] = []  # 需要命中的 phrase 正向词
    neg_patterns: list[Tuple[str, ...]] = []  # 禁止出现的 phrase 否词
    broad_tokens: list[str] = []  # 需要出现的 broad token（去重后合并）
    exact_negs = set()
    for group in (left, right):
        pos = group.positive
        if pos.match_type == PHRASE:
            phrase_patterns.append(pos.tokens)
        else:  # broad
            for tok in dict.fromkeys(pos.tokens):
                if tok not in broad_tokens:
                    broad_tokens.append(tok)
        for neg in group.negatives:
            if neg.match_type == PHRASE:
                neg_patterns.append(neg.tokens)
            else:
                exact_negs.add(neg.tokens)
    for neg in account_negatives:
        if neg.match_type == PHRASE:
            neg_patterns.append(neg.tokens)
        else:
            exact_negs.add(neg.tokens)

    # AC 自动机同时承载 phrase 正向词（记录命中）与 phrase 否词（禁止）。
    patterns = phrase_patterns + neg_patterns
    ac = _AhoCorasick(patterns)
    neg_pattern_ids = set(range(len(phrase_patterns), len(patterns)))
    forbidden_nodes = set()
    for node in range(len(ac.goto)):
        if neg_pattern_ids.intersection(ac.out[node]):
            forbidden_nodes.add(node)

    exact_trie = _ExactTrie(sorted(exact_negs))

    broad_index = {tok: i for i, tok in enumerate(broad_tokens)}
    n_broad = len(broad_tokens)
    n_phrase = len(phrase_patterns)
    full_mask = (1 << (n_broad + n_phrase)) - 1

    # BFS：状态 = (AC 节点, 需求命中掩码)。逐层变长、层内按字典序扩展，
    # 首次到达的接受态即最短且字典序最小的见证；状态有限，必然终止。
    from collections import deque

    queue = deque([(0, 0, 0, ())])  # (ac_node, trie_node, mask, term)
    visited = {(0, 0, 0)}
    while queue:
        node, trie_node, mask, term = queue.popleft()
        for tok in alphabet:
            nxt_node = ac.step(node, tok)
            if nxt_node in forbidden_nodes:
                continue
            nxt_trie = exact_trie.step(trie_node, tok)
            nxt_mask = mask
            bit = broad_index.get(tok)
            if bit is not None:
                nxt_mask |= 1 << bit
            for pat_id in ac.out[nxt_node]:
                if pat_id < n_phrase:
                    nxt_mask |= 1 << (n_broad + pat_id)
            nxt_term = term + (tok,)
            if nxt_mask == full_mask and (
                nxt_trie == _ExactTrie.DEAD or not exact_trie.terminal[nxt_trie]
            ):
                return nxt_term
            state = (nxt_node, nxt_trie, nxt_mask)
            if state not in visited:
                visited.add(state)
                queue.append((nxt_node, nxt_trie, nxt_mask, nxt_term))
    return None
