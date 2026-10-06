from __future__ import annotations

import math
import os
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finpilot.analytics import composite_score, frames, fundamental_features, market_features, risk_snapshot
from finpilot.domain import Observation


class AnalyticsTests(unittest.TestCase):
    def test_frames_and_as_of_cutoff_are_point_in_time(self) -> None:
        observations = [
            Observation("SYNTH", "close", 100.0, "USD", "2024-01-01", "2024-01-01", None, "2024-01-01", "fixture", "x", "h"),
            Observation("SYNTH", "close", 110.0, "USD", "2024-01-02", "2024-01-02", None, "2024-01-02", "fixture", "x", "h"),
            Observation("SYNTH", "revenue", 100.0, "USD_mm", "2023-01-01", "2023-12-31", "2024-02-01", "2024-02-01", "fixture", "x", "h"),
            Observation("SYNTH", "revenue", 120.0, "USD_mm", "2024-01-01", "2024-12-31", "2025-02-01", "2025-02-01", "fixture", "x", "h"),
        ]
        market, fundamentals = frames(observations)
        self.assertEqual(len(market), 2)
        self.assertEqual(len(fundamentals), 2)
        early = fundamental_features(fundamentals, "2024-12-31")
        late = fundamental_features(fundamentals, "2025-12-31")
        self.assertEqual(early["latest"]["revenue"], 100.0)
        self.assertEqual(late["latest"]["revenue"], 120.0)

    def test_market_features_hand_calculation(self) -> None:
        dates = pd.date_range("2024-01-01", periods=4, freq="D")
        market = pd.DataFrame({"date": dates, "close": [100.0, 110.0, 99.0, 108.0]})
        result = market_features(market, "2024-01-04")
        self.assertAlmostEqual(result["last_close"], 108.0)
        self.assertAlmostEqual(result["max_drawdown"], 99.0 / 110.0 - 1.0)
        self.assertIsNone(result["return_20d"])
        self.assertAlmostEqual(result["volatility_20d"], pd.Series([0.1, -0.1, 108.0 / 99.0 - 1.0]).std(ddof=1) * math.sqrt(252.0))

    def test_drawdown_penalty_has_correct_direction(self) -> None:
        base = {"return_20d": 0.1, "return_60d": 0.1, "volatility_20d": 0.2}
        fundamentals = {"revenue_growth_yoy": 0.1, "fcf_margin": 0.2}
        mild = composite_score({**base, "max_drawdown": -0.10}, fundamentals, {})
        severe = composite_score({**base, "max_drawdown": -0.40}, fundamentals, {})
        self.assertGreaterEqual(mild["score"], severe["score"])
        self.assertLess(mild["components"]["risk_penalty"], severe["components"]["risk_penalty"])

    def test_risk_snapshot_flags_negative_quality(self) -> None:
        result = risk_snapshot({"status": "valid", "volatility_20d": 0.2, "max_drawdown": -0.1}, {"status": "valid", "operating_margin": -0.02, "fcf_margin": -0.01})
        self.assertEqual(result["status"], "review")
        self.assertIn("negative_operating_margin", result["flags"])
        self.assertIn("negative_fcf_margin", result["flags"])


if __name__ == "__main__":
    unittest.main()
