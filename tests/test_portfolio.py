from __future__ import annotations

import unittest
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finpilot.portfolio import build_portfolio, portfolio_stress


def screen_row(entity_id: str, score: float | None = 1.0, volatility: float | None = 0.2, sector: str = "S") -> dict:
    return {
        "entity_id": entity_id,
        "sector": sector,
        "score": {"score": score},
        "market": {"volatility_20d": volatility},
        "evidence_ids": [f"ev-{entity_id}"],
    }


def screen(*rows: dict) -> dict:
    return {"selected": [row["entity_id"] for row in rows], "rows": list(rows)}


def prices(values: list[float], dates: pd.DatetimeIndex | None = None) -> pd.DataFrame:
    dates = dates if dates is not None else pd.date_range("2025-01-01", periods=len(values), freq="D")
    return pd.DataFrame({"date": dates, "close": values})


class BuildPortfolioTests(unittest.TestCase):
    def test_cap_leaves_cash_instead_of_relaxing_cap(self) -> None:
        result = build_portfolio(screen(screen_row("A"), screen_row("B")), weight_cap=0.30)
        self.assertEqual(result["method"], "equal")
        self.assertEqual([holding["entity_id"] for holding in result["holdings"]], ["A", "B"])
        self.assertAlmostEqual(result["holdings"][0]["weight"], 0.30)
        self.assertAlmostEqual(result["holdings"][1]["weight"], 0.30)
        self.assertAlmostEqual(result["weights_sum"], 0.60)
        self.assertAlmostEqual(result["cash_weight"], 0.40)
        self.assertTrue(all(holding["weight"] <= 0.30 + 1e-12 for holding in result["holdings"]))

    def test_equal_cap_and_full_investment_with_enough_names(self) -> None:
        result = build_portfolio(
            screen(*(screen_row(name) for name in "ABCD")), weight_cap=0.30
        )
        self.assertAlmostEqual(result["weights_sum"], 1.0)
        self.assertAlmostEqual(result["cash_weight"], 0.0)
        self.assertTrue(all(holding["weight"] <= 0.30 + 1e-12 for holding in result["holdings"]))

    def test_score_weighted_zeros_nonpositive_scores_and_all_zero_is_cash(self) -> None:
        result = build_portfolio(
            screen(screen_row("A", 2), screen_row("B", 1), screen_row("C", 0), screen_row("D", -1)),
            method="score_weighted",
            weight_cap=1.0,
        )
        self.assertAlmostEqual(result["holdings"][0]["weight"], 2 / 3)
        self.assertAlmostEqual(result["holdings"][1]["weight"], 1 / 3)
        self.assertEqual(result["holdings"][2]["weight"], 0.0)
        self.assertEqual(result["holdings"][3]["weight"], 0.0)
        cash = build_portfolio(
            screen(screen_row("A", 0), screen_row("B", -1)),
            method="score_weighted",
        )
        self.assertEqual(cash["weights_sum"], 0.0)
        self.assertEqual(cash["cash_weight"], 1.0)

    def test_inverse_volatility_uses_observed_volatility_without_none_imputation(self) -> None:
        result = build_portfolio(
            screen(screen_row("A", volatility=0.10), screen_row("B", volatility=0.20)),
            method="vol_inverse",
            weight_cap=1.0,
        )
        self.assertAlmostEqual(result["holdings"][0]["weight"], 2 / 3)
        self.assertAlmostEqual(result["holdings"][1]["weight"], 1 / 3)
        missing = build_portfolio(
            screen(screen_row("A", volatility=None), screen_row("B", volatility=0.20)),
            method="vol_inverse",
            weight_cap=1.0,
        )
        self.assertEqual(missing["holdings"][0]["weight"], 0.0)
        self.assertAlmostEqual(missing["holdings"][1]["weight"], 1.0)
        zero = build_portfolio(
            screen(screen_row("A", volatility=0.0), screen_row("B", volatility=0.20)),
            method="vol_inverse",
            weight_cap=1.0,
        )
        self.assertEqual(zero["holdings"][0]["weight"], 0.0)

    def test_invalid_parameters_are_rejected(self) -> None:
        base = screen(screen_row("A"))
        for kwargs in (
            {"method": "bad"},
            {"max_names": 0},
            {"min_names": 0},
            {"min_names": 2, "max_names": 1},
            {"weight_cap": 0},
            {"weight_cap": 1.1},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    build_portfolio(base, **kwargs)


class PortfolioStressTests(unittest.TestCase):
    def setUp(self) -> None:
        self.holdings = [
            {"entity_id": "A", "sector": "Tech", "weight": 0.5},
            {"entity_id": "B", "sector": "Banks", "weight": 0.25},
        ]

    def test_dates_are_aligned_by_actual_date_not_position(self) -> None:
        dates_a = pd.date_range("2025-01-01", periods=80, freq="D")
        dates_b = dates_a.delete(10)
        frame_a = prices(list(100 + np.arange(len(dates_a), dtype=float)), dates_a)
        frame_b = prices(list(200 + np.arange(len(dates_b), dtype=float)), dates_b)
        result = portfolio_stress(
            self.holdings,
            {"A": frame_a, "B": frame_b},
            scenarios=[{"name": "p", "type": "parametric", "z": 1.0}],
        )
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["joint_return_observations"], len(dates_b) - 1)
        self.assertAlmostEqual(result["sector_weights"]["Tech"], 0.5)
        self.assertAlmostEqual(result["sector_weights"]["Banks"], 0.25)
        self.assertGreaterEqual(result["hhi"], 0.0)

    def test_parametric_covariance_is_daily_and_uses_weights(self) -> None:
        dates = pd.date_range("2025-01-01", periods=80, freq="D")
        a_returns = np.resize(np.array([0.01, -0.01]), len(dates) - 1)
        b_returns = np.resize(np.array([0.02, -0.02]), len(dates) - 1)
        a_close = [100.0]
        b_close = [100.0]
        for a_return, b_return in zip(a_returns, b_returns):
            a_close.append(a_close[-1] * (1 + a_return))
            b_close.append(b_close[-1] * (1 + b_return))
        result = portfolio_stress(
            self.holdings,
            {"A": prices(a_close, dates), "B": prices(b_close, dates)},
            scenarios=[{"name": "p", "type": "parametric", "z": 1.0}],
        )
        daily = pd.DataFrame({"A": a_returns, "B": b_returns}).cov().to_numpy()
        weights = np.array([0.5, 0.25])
        expected = float(np.sqrt(weights @ daily @ weights))
        self.assertAlmostEqual(result["scenarios"][0]["portfolio_loss"], expected)
        self.assertEqual(result["scenarios"][0]["horizon_label"], "1-day")

    def test_single_asset_covariance_and_zero_volatility(self) -> None:
        dates = pd.date_range("2025-01-01", periods=80, freq="D")
        constant = portfolio_stress(
            [{"entity_id": "A", "sector": "S", "weight": 1.0}],
            {"A": prices([100.0] * len(dates), dates)},
            scenarios=[{"name": "p", "type": "parametric", "z": 1.645}],
        )
        self.assertEqual(constant["status"], "valid")
        self.assertEqual(constant["scenarios"][0]["portfolio_loss"], 0.0)
        self.assertEqual(constant["scenarios"][0]["per_entity_contribution"]["A"], 0.0)

    def test_historical_is_compounded_portfolio_rolling_window(self) -> None:
        dates = pd.date_range("2025-01-01", periods=60, freq="D")
        a_returns = np.full(len(dates) - 1, -0.01)
        b_returns = np.full(len(dates) - 1, 0.01)
        a_close = [100.0]
        b_close = [100.0]
        for a_return, b_return in zip(a_returns, b_returns):
            a_close.append(a_close[-1] * (1 + a_return))
            b_close.append(b_close[-1] * (1 + b_return))
        result = portfolio_stress(
            self.holdings,
            {"A": prices(a_close, dates), "B": prices(b_close, dates)},
            scenarios=[{"name": "h", "type": "historical", "window": 20}],
        )
        # The remaining 25% is cash, so the fixed-weight daily portfolio
        # return is 0.5*(-1%) + 0.25*(+1%) = -0.25%.
        expected = -(np.power(1 - 0.0025, 20) - 1)
        scenario = result["scenarios"][0]
        self.assertAlmostEqual(scenario["portfolio_loss"], expected)
        self.assertEqual(scenario["horizon_label"], "20-day")
        self.assertIn("fixed current weights", " ".join(scenario["assumptions"]))

    def test_short_common_window_is_insufficient_and_gaps_warn(self) -> None:
        dates = pd.date_range("2025-01-01", periods=39, freq="D")
        gap_dates = dates.delete(10)
        result = portfolio_stress(
            self.holdings,
            {"A": prices([100 + i for i in range(len(dates))], dates), "B": prices([200 + i for i in range(len(gap_dates))], gap_dates)},
        )
        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["joint_return_observations"], len(gap_dates) - 1)
        self.assertTrue(any("fewer than 40" in warning for warning in result["warnings"]))

    def test_invalid_stress_inputs_are_rejected(self) -> None:
        dates = pd.date_range("2025-01-01", periods=45, freq="D")
        frame = prices([100 + i for i in range(len(dates))], dates)
        with self.assertRaises(ValueError):
            portfolio_stress([{"entity_id": "A", "weight": -0.1}], {"A": frame})
        with self.assertRaises(ValueError):
            portfolio_stress([{"entity_id": "A", "weight": 1.1}], {"A": frame})
        with self.assertRaises(ValueError):
            portfolio_stress([{"entity_id": "A", "weight": 1.0}], {"A": frame}, scenarios=[{"name": "x", "type": "parametric", "z": 0}])


if __name__ == "__main__":
    unittest.main()
