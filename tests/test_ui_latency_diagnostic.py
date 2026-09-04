import unittest

from tools.ui_latency_diagnostic import summarize_latency


class UiLatencyDiagnosticTests(unittest.TestCase):
    def test_summary_reports_distribution_and_threshold_counts(self) -> None:
        report = summarize_latency([0.5, 2.0, 17.0, 34.0, 60.0])
        self.assertIn("样本 5", report)
        self.assertIn("平均 22.70 ms", report)
        self.assertIn("P95 60.00 ms", report)
        self.assertIn(">16 ms: 3", report)
        self.assertIn(">33 ms: 2", report)
        self.assertIn(">50 ms: 1", report)

    def test_empty_summary_is_clear(self) -> None:
        self.assertEqual(summarize_latency([]), "没有采集到数据。")


if __name__ == "__main__":
    unittest.main()
