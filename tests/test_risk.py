from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finpilot.risk import (
    _auc,
    _classification_metrics,
    black_scholes_price,
    bond_price,
    bond_risk,
    credit_losses,
    option_price,
    run_risk_lab,
    synthetic_loans,
)


class CreditRiskTests(unittest.TestCase):
    def test_fixture_has_fixed_months_and_immutable_split(self) -> None:
        first = run_risk_lab(seed=42)
        second = run_risk_lab(seed=42)
        self.assertEqual(first, second)
        self.assertEqual(len(first["loans"]), 240)
        self.assertEqual(first["loans"][0]["month"], "2023-01")
        self.assertEqual(first["loans"][-1]["month"], "2024-12")
        self.assertEqual(first["summary"]["train_count"], 120)
        self.assertEqual(first["summary"]["validation_count"], 120)
        self.assertEqual(first["validation"]["train_period"]["end"], "2023-12")
        self.assertEqual(first["validation"]["validation_period"]["start"], "2024-01")

    def test_credit_el_is_ead_weighted_with_caps(self) -> None:
        loans = [
            {"pd": 0.10, "lgd": 0.50, "ead": 100.0, "default": 0},
            {"pd": 0.20, "lgd": 0.25, "ead": 900.0, "default": 1},
        ]
        result = credit_losses(loans, pd_multiplier=1.0, lgd_shift=0.0)
        # Independent hand calculation: 100*.1*.5 + 900*.2*.25 = 50.
        self.assertAlmostEqual(result["expected_loss_amount"], 50.0)
        self.assertAlmostEqual(result["expected_loss_rate"], 0.05)
        self.assertAlmostEqual(result["ead_concentration"]["hhi"], 0.1**2 + 0.9**2)
        stressed = credit_losses(loans, pd_multiplier=10.0, lgd_shift=1.0)
        self.assertAlmostEqual(stressed["expected_loss_amount"], 1000.0)
        self.assertAlmostEqual(stressed["expected_loss_rate"], 1.0)

    def test_auc_and_brier_have_independent_small_sample_benchmarks(self) -> None:
        # Positives have scores .8 and .4; negatives have .4 and .1.
        # Three strict wins plus one half tie out of four comparisons = .875.
        self.assertAlmostEqual(_auc([1, 0, 1, 0], [0.8, 0.4, 0.4, 0.1]), 0.875)
        rows = [
            {"default": 1, "predicted_pd": 0.8},
            {"default": 0, "predicted_pd": 0.4},
            {"default": 1, "predicted_pd": 0.4},
            {"default": 0, "predicted_pd": 0.1},
        ]
        result = _classification_metrics(rows)
        self.assertAlmostEqual(result["brier"], (0.2**2 + 0.4**2 + 0.6**2 + 0.1**2) / 4.0)
        self.assertAlmostEqual(result["ece"], 0.25 * 0.2 + 0.50 * 0.1 + 0.25 * 0.1)


class BondRiskTests(unittest.TestCase):
    def test_zero_coupon_price_duration_convexity_and_dv01(self) -> None:
        # One-year annual zero-coupon bond: P = 100/1.05, Dmod = 1/1.05.
        result = bond_risk(100.0, 0.0, 0.05, 1.0, frequency=1, shock_bps=100.0)
        self.assertAlmostEqual(result["price"], 100.0 / 1.05)
        self.assertAlmostEqual(result["modified_duration"], 1.0 / 1.05)
        self.assertAlmostEqual(result["convexity"], 2.0 / (1.05**2))
        self.assertAlmostEqual(result["dv01"], 100.0 / 1.05 - 100.0 / 1.0501)
        self.assertAlmostEqual(result["scenario"]["shocked_price"], 100.0 / 1.06)
        self.assertLess(result["scenario"]["price_change"], 0.0)

    def test_par_bond_matches_face_value(self) -> None:
        self.assertAlmostEqual(bond_price(1000.0, 0.04, 0.04, 5.0, 2), 1000.0)


class OptionRiskTests(unittest.TestCase):
    def test_put_call_parity(self) -> None:
        call = black_scholes_price(100.0, 100.0, 0.05, 0.2, 1.0, "call")
        put = black_scholes_price(100.0, 100.0, 0.05, 0.2, 1.0, "put")
        self.assertAlmostEqual(call - put, 100.0 - 100.0 * math.exp(-0.05))
        self.assertAlmostEqual(call, 10.450583572185565)

    def test_seeded_monte_carlo_reports_standard_error(self) -> None:
        result = option_price(100.0, 100.0, 0.05, 0.2, 1.0, simulations=100_000, seed=42)
        self.assertGreater(result["standard_error"], 0.0)
        self.assertLess(abs(result["monte_carlo"] - result["black_scholes"]), 4.0 * result["standard_error"])
        self.assertEqual(result, option_price(100.0, 100.0, 0.05, 0.2, 1.0, simulations=100_000, seed=42))


if __name__ == "__main__":
    unittest.main()
