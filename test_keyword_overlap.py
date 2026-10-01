import itertools
import unittest

from keyword_overlap import (
    BROAD,
    EXACT,
    OTHER,
    PHRASE,
    AdGroup,
    Keyword,
    accepts,
    find_overlap,
)


def brute_force(left, right, account_negatives, alphabet, max_len):
    """暴力枚举：按长度、同长度按字典序找第一个双方共同接纳的搜索词。"""
    for length in range(1, max_len + 1):
        for term in itertools.product(alphabet, repeat=length):
            if accepts(left, account_negatives, term) and accepts(
                right, account_negatives, term
            ):
                return term
    return None


class RequiredScenariosTest(unittest.TestCase):
    def test_phrase_cross(self):
        left = AdGroup(Keyword(PHRASE, ("a", "b")))
        right = AdGroup(Keyword(PHRASE, ("b", "a")))
        self.assertEqual(find_overlap(left, right, []), ("a", "b", "a"))

    def test_phrase_cross_with_account_exact_negative(self):
        left = AdGroup(Keyword(PHRASE, ("a", "b")))
        right = AdGroup(Keyword(PHRASE, ("b", "a")))
        negs = [Keyword(EXACT, ("a", "b", "a"))]
        # exact 否词只禁止完全相等的词，不能当子串禁止
        self.assertEqual(find_overlap(left, right, negs), ("b", "a", "b"))

    def test_broad_with_group_phrase_negatives(self):
        left = AdGroup(Keyword(BROAD, ("a", "b")), [Keyword(PHRASE, ("a", "b"))])
        right = AdGroup(Keyword(BROAD, ("a", "b")), [Keyword(PHRASE, ("b", "a"))])
        self.assertEqual(find_overlap(left, right, []), ("a", OTHER, "b"))

    def test_broad_with_account_phrase_negative_no_solution(self):
        left = AdGroup(Keyword(BROAD, ("a", "b")), [Keyword(PHRASE, ("a", "b"))])
        right = AdGroup(Keyword(BROAD, ("a", "b")), [Keyword(PHRASE, ("b", "a"))])
        negs = [Keyword(PHRASE, ("a",))]
        self.assertIsNone(find_overlap(left, right, negs))


class SemanticsTest(unittest.TestCase):
    def test_exact_positive(self):
        left = AdGroup(Keyword(EXACT, ("a", "b")))
        right = AdGroup(Keyword(PHRASE, ("a", "b")))
        self.assertEqual(find_overlap(left, right, []), ("a", "b"))

    def test_exact_positive_blocked_by_account_exact(self):
        left = AdGroup(Keyword(EXACT, ("a", "b")))
        right = AdGroup(Keyword(PHRASE, ("a", "b")))
        negs = [Keyword(EXACT, ("a", "b"))]
        self.assertIsNone(find_overlap(left, right, negs))

    def test_exact_both_sides_mismatch(self):
        left = AdGroup(Keyword(EXACT, ("a",)))
        right = AdGroup(Keyword(EXACT, ("b",)))
        self.assertIsNone(find_overlap(left, right, []))

    def test_broad_order_free_and_duplicate_config_tokens(self):
        left = AdGroup(Keyword(BROAD, ("a", "b", "a")))
        right = AdGroup(Keyword(BROAD, ("b", "a")))
        self.assertEqual(find_overlap(left, right, []), ("a", "b"))

    def test_phrase_repetition_counts(self):
        left = AdGroup(Keyword(PHRASE, ("a", "a")))
        right = AdGroup(Keyword(BROAD, ("a",)))
        self.assertEqual(find_overlap(left, right, []), ("a", "a"))

    def test_other_sorted_last(self):
        # 需要插入一个分隔 token 时，普通 token 优先于 OTHER
        left = AdGroup(Keyword(BROAD, ("a", "b")), [Keyword(PHRASE, ("a", "b"))])
        right = AdGroup(Keyword(BROAD, ("a", "b")), [Keyword(PHRASE, ("b", "a"))])
        witness = find_overlap(left, right, [])
        self.assertEqual(witness, ("a", OTHER, "b"))

    def test_witness_actually_accepted(self):
        left = AdGroup(Keyword(PHRASE, ("x", "y")), [Keyword(EXACT, ("x", "y"))])
        right = AdGroup(Keyword(BROAD, ("y", "z")))
        witness = find_overlap(left, right, [])
        self.assertIsNotNone(witness)
        self.assertTrue(accepts(left, [], witness))
        self.assertTrue(accepts(right, [], witness))

    def test_reserved_other_rejected_in_config(self):
        with self.assertRaises(ValueError):
            Keyword(PHRASE, (OTHER,))

    def test_empty_tokens_rejected(self):
        with self.assertRaises(ValueError):
            Keyword(EXACT, ())

    def test_broad_negative_rejected(self):
        with self.assertRaises(ValueError):
            AdGroup(Keyword(BROAD, ("a",)), [Keyword(BROAD, ("b",))])


class BruteForceCrossCheckTest(unittest.TestCase):
    """与小规模暴力枚举对照，验证最短性与字典序。"""

    def test_cross_check(self):
        alphabet = ("a", "b", OTHER)
        positives = [
            Keyword(EXACT, ("a",)),
            Keyword(PHRASE, ("a", "b")),
            Keyword(BROAD, ("a", "b")),
            Keyword(BROAD, ("a", "a")),
        ]
        negatives = [
            (),
            (Keyword(EXACT, ("a", "b")),),
            (Keyword(PHRASE, ("a",)),),
            (Keyword(PHRASE, ("b", "a")),),
        ]
        account_options = [
            (),
            (Keyword(EXACT, ("a", "b", "a")),),
            (Keyword(PHRASE, ("b",)),),
        ]
        for pos_l in positives:
            for pos_r in positives:
                for neg_l in negatives:
                    for neg_r in negatives:
                        for acc in account_options:
                            left = AdGroup(pos_l, neg_l)
                            right = AdGroup(pos_r, neg_r)
                            got = find_overlap(left, right, acc)
                            want = brute_force(left, right, acc, alphabet, 5)
                            if want is None:
                                # 暴力只搜到长度 5，库结果若存在也必须 ≤5 且一致
                                if got is not None:
                                    self.assertLessEqual(len(got), 5)
                                    self.assertEqual(got, want)
                            else:
                                self.assertEqual(
                                    got,
                                    want,
                                    msg=f"{left} {right} {acc}",
                                )


if __name__ == "__main__":
    unittest.main()
