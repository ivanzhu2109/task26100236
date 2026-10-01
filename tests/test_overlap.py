import itertools
import unittest

from keyword_overlap import OTHER, AdGroup, Keyword, find_overlap
from keyword_overlap.search import _alphabet


def matches_keyword(match_type, pattern, term):
    if match_type == "exact":
        return list(pattern) == list(term)
    if match_type == "phrase":
        n = len(pattern)
        return any(list(term[i:i + n]) == list(pattern) for i in range(len(term) - n + 1))
    if match_type == "broad":
        return set(pattern) <= set(term)
    raise AssertionError(match_type)


def accepts(group, account_negatives, term):
    """Independent spec-level checker used to verify witnesses."""
    positive = group["positive"]
    if not matches_keyword(positive[0], positive[1], term):
        return False
    for match_type, tokens in list(group.get("negatives", [])) + list(account_negatives):
        if matches_keyword(match_type, tokens, term):
            return False
    return True


def term_sort_key(term):
    """Order ordinary tokens by ASCII, the reserved OTHER token last."""
    return tuple((token == OTHER, token) for token in term)


class OverlapTestCase(unittest.TestCase):
    def assert_witness(self, left, right, account_negatives, expected):
        witness = find_overlap(left, right, account_negatives)
        self.assertEqual(expected, None if witness is None else list(witness))
        if witness is not None:
            self.assertTrue(accepts(left, account_negatives, witness))
            self.assertTrue(accepts(right, account_negatives, witness))

    def assert_minimal(self, left, right, account_negatives):
        """Brute-force: no jointly accepted term may beat the returned witness."""
        witness = find_overlap(left, right, account_negatives)
        tokens = sorted(
            set(t for group in (left, right) for t in group["positive"][1])
            | set(t for group in (left, right)
                  for neg in group.get("negatives", []) for t in neg[1])
            | set(t for neg in account_negatives for t in neg[1])
        ) + [OTHER]
        limit = len(witness) if witness is not None else 4
        best = None
        for length in range(1, limit + 1):
            for candidate in itertools.product(tokens, repeat=length):
                if best is not None and term_sort_key(candidate) >= term_sort_key(best):
                    continue
                if (accepts(left, account_negatives, candidate)
                        and accepts(right, account_negatives, candidate)):
                    best = candidate
            if best is not None:
                break
        self.assertEqual(best, witness)


class RequiredScenariosTest(OverlapTestCase):
    def test_phrase_cross_overlap(self):
        left = {"positive": ("phrase", ["a", "b"])}
        right = {"positive": ("phrase", ["b", "a"])}
        self.assert_witness(left, right, [], ["a", "b", "a"])
        self.assert_minimal(left, right, [])

    def test_exact_account_negative_is_not_a_substring_ban(self):
        left = {"positive": ("phrase", ["a", "b"])}
        right = {"positive": ("phrase", ["b", "a"])}
        negatives = [("exact", ["a", "b", "a"])]
        self.assert_witness(left, right, negatives, ["b", "a", "b"])
        self.assert_minimal(left, right, negatives)

    def test_broad_with_phrase_negatives_uses_other(self):
        left = {"positive": ("broad", ["a", "b"]), "negatives": [("phrase", ["a", "b"])]}
        right = {"positive": ("broad", ["a", "b"]), "negatives": [("phrase", ["b", "a"])]}
        self.assert_witness(left, right, [], ["a", OTHER, "b"])
        self.assert_minimal(left, right, [])

    def test_account_phrase_negative_eliminates_overlap(self):
        left = {"positive": ("broad", ["a", "b"]), "negatives": [("phrase", ["a", "b"])]}
        right = {"positive": ("broad", ["a", "b"]), "negatives": [("phrase", ["b", "a"])]}
        negatives = [("phrase", ["a"])]
        self.assert_witness(left, right, negatives, None)
        self.assert_minimal(left, right, negatives)


class MatchSemanticsTest(OverlapTestCase):
    def test_exact_positives(self):
        left = {"positive": ("exact", ["a", "b"])}
        right = {"positive": ("exact", ["a", "b"])}
        self.assert_witness(left, right, [], ["a", "b"])

    def test_exact_positives_disagree(self):
        left = {"positive": ("exact", ["a"])}
        right = {"positive": ("exact", ["a", "b"])}
        self.assert_witness(left, right, [], None)

    def test_broad_ignores_order_and_duplicate_config_tokens(self):
        left = {"positive": ("broad", ["a", "a", "b"])}
        right = {"positive": ("broad", ["b", "a"])}
        self.assert_witness(left, right, [], ["a", "b"])
        self.assert_minimal(left, right, [])

    def test_broad_allows_extra_tokens_in_term(self):
        left = {"positive": ("broad", ["a"])}
        right = {"positive": ("exact", ["b", "a", "b"])}
        self.assert_witness(left, right, [], ["b", "a", "b"])

    def test_phrase_overlapping_occurrences(self):
        left = {"positive": ("phrase", ["a", "a"])}
        right = {"positive": ("phrase", ["a", "a", "a"])}
        self.assert_witness(left, right, [], ["a", "a", "a"])
        self.assert_minimal(left, right, [])

    def test_group_level_exact_negative(self):
        left = {"positive": ("broad", ["a"]), "negatives": [("exact", ["a"])]}
        right = {"positive": ("broad", ["a"])}
        self.assert_witness(left, right, [], ["a", "a"])
        self.assert_minimal(left, right, [])

    def test_other_sorts_after_ordinary_tokens(self):
        left = {
            "positive": ("broad", ["a"]),
            "negatives": [("exact", ["a"]), ("phrase", ["a", "a"])],
        }
        right = {"positive": ("broad", ["a"]), "negatives": [("exact", ["b", "b", "b"])]}
        # "a a" is banned; "a b" must win over "a OTHER" because b < OTHER.
        self.assert_witness(left, right, [], ["a", "b"])
        self.assert_minimal(left, right, [])

    def test_other_filler_when_no_plain_token_works(self):
        left = {
            "positive": ("broad", ["a"]),
            "negatives": [("exact", ["a"]), ("phrase", ["a", "a"]), ("phrase", ["a", "b"])],
        }
        right = {"positive": ("broad", ["a"]), "negatives": [("exact", ["b", "b", "b"])]}
        self.assert_witness(left, right, [], ["a", OTHER])
        self.assert_minimal(left, right, [])


class ValidationTest(unittest.TestCase):
    def test_broad_negative_rejected(self):
        left = {"positive": ("broad", ["a"]), "negatives": [("broad", ["a"])]}
        right = {"positive": ("broad", ["a"])}
        with self.assertRaises(ValueError):
            find_overlap(left, right)

    def test_other_in_config_rejected(self):
        left = {"positive": ("phrase", ["a", OTHER])}
        right = {"positive": ("broad", ["a"])}
        with self.assertRaises(ValueError):
            find_overlap(left, right)

    def test_empty_tokens_rejected(self):
        left = {"positive": ("exact", [])}
        right = {"positive": ("broad", ["a"])}
        with self.assertRaises(ValueError):
            find_overlap(left, right)

    def test_unknown_match_type_rejected(self):
        left = {"positive": ("regex", ["a"])}
        right = {"positive": ("broad", ["a"])}
        with self.assertRaises(ValueError):
            find_overlap(left, right)


class DataclassInputTest(OverlapTestCase):
    def test_keyword_and_adgroup_objects(self):
        left = AdGroup(Keyword("phrase", ("a", "b")))
        right = AdGroup(Keyword("phrase", ("b", "a")))
        witness = find_overlap(left, right, [Keyword("exact", ("a", "b", "a"))])
        self.assertEqual(("b", "a", "b"), witness)


if __name__ == "__main__":
    unittest.main()
