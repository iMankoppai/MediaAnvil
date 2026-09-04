import unittest

from tools.ui_latency_diagnostic import analyze_drag_tracking


class UiLatencyDiagnosticTests(unittest.TestCase):
    def test_reports_stable_cursor_to_window_tracking(self) -> None:
        samples = [
            (index * 0.01, True, 100 + index * 5, 80, 50 + index * 5, 20)
            for index in range(20)
        ]
        summary, detail = analyze_drag_tracking(samples)
        self.assertIn("有效拖动 1 次", summary)
        self.assertIn("偏离 P95 0.0 px", summary)
        self.assertIn("最大 0.0 px", summary)
        self.assertIn("采样间隔 P95 10.0 ms", detail)

    def test_reports_cursor_window_separation(self) -> None:
        samples = [
            (index * 0.01, True, 100 + index * 5, 80, 50 + index * 4, 20)
            for index in range(20)
        ]
        summary, _ = analyze_drag_tracking(samples)
        self.assertIn("偏离 P95 18.0 px", summary)
        self.assertIn("最大 19.0 px", summary)

    def test_no_drag_is_clear(self) -> None:
        summary, detail = analyze_drag_tracking([])
        self.assertEqual(summary, "没有识别到有效的窗口拖动。")
        self.assertIn("标题栏", detail)


if __name__ == "__main__":
    unittest.main()
