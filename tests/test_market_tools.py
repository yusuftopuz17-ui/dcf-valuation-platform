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
from valuation_platform.professional_analysis import (
    DEFAULT_SIMILARITY_WEIGHTS,
    comparable_similarity,
    football_field_ranges,
    identify_multiple_outliers,
    peer_multiple_statistics,
    validate_similarity_weights,
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
    assert implied.loc["EV/EBITDA", "Implied Enterprise Value"] == pytest.approx(1200)
    assert implied.loc["EV/EBITDA", "Implied Equity Value"] == pytest.approx(1180)
    assert implied.loc["EV/EBITDA", "Net Debt Adjustment"] == pytest.approx(-20)
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


def test_similarity_excludes_unavailable_criteria_without_fabricating_scores():
    target = {
        "Sector": "Technology", "Subsector": "Software", "Geography": ["United States"],
        "Country": "United States", "Business Model": [], "Customer Structure": [],
        "Revenue Model": [], "Revenue Growth": .20, "EBITDA Margin": .35, "Revenue": 1000,
    }
    peers = pd.DataFrame([
        {
            "Ticker": "GOOD", "Company": "Good Peer", "Sector": "Technology",
            "Subsector": "Software", "Country": "United States", "Business Model": [],
            "Customer Structure": [], "Revenue Model": [], "Revenue Growth": .18,
            "EBITDA Margin": .32, "Revenue": 900,
        },
        {
            "Ticker": "WEAK", "Company": "Weak Peer", "Sector": "Industrials",
            "Subsector": "Machinery", "Country": "Germany", "Business Model": [],
            "Customer Structure": [], "Revenue Model": [], "Revenue Growth": .03,
            "EBITDA Margin": .08, "Revenue": 5000,
        },
    ]).set_index("Ticker")
    scored = comparable_similarity(target, peers, DEFAULT_SIMILARITY_WEIGHTS)
    assert scored.index[0] == "GOOD"
    assert np.isnan(scored.loc["GOOD", "Customer Base Score"])
    assert np.isnan(scored.loc["GOOD", "Revenue Model Score"])
    assert scored.loc["GOOD", "Available Weight"] < 1.0
    assert scored.loc["GOOD", "Overall Similarity"] > scored.loc["WEAK", "Overall Similarity"]
    with pytest.raises(ValueError, match="100%"):
        validate_similarity_weights({**DEFAULT_SIMILARITY_WEIGHTS, "Sector": .10})


def test_peer_statistics_outliers_and_football_ranges():
    peers = pd.DataFrame({
        "EV/EBITDA": [8.0, 9.0, 10.0, 40.0, 11.0],
        "P/E": [18.0, 19.0, 20.0, 21.0, 22.0],
        "P/S": [2.0, 2.5, 3.0, 3.5, 4.0],
        "P/B": [3.0, 3.2, 3.4, 3.6, 3.8],
        "Company": ["A", "B", "C", "Outlier", "D"],
    }, index=["A", "B", "C", "X", "D"])
    statistics = peer_multiple_statistics(peers)
    assert statistics.loc["P/E", "Median"] == pytest.approx(20.0)
    outliers = identify_multiple_outliers(peers)
    assert set(outliers["Ticker"]) == {"X"}

    sensitivity = dcf_sensitivity(100, .10, .025, .09, 5, 10, 20, True, False)
    ranges = football_field_ranges(sensitivity, .09, .025)
    assert set(ranges["Method"]) == {
        "DCF — WACC Sensitivity",
        "DCF — Terminal Growth Sensitivity",
    }
    assert (ranges["Low"] <= ranges["Midpoint"]).all()
    assert (ranges["Midpoint"] <= ranges["High"]).all()
