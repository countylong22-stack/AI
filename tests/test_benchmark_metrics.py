import unittest

from rooster_pentester.benchmark import evaluate_findings


class BenchmarkMetricsTests(unittest.TestCase):
    def test_perfect_detection_and_severity_agreement(self):
        expected = [
            {"finding_id": "tls-hsts", "severity": "MEDIUM"},
            {"finding_id": "csp", "severity": "LOW"},
        ]
        result = evaluate_findings(expected, list(expected))
        self.assertEqual(result["metrics"]["precision"], 1.0)
        self.assertEqual(result["metrics"]["recall"], 1.0)
        self.assertEqual(result["metrics"]["f1"], 1.0)
        self.assertEqual(result["metrics"]["severity_exact_match_rate"], 1.0)

    def test_false_positive_and_false_negative_are_separated(self):
        result = evaluate_findings(
            [{"check": "hsts", "severity": "MEDIUM"}, {"check": "csp", "severity": "LOW"}],
            [{"check": "hsts", "severity": "HIGH"}, {"check": "extra", "severity": "LOW"}],
        )
        self.assertEqual(result["counts"]["true_positive"], 1)
        self.assertEqual(result["counts"]["false_positive"], 1)
        self.assertEqual(result["counts"]["false_negative"], 1)
        self.assertEqual(result["metrics"]["precision"], 0.5)
        self.assertEqual(result["metrics"]["recall"], 0.5)
        self.assertEqual(result["metrics"]["severity_exact_match_rate"], 0.0)
        self.assertEqual(len(result["severity_mismatches"]), 1)

    def test_keys_are_normalized_but_not_fuzzy_matched(self):
        result = evaluate_findings(
            [{"finding_id": "  HSTS   Header "}],
            [{"finding_id": "hsts header"}],
        )
        self.assertEqual(result["metrics"]["f1"], 1.0)
        result = evaluate_findings([{"check": "hsts"}], [{"check": "hsts missing"}])
        self.assertEqual(result["counts"]["true_positive"], 0)

    def test_duplicate_keys_are_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_findings(
                [{"check": "hsts"}, {"check": "HSTS"}],
                [],
            )

    def test_missing_identity_key_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_findings([{"severity": "HIGH"}], [])

    def test_empty_fixture_is_well_defined(self):
        result = evaluate_findings([], [])
        self.assertEqual(result["metrics"]["precision"], 1.0)
        self.assertEqual(result["metrics"]["recall"], 1.0)
        self.assertEqual(result["metrics"]["f1"], 1.0)
        self.assertIsNone(result["metrics"]["severity_exact_match_rate"])


if __name__ == "__main__":
    unittest.main()
