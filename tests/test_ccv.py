"""Deterministic CCV workflow tests."""

import numpy as np
import pandas as pd
import pytest

from src.ccv_reporting import build_ccv_csv, build_ccv_excel, build_ccv_pdf
from src import ccv_provider
from valuation_platform.ccv import (
    DEFAULT_WEIGHTS, SECTOR_TAXONOMY, ValuationProject, apply_boundaries, calculate_multiples,
    clean_outliers, enterprise_value, implied_valuations, normalize_value, rank_peers, run_ccv,
    similarity_scores, summary_statistics, validate_boundaries, validate_weights,
)


def candidates():
    rows = []
    for i, ticker in enumerate(["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]):
        rows.append({
            "Ticker": ticker, "Company": f"Company {ticker}", "Exchange": "NASDAQ", "Country": "US",
            "Sector": "Technology", "Subsector": "Software", "Business Model": ["SaaS"],
            "Customer Structure": ["B2B"], "Geography": ["North America"], "Revenue Model": ["Subscription"],
            "Business Description": "Business software", "Revenue": 100 + i * 10, "EBITDA": 20 + i,
            "EBIT": 15 + i, "Net Income": 10 + i, "Revenue Growth": .08 + i * .005,
            "EBITDA Margin": (20 + i) / (100 + i * 10), "Market Cap": 300 + i * 20,
            "Enterprise Value": 320 + i * 20, "Data Source": "Verified Test Provider",
            "Source URL": f"https://example.test/{ticker}", "Financial Period": "TTM",
            "Retrieved At": "2026-07-23T00:00:00+00:00",
        })
    return pd.DataFrame(rows).set_index("Ticker")


def target():
    return {"Company": "Target", "Ticker": "PRIVATE", "Sector": "Technology", "Subsector": "Software",
            "Business Model": ["SaaS"], "Customer Structure": ["B2B"], "Geography": ["North America"],
            "Revenue Model": ["Subscription"], "Revenue": 120.0, "EBITDA": 24.0, "EBIT": 18.0,
            "Net Income": 12.0, "Revenue Growth": .10, "EBITDA Margin": .20,
            "Diluted Shares": 10.0, "Currency": "USD"}


def test_taxonomy_dependencies_and_other_is_last():
    assert SECTOR_TAXONOMY["Technology"] == ["Software", "Managed IT Services", "IT Solutions", "Other"]
    assert list(SECTOR_TAXONOMY)[-1] == "Other"
    assert all(values[-1] == "Other" for values in SECTOR_TAXONOMY.values())


def test_currency_unit_normalization_and_boundary_validation():
    assert normalize_value(2.5, "millions") == 2_500_000
    validate_boundaries({"min_Revenue": 10, "max_Revenue": 10})
    with pytest.raises(ValueError):
        validate_boundaries({"min_Revenue": 11, "max_Revenue": 10})


def test_currency_mismatch_is_rejected_when_monetary_boundary_is_active():
    frame = candidates()
    frame["Currency"] = ["USD", "EUR", "USD", "USD", "USD", "USD"]
    accepted, rejected = apply_boundaries(frame, {"min_Revenue": 1, "currency_Revenue": "USD"})
    assert "BBB" not in accepted.index
    assert "FX dönüşümü uygulanmadı" in rejected.loc["BBB", "Rejection Reason"]


def test_similarity_weights_must_total_one():
    validate_weights(DEFAULT_WEIGHTS)
    with pytest.raises(ValueError):
        validate_weights({**DEFAULT_WEIGHTS, "Sector": .20})


def test_enterprise_value_formula():
    assert enterprise_value(100, debt=30, preferred=4, nci=2, cash=10) == 126


def test_negative_metrics_are_non_meaningful():
    frame = candidates().iloc[:2].copy()
    frame.loc["AAA", ["EBITDA", "EBIT", "Net Income"]] = [-1, 0, -2]
    result = calculate_multiples(frame)
    assert np.isnan(result.loc["AAA", "EV/EBITDA"])
    assert np.isnan(result.loc["AAA", "EV/EBIT"])
    assert np.isnan(result.loc["AAA", "P/E"])
    assert np.isfinite(result.loc["AAA", "EV/Revenue"])


def test_similarity_is_deterministic_and_ranked():
    first = similarity_scores(target(), candidates(), DEFAULT_WEIGHTS)
    second = similarity_scores(target(), candidates(), DEFAULT_WEIGHTS)
    pd.testing.assert_frame_equal(first, second)
    assert first["Similarity Score"].between(0, 1).all()


def test_manual_inclusion_exclusion_and_strict_boundary():
    frame = calculate_multiples(candidates())
    selected, rejected = rank_peers(target(), frame, {"min_Revenue": 130}, DEFAULT_WEIGHTS, 3, 0,
                                    include=["FFF"], exclude=["DDD"], locked=["EEE"])
    assert "FFF" in selected.index and "EEE" in selected.index
    assert "DDD" in rejected.index
    assert "AAA" in rejected.index


def test_iqr_outlier_detection_and_summary_statistics():
    frame = calculate_multiples(candidates())
    frame.loc["FFF", "EV/EBITDA"] = 100
    clean, audit, bounds = clean_outliers(frame, "IQR", 1.5)
    assert np.isnan(clean.loc["FFF", "EV/EBITDA"])
    assert ((audit["Ticker"] == "FFF") & (audit["Multiple"] == "EV/EBITDA")).any()
    stats = summary_statistics(clean)
    assert stats.loc["EV/EBITDA", "Median"] == clean["EV/EBITDA"].median()
    assert bounds.loc["EV/EBITDA", "Excluded"] == 1


def test_winsorization_caps_observations_without_deleting_them():
    frame = calculate_multiples(candidates())
    frame.loc["FFF", "EV/Revenue"] = 100
    clean, audit, _ = clean_outliers(frame, "Winsorization", 1.5)
    assert clean["EV/Revenue"].notna().sum() == frame["EV/Revenue"].notna().sum()
    assert clean.loc["FFF", "EV/Revenue"] < 100
    assert audit.empty


def test_implied_ev_equity_bridge_and_per_share():
    stats = summary_statistics(calculate_multiples(candidates()))
    implied = implied_valuations(stats, target(), {"Cash": 5, "Debt": 20, "Preferred Equity": 2,
                                                   "Non-Controlling Interest": 1,
                                                   "Other Non-operating Assets": 3, "Debt-like Liabilities": 4})
    row = implied[(implied["Multiple"] == "EV/EBITDA") & (implied["Statistic"] == "Median")].iloc[0]
    assert row["Implied Equity Value"] == pytest.approx(row["Implied Enterprise Value"] + 5 - 20 - 2 - 1 + 3 - 4)
    assert row["Implied Value Per Share"] == pytest.approx(row["Implied Equity Value"] / 10)


def test_missing_bridge_keeps_enterprise_value_only():
    stats = summary_statistics(calculate_multiples(candidates()))
    implied = implied_valuations(stats, target(), {"Cash": None, "Debt": None})
    row = implied[(implied["Multiple"] == "EV/Revenue") & (implied["Statistic"] == "Median")].iloc[0]
    assert np.isfinite(row["Implied Enterprise Value"])
    assert np.isnan(row["Implied Equity Value"])


def test_description_only_private_company_has_no_monetary_value():
    project = ValuationProject(selected_method="Comparable Companies", company_type="Private")
    result = run_ccv({"Company": "Description Only", "Sector": "Technology", "Subsector": "Software"},
                     candidates(), project, {"Cash": None, "Debt": None})
    assert result["implied_valuations"].empty


def test_empty_candidate_universe_has_clear_error():
    project = ValuationProject(selected_method="Comparable Companies", company_type="Public")
    with pytest.raises(ValueError, match="Doğrulanmış aday şirket bulunamadı"):
        run_ccv(target(), pd.DataFrame(), project, {"Cash": 0, "Debt": 0})


def test_fully_filtered_candidate_universe_has_clear_error():
    project = ValuationProject(selected_method="Comparable Companies", company_type="Public")
    project.boundaries = {"min_Revenue": 1_000_000}
    with pytest.raises(ValueError, match="kullanılabilir benzer şirket kalmadı"):
        run_ccv(target(), candidates(), project, {"Cash": 0, "Debt": 0})


def test_private_company_with_revenue_and_ebitda_uses_only_applicable_metrics():
    project = ValuationProject(selected_method="Comparable Companies", company_type="Private")
    partial = {**target(), "EBIT": None, "Net Income": None}
    result = run_ccv(partial, candidates(), project, {"Cash": None, "Debt": None})
    assert set(result["implied_valuations"]["Multiple"]) == {"EV/Revenue", "EV/EBITDA"}


def test_complete_workflow_and_report_outputs():
    project = ValuationProject(selected_method="Comparable Companies", company_type="Public")
    project.manual_overrides = {"target_peer_count": 5, "minimum_similarity": .2, "period": "TTM"}
    project.target_identity = target()
    result = run_ccv(target(), candidates(), project, {"Cash": 5, "Debt": 20, "Preferred Equity": 0,
                                                       "Non-Controlling Interest": 0,
                                                       "Other Non-operating Assets": 0, "Debt-like Liabilities": 0})
    assert len(result["selected_peers"]) == 5
    assert result["confidence"]["Level"] in {"High", "Medium", "Low"}
    assert len(build_ccv_excel(result)) > 1_000
    assert len(build_ccv_csv(result)) > 500
    assert len(build_ccv_pdf(result)) > 1_000


def test_provider_failure_is_visible_and_does_not_fabricate(monkeypatch):
    def fake_company(ticker, years, period):
        if ticker == "FAIL":
            raise RuntimeError("rate limited")
        return {"record": {**candidates().loc["AAA"].to_dict(), "Ticker": ticker}, "historical": pd.DataFrame()}
    monkeypatch.setattr(ccv_provider, "company_record", fake_company)
    frame, failures, _ = ccv_provider.load_candidate_records(["GOOD", "FAIL"])
    assert list(frame.index) == ["GOOD"]
    assert failures.iloc[0]["Ticker"] == "FAIL"
    assert "rate limited" in failures.iloc[0]["Error"]


def test_project_round_trip_preserves_navigation_state():
    project = ValuationProject(selected_method="Comparable Companies", company_type="Private", active_ccv_page="Benzer Şirketler")
    restored = ValuationProject.from_dict(project.to_dict())
    assert restored.selected_method == "Comparable Companies"
    assert restored.company_type == "Private"
    assert restored.active_ccv_page == "Benzer Şirketler"
