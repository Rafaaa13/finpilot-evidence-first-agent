from __future__ import annotations

import math
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finpilot.pipeline import run_fixture
from finpilot.report import write_json
from finpilot.serialization import json_safe


class PipelineTests(unittest.TestCase):
    def test_fixture_run_has_integrated_risk_and_passes_gates(self) -> None:
        result = run_fixture(output_dir="/tmp/finpilot-test-pipeline")
        self.assertTrue(result["risk_lab"]["summary"]["loan_count"] == 240)
        self.assertTrue(result["leakage_check"]["passed"])
        self.assertTrue(result["evaluation"]["numeric_consistency"]["passed"])
        self.assertTrue(result["result_hash"])
        self.assertTrue(result["run_id"])

    def test_early_cutoff_is_reviewable_not_a_report_crash(self) -> None:
        result = run_fixture("AAPL", "2021-06-30", output_dir="/tmp/finpilot-test-early", include_risk_lab=False)
        self.assertIsNone(result["score"]["score"])
        self.assertEqual(result["market"]["status"], "missing")

    def test_strict_json_converts_nonfinite_to_null(self) -> None:
        path = Path("/tmp/finpilot-test-json/result.json")
        write_json(path, {"x": float("nan"), "nested": [float("inf"), 1]})
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("NaN", text)
        self.assertNotIn("Infinity", text)
        self.assertIsNone(__import__("json").loads(text)["x"])


if __name__ == "__main__":
    unittest.main()
