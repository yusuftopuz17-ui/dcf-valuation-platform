"""Tests for the lightweight public-market tools."""

import numpy as np
import pandas as pd
import pytest

from valuation_platform.market_tools import (
    comparable_implied_prices,
    dcf_sensitivity,
    forward_dcf,
    reverse_dcf,
    scenario_table,
)


def test_forward_and_reverse_dcf_reconcile():
    result = forward_dcf(100, .10, .025, .09, 5, 10, 20, 80, True, False)
    implied = reverse_dcf(result["Per Share"], 100, .025, .09, 5, 10, 20, True, False)
    assert implied == pytest.approx(.10, abs=1e-8)
    assert result["Enterprise Value"] - 20 == pytest.approx(result["Equity Value"])
    assert result["Terminal Share"] > 0


def test_dcf_sensitivity_and_scenarios():
    grid = dcf_sensitivity(100, .10, .025, .09, 5, 10, 20, True, False)
    assert grid.shape == (9, 9)
    cases = scenario_table(100, .10, .025, .09, 5, 10, 20, 80, True, False)
    assert cases.loc["Ayı", "Hisse Başı Değer"] < cases.loc["Baz", "Hisse Başı Değer"]
    assert cases.loc["Baz", "Hisse Başı Değer"] < cases.loc["Boğa", "Hisse Başı Değer"]


def test_comparable_implied_prices_use_ev_bridge():
    target = pd.Series({
        "EBITDA": 100, "Net Income": 60, "Revenue": 500, "Equity": 300,
        "Diluted Shares": 10, "Net Debt": 20, "Current Price": 50,
    })
    peers = pd.DataFrame({
        "EV/EBITDA": [10, 12, 14], "P/E": [20, 22, 24],
        "P/S": [3, 4, 5], "P/B": [5, 6, 7],
    })
    implied = comparable_implied_prices(target, peers)
    assert implied.loc["EV/EBITDA", "İma Edilen Fiyat"] == pytest.approx((1200 - 20) / 10)
    assert np.isfinite(implied["İma Edilen Fiyat"]).all()
