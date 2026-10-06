from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finpilot.backtest import leakage_check, run_momentum_backtest


class BacktestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.market = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=6, freq="D"),
                "close": [1.0, 1.0, 1.0, 2.0, 3.0, 4.0],
            }
        )

    def test_next_close_execution_does_not_use_signal_close(self) -> None:
        result = run_momentum_backtest(self.market, transaction_cost=0.0, short_window=2, long_window=3)
        self.assertEqual(result["status"], "valid")
        self.assertEqual(len(result["executions"]), 1)
        trade = result["executions"][0]
        self.assertEqual(trade["signal_date"], "2024-01-04")
        self.assertEqual(trade["execution_date"], "2024-01-05")
        # The price jump into the execution close is not earned.  The first
        # strategy gain is the next close-to-close return, 4/3 - 1.
        curve = result["equity_curve"]
        self.assertAlmostEqual(curve[4]["equity"], 1.0)
        self.assertAlmostEqual(curve[5]["equity"], 4.0 / 3.0)
        self.assertAlmostEqual(result["benchmark"]["total_return"], 3.0)

    def test_sharpe_uses_arithmetic_daily_excess_returns(self) -> None:
        result = run_momentum_backtest(self.market, transaction_cost=0.0, short_window=2, long_window=3)
        realized = np.array([0.0, 0.0, 0.0, 0.0, 1.0 / 3.0])
        expected = realized.mean() / realized.std(ddof=1) * math.sqrt(252.0)
        self.assertAlmostEqual(result["metrics"]["sharpe"], expected)
        # This differs materially from CAGR / annualized volatility, the old
        # incorrect ratio used by the implementation under test.
        self.assertNotAlmostEqual(result["metrics"]["sharpe"], result["metrics"]["annualized_return"] / result["metrics"]["annualized_volatility"])

    def test_cost_is_charged_at_execution_and_is_measured_in_ablation(self) -> None:
        result = run_momentum_backtest(self.market, transaction_cost=0.01, short_window=2, long_window=3)
        self.assertAlmostEqual(result["equity_curve"][4]["equity"], 0.99)
        self.assertAlmostEqual(result["metrics"]["total_return"], 0.99 * (4.0 / 3.0) - 1.0)
        self.assertTrue(result["ablation"]["measured"])
        self.assertGreater(result["ablation"]["fee_drag"], 0.0)
        self.assertEqual(len(result["segments"]), 2)

    def test_leakage_check_blocks_future_effective_and_filed_observations(self) -> None:
        observations = [
            {"metric": "close", "effective_at": "2024-01-03", "filed_at": None},
            {"metric": "revenue", "effective_at": "2024-01-01", "filed_at": "2024-01-05"},
        ]
        result = leakage_check(observations, "2024-01-04", "2024-01-05")
        self.assertFalse(result["passed"])
        self.assertTrue(any(item.startswith("future_filing") for item in result["failures"]))
        self.assertTrue(leakage_check(observations[:1], "2024-01-04", "2024-01-05")["passed"])


if __name__ == "__main__":
    unittest.main()
