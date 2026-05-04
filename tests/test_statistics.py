import math
import unittest

from mlcore.evaluation.statistics import bootstrap_mean_ci


class BootstrapMeanConfidenceIntervalTests(unittest.TestCase):
    def test_returns_deterministic_output_with_fixed_seed(self):
        first_result = bootstrap_mean_ci(
            [0.2, 0.4, 0.8, 1.0],
            n_bootstrap=200,
            random_state=123,
        )
        second_result = bootstrap_mean_ci(
            [0.2, 0.4, 0.8, 1.0],
            n_bootstrap=200,
            random_state=123,
        )

        self.assertEqual(first_result, second_result)
        self.assertEqual(first_result["n"], 4)
        self.assertLessEqual(first_result["ci_lower"], first_result["mean"])
        self.assertLessEqual(first_result["mean"], first_result["ci_upper"])

    def test_ignores_nan_values(self):
        with_nan = bootstrap_mean_ci(
            [0.25, math.nan, None, 0.75],
            n_bootstrap=100,
            random_state=42,
        )
        without_nan = bootstrap_mean_ci(
            [0.25, 0.75],
            n_bootstrap=100,
            random_state=42,
        )

        self.assertEqual(with_nan, without_nan)

    def test_handles_empty_input(self):
        result = bootstrap_mean_ci([], n_bootstrap=100)

        self.assertEqual(
            result,
            {"mean": None, "ci_lower": None, "ci_upper": None, "n": 0},
        )

    def test_handles_single_value(self):
        result = bootstrap_mean_ci([0.6], n_bootstrap=100)

        self.assertEqual(result["mean"], 0.6)
        self.assertEqual(result["ci_lower"], 0.6)
        self.assertEqual(result["ci_upper"], 0.6)
        self.assertEqual(result["n"], 1)

    def test_validates_parameters(self):
        with self.assertRaisesRegex(ValueError, "n_bootstrap"):
            bootstrap_mean_ci([0.1, 0.2], n_bootstrap=0)

        with self.assertRaisesRegex(ValueError, "confidence_level"):
            bootstrap_mean_ci([0.1, 0.2], confidence_level=1.0)


if __name__ == "__main__":
    unittest.main()
