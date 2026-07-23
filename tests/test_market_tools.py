"""Tests for the lightweight public-market tools."""

import numpy as np
import pandas as pd
import pytest

from valuation_platform.market_tools import (
    comparable_implied_prices,
    dcf_sensitivity,
    forward_dcf,
    reverse_dcf,
    reverse_dcf_sensitivity,
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
    assert cases.loc["Bear", "Value Per Share"] < cases.loc["Base", "Value Per Share"]
    assert cases.loc["Base", "Value Per Share"] < cases.loc["Bull", "Value Per Share"]
    reverse_grid = reverse_dcf_sensitivity(80, 100, .025, .09, 5, 10, 20, True, False)
    assert reverse_grid.shape == (3, 3)
    assert np.isfinite(reverse_grid.to_numpy()).all()


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
    assert implied.loc["EV/EBITDA", "Implied Price"] == pytest.approx((1200 - 20) / 10)
    assert np.isfinite(implied["Implied Price"]).all()


def test_comparable_implied_prices_ignores_non_economic_provider_multiples():
    target = pd.Series({
        "EBITDA": 100.0, "Net Income": 80.0, "Revenue": 500.0, "Equity": 250.0,
        "Diluted Shares": 10.0, "Net Debt": 20.0, "Current Price": 25.0,
    })
    peers = pd.DataFrame({
        "EV/EBITDA": [10.0, 12.0, 33000.0],
        "P/E": [18.0, 20.0, 20000.0],
        "P/S": [3.0, 4.0, 5000.0],
        "P/B": [5.0, 6.0, 30000.0],
    })
    implied = comparable_implied_prices(target, peers)
    assert implied.loc["EV/EBITDA", "Peer Median"] == pytest.approx(11.0)
    assert implied.loc["P/E", "Peer Median"] == pytest.approx(19.0)
