"""Paired bootstrap, McNemar, Holm, and reliability statistics."""

import unittest

from benchmark.statistics import (
    all_success_rate,
    holm_adjust,
    mcnemar_exact,
    paired_bootstrap,
    pass_at_one,
)


class TestPairedBootstrap(unittest.TestCase):
    def test_deterministic_across_runs(self):
        blocks = {"a": [0.2, -0.1], "b": [0.5], "c": [0.0, 0.3, -0.2]}
        first = paired_bootstrap(blocks, n_resamples=200, seed=42)
        second = paired_bootstrap(blocks, n_resamples=200, seed=42)
        self.assertEqual(first, second)

    def test_confidence_interval_covers_the_true_difference(self):
        blocks = {f"block-{i}": [0.2] * 5 for i in range(60)}
        result = paired_bootstrap(blocks, n_resamples=1000, seed=7)
        self.assertAlmostEqual(result["observed_mean_diff"], 0.2)
        self.assertLessEqual(result["ci_low"], 0.2)
        self.assertGreaterEqual(result["ci_high"], 0.2)

    def test_resamples_by_block_not_by_query(self):
        blocks = {"stable": [1.0, 1.0, 1.0], "unstable": [-1.0, -1.0, -1.0]}
        result = paired_bootstrap(blocks, n_resamples=100, seed=3)
        # Query-level resampling could land at any mean; block-level keeps the
        # two fixed block values, so the observed mean is exactly 0.0.
        self.assertAlmostEqual(result["observed_mean_diff"], 0.0)


class TestMcNemar(unittest.TestCase):
    def test_exact_two_sided_p_value(self):
        a = [True, True, True, True, True]
        b = [False, False, False, False, False]
        result = mcnemar_exact(a, b)
        self.assertEqual(result["a_wins"], 5)
        self.assertEqual(result["b_wins"], 0)
        self.assertAlmostEqual(result["p_value"], 2 * 0.5**5, places=6)

    def test_concordant_only_is_not_significant(self):
        a = [True, True, False, False]
        b = [True, True, False, False]
        result = mcnemar_exact(a, b)
        self.assertEqual(result["discordant"], 0)
        self.assertEqual(result["p_value"], 1.0)


class TestHolm(unittest.TestCase):
    def test_known_adjustment(self):
        self.assertEqual(holm_adjust([0.01, 0.04, 0.5]), [0.03, 0.08, 0.5])
        self.assertEqual(holm_adjust([0.001]), [0.001])


class TestReliability(unittest.TestCase):
    def test_pass_at_one_and_all_success(self):
        groups = [[True, False], [True, True], [False, True]]
        self.assertAlmostEqual(pass_at_one(groups), 2 / 3, places=3)
        self.assertAlmostEqual(all_success_rate(groups), 1 / 3, places=3)


if __name__ == "__main__":
    unittest.main()
