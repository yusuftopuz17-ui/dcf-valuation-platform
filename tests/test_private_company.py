"""Private-company DCF methodology tests."""

import numpy as np
import pandas as pd

from valuation_platform.private_company import PrivateCompanyConfig, normalize_history, private_beta, run_private_dcf


def sample_history():
    return pd.DataFrame({"Year": [2023, 2024, 2025], "Revenue": [80e6, 90e6, 100e6], "EBITDA": [14e6, 17e6, 20e6],
                         "EBIT": [11e6, 14e6, 17e6], "Taxes": [2e6, 2.5e6, 3e6], "D&A": [3e6, 3e6, 3e6],
                         "Capex": [4e6, 4.5e6, 5e6], "NWC": [8e6, 9e6, 10e6], "Debt": [20e6, 18e6, 15e6], "Cash": [4e6, 5e6, 6e6]})


def sample_peers():
    return pd.DataFrame({"Levered Beta": [1.0, 1.1, 1.2, 8.0], "Debt": [20, 30, 15, 10], "Equity": [100, 120, 90, 100],
                         "Tax Rate": [.21, .22, .20, .21], "Revenue Growth": [.08, .10, .12, .09],
                         "EBITDA Margin": [.18, .22, .24, .20], "EV/EBITDA": [9, 10, 11, 10]}, index=["A", "B", "C", "OUT"])


def test_only_approved_reasoned_adjustments_are_applied():
    adjustments = pd.DataFrame([{"Year": 2025, "Metric": "EBITDA", "Amount": 1e6, "Reason": "One-time legal expense", "Approved": True},
                                {"Year": 2024, "Metric": "EBIT", "Amount": 9e6, "Reason": "", "Approved": True}])
    normalized, log = normalize_history(sample_history(), adjustments)
    assert normalized.loc[2025, "Normalized EBITDA"] == 21e6
    assert (log["Status"] == "Applied").sum() == 1
    assert log["Status"].str.contains("Rejected").sum() == 1


def test_peer_beta_is_unlevered_cleaned_and_relevered():
    beta, table, exclusions = private_beta(sample_peers(), .21, .20)
    assert 0.8 < beta < 1.4
    assert "Unlevered Beta" in table
    assert "OUT" in exclusions.index


def test_private_dcf_fcff_bridge_and_scenarios():
    result = run_private_dcf(sample_history(), pd.DataFrame(), sample_peers(), PrivateCompanyConfig("ABC"),
                             {"Cash": 6e6, "Debt": 15e6, "Non-operating Assets": 2e6, "Debt-like Liabilities": 1e6})
    assert result["status"] == "valued"
    assert np.allclose(result["forecast"]["FCFF"], result["forecast"]["NOPAT"] + result["forecast"]["D&A"] - result["forecast"]["Capex"] - result["forecast"]["Change in NWC"])
    assert result["dcf"]["Enterprise Value"].gt(0).all()
    assert list(result["scenarios"]["Scenario"]) == ["Bear", "Base", "Bull"]
    assert result["scenarios"]["Equity Value"].is_monotonic_increasing
    assert result["bridge"].iloc[-1]["Adjustment"] == "Equity Value"


def test_no_scale_returns_benchmarks_without_fabricated_value():
    empty = sample_history(); empty[["Revenue", "EBITDA", "EBIT"]] = np.nan
    result = run_private_dcf(empty, pd.DataFrame(), sample_peers(), PrivateCompanyConfig("No Scale"), {"Cash": 0, "Debt": 0})
    assert result["status"] == "benchmarks_only"
    assert "dcf" not in result
    assert result["overall_confidence"] == "Low"
