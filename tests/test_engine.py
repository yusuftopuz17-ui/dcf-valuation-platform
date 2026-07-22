"""Finance-engine and validation tests."""

from dataclasses import replace

import numpy as np
import pytest

from valuation_platform.config import ForecastAssumptions, TerminalAssumptions, ValuationConfig, WACCAssumptions
from valuation_platform.model import dcf, discount_factors, forecast, wacc


def test_configuration_validation():
    with pytest.raises(ValueError): ValuationConfig("BAD TICKER", ["AAA"])
    with pytest.raises(ValueError): ValuationConfig("AAA", ["AAA"])


def test_forecast_dimensions_and_calculations(results):
    model = results["forecast"]
    assert model.shape == (5, 12)
    assert model["Revenue"].iloc[0] == pytest.approx(results["financials"]["Revenue"].iloc[-1] * 1.10)
    assert np.allclose(model["EBITDA"], model["Revenue"] * model["EBITDA Margin"])
    expected = model["NOPAT"] + model["D&A"] - model["Capex"] - model["Change in NWC"]
    assert np.allclose(model["UFCF"], expected)


def test_wacc_formula(results):
    value = results["wacc"]
    assert 0 < value < .30
    assert results["wacc_bridge"].iloc[-1]["Bileşen"] == "WACC"


def test_discount_and_terminal_value(results):
    assert np.allclose(discount_factors(.10, 2, False), [1/1.1, 1/1.1**2])
    result = results["dcf_pg"]; model = results["forecast"]
    expected = model["UFCF"].iloc[-1] * 1.025 / (results["wacc"] - .025)
    assert result["Terminal Value"] == pytest.approx(expected)
    assert result["Equity Value"] == pytest.approx(result["Enterprise Value"] - results["market"]["Net Debt"])


def test_sensitivity_and_scenarios(results):
    assert results["sensitivities"]["WACC / Terminal Growth"].shape == (5, 5)
    assert results["operating_sensitivity"].shape == (5, 5)
    values = results["scenarios"].set_index("Scenario")["Implied Price"]
    assert values["Bear"] < values["Base"] < values["Bull"]


def test_comparable_and_outliers(results):
    assert (results["peer_multiples"]["EV/EBITDA"] > 0).all()
    assert {"25th Percentile", "Median", "75th Percentile"}.issubset(results["implied_values"]["Statistic"])
    assert len(results["football"]) >= 4

