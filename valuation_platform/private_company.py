"""Transparent private-company FCFF valuation workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class PrivateCompanyConfig:
    company_name: str
    currency: str = "USD"
    forecast_years: int = 5
    tax_rate: float = 0.21
    risk_free_rate: float = 0.04
    equity_risk_premium: float = 0.055
    country_risk_premium: float = 0.0
    additional_risk_adjustment: float = 0.0
    pre_tax_cost_of_debt: float = 0.06
    target_debt_weight: float = 0.20
    terminal_growth_rate: float = 0.025
    exit_multiple: float | None = None
    mid_year_discounting: bool = True

    def validate(self) -> None:
        if not self.company_name.strip():
            raise ValueError("Özel şirket adı zorunludur.")
        if not 3 <= self.forecast_years <= 10:
            raise ValueError("Tahmin dönemi 3-10 yıl olmalıdır.")
        if not 0 <= self.tax_rate <= 0.60 or not 0 <= self.target_debt_weight < 0.95:
            raise ValueError("Vergi ve hedef borç ağırlığı geçersizdir.")
        if self.terminal_growth_rate >= 0.20:
            raise ValueError("Terminal büyüme oranı savunulabilir bir aralıkta olmalıdır.")


def normalize_history(history: pd.DataFrame, adjustments: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply only user-approved, reasoned normalizations and preserve reported data."""
    required = ["Year", "Revenue", "EBITDA", "EBIT", "Taxes", "D&A", "Capex", "NWC", "Debt", "Cash"]
    frame = history.copy()
    for column in required:
        if column not in frame:
            frame[column] = np.nan
    frame = frame[required].copy()
    frame["Year"] = pd.to_numeric(frame["Year"], errors="coerce")
    for column in required[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["Year"]).sort_values("Year").set_index("Year")
    normalized = frame.copy()
    log_rows: list[dict[str, Any]] = []
    if adjustments is not None and not adjustments.empty:
        for row in adjustments.to_dict("records"):
            year = pd.to_numeric(row.get("Year"), errors="coerce")
            metric = str(row.get("Metric", "")).strip()
            amount = pd.to_numeric(row.get("Amount"), errors="coerce")
            reason = str(row.get("Reason", "")).strip()
            approved = bool(row.get("Approved", False))
            valid = approved and year in normalized.index and metric in normalized.columns and np.isfinite(amount) and bool(reason)
            if valid:
                before = normalized.loc[year, metric]
                normalized.loc[year, metric] = before + amount
                log_rows.append({"Year": int(year), "Metric": metric, "Adjustment": amount, "Reason": reason,
                                 "Reported": before, "Normalized": normalized.loc[year, metric], "Status": "Applied"})
            elif approved:
                log_rows.append({"Year": year, "Metric": metric, "Adjustment": amount, "Reason": reason,
                                 "Reported": np.nan, "Normalized": np.nan, "Status": "Rejected - incomplete justification or invalid field"})
    reported = frame.add_prefix("Reported ")
    normalized = normalized.add_prefix("Normalized ")
    return pd.concat([reported, normalized], axis=1), pd.DataFrame(log_rows)


def private_beta(peer_data: pd.DataFrame, tax_rate: float, target_debt_weight: float) -> tuple[float, pd.DataFrame, pd.DataFrame]:
    """Unlever peer betas, remove invalid/IQR outliers, and relever to the target structure."""
    peers = peer_data.copy()
    for column in ["Levered Beta", "Debt", "Equity", "Tax Rate"]:
        peers[column] = pd.to_numeric(peers.get(column), errors="coerce")
    peers["Debt / Equity"] = peers["Debt"] / peers["Equity"]
    peers["Unlevered Beta"] = peers["Levered Beta"] / (1 + (1 - peers["Tax Rate"].fillna(tax_rate)) * peers["Debt / Equity"])
    invalid = (~np.isfinite(peers["Unlevered Beta"])) | (peers["Unlevered Beta"] <= 0) | (peers["Equity"] <= 0)
    valid = peers.loc[~invalid, "Unlevered Beta"]
    if valid.empty:
        raise ValueError("Benzer şirketlerden geçerli beta hesaplanamadı.")
    q1, q3 = valid.quantile([.25, .75]); iqr = q3 - q1
    outlier = (peers["Unlevered Beta"] < q1 - 1.5 * iqr) | (peers["Unlevered Beta"] > q3 + 1.5 * iqr) if iqr > 0 else False
    included = ~(invalid | outlier)
    peers["Status"] = np.where(invalid, "Excluded - invalid data", np.where(outlier, "Excluded - IQR outlier", "Included"))
    clean = peers.loc[included, "Unlevered Beta"]
    median_unlevered = float(clean.median())
    target_de = target_debt_weight / (1 - target_debt_weight)
    relevered = median_unlevered * (1 + (1 - tax_rate) * target_de)
    exclusions = peers.loc[~included, ["Levered Beta", "Debt / Equity", "Tax Rate", "Unlevered Beta", "Status"]]
    return float(relevered), peers, exclusions


def derive_operating_assumptions(normalized_history: pd.DataFrame, peers: pd.DataFrame, config: PrivateCompanyConfig,
                                 overrides: dict[str, float] | None = None) -> pd.DataFrame:
    """Derive editable assumptions with source and confidence labels."""
    overrides = overrides or {}
    h = normalized_history.filter(like="Normalized ").copy()
    h.columns = h.columns.str.replace("Normalized ", "", regex=False)
    revenue = h["Revenue"].dropna()
    growth = revenue.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    hist_margin = (h["EBITDA"] / h["Revenue"]).replace([np.inf, -np.inf], np.nan).dropna()
    peer_growth = pd.to_numeric(peers.get("Revenue Growth"), errors="coerce").dropna()
    peer_margin = pd.to_numeric(peers.get("EBITDA Margin"), errors="coerce").dropna()
    def estimate(name: str, company_value: float, peer_value: float, fallback: float, source_company: str) -> dict[str, Any]:
        if name in overrides and np.isfinite(overrides[name]):
            return {"Assumption": name, "Value": float(overrides[name]), "Source": "Manually adjusted", "Confidence": "Medium"}
        if np.isfinite(company_value):
            return {"Assumption": name, "Value": float(company_value), "Source": source_company, "Confidence": "High" if len(revenue) >= 3 else "Medium"}
        if np.isfinite(peer_value):
            return {"Assumption": name, "Value": float(peer_value), "Source": "Comparable-company-derived", "Confidence": "Medium"}
        return {"Assumption": name, "Value": float(fallback), "Source": "Sector-derived fallback", "Confidence": "Low"}
    latest_growth = growth.iloc[-1] if not growth.empty else np.nan
    hist_growth = growth.median() if not growth.empty else np.nan
    start_growth = np.nanmean([latest_growth, hist_growth, peer_growth.median()]) if any(np.isfinite(x) for x in [latest_growth, hist_growth, peer_growth.median()]) else np.nan
    mature_margin = np.nanmean([hist_margin.median(), peer_margin.median()]) if any(np.isfinite(x) for x in [hist_margin.median(), peer_margin.median()]) else np.nan
    ratios = {}
    for metric, default in [("D&A", .03), ("Capex", .04), ("NWC", .05)]:
        series = (h[metric] / h["Revenue"]).replace([np.inf, -np.inf], np.nan).dropna()
        ratios[metric] = (series.median() if not series.empty else np.nan, default)
    rows = [
        estimate("Initial Revenue Growth", start_growth, peer_growth.median(), .05, "Company-specific / comparable blended"),
        estimate("Mature Revenue Growth", min(config.terminal_growth_rate + .02, start_growth) if np.isfinite(start_growth) else np.nan,
                 peer_growth.median(), .04, "Company-specific mean reversion"),
        estimate("Initial EBITDA Margin", hist_margin.iloc[-1] if not hist_margin.empty else np.nan, peer_margin.median(), .15, "Company-specific"),
        estimate("Mature EBITDA Margin", mature_margin, peer_margin.median(), .15, "Company-specific / comparable convergence"),
        estimate("D&A / Revenue", ratios["D&A"][0], np.nan, ratios["D&A"][1], "Company-specific"),
        estimate("Capex / Revenue", ratios["Capex"][0], np.nan, ratios["Capex"][1], "Company-specific"),
        estimate("NWC / Revenue", ratios["NWC"][0], np.nan, ratios["NWC"][1], "Company-specific"),
    ]
    return pd.DataFrame(rows).set_index("Assumption")


def run_private_dcf(history: pd.DataFrame, adjustments: pd.DataFrame, peers: pd.DataFrame, config: PrivateCompanyConfig,
                    balance_adjustments: dict[str, float], overrides: dict[str, float] | None = None,
                    shareholder_adjustment: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run a private-company DCF or return benchmarks only when no scale input exists."""
    config.validate()
    normalized, adjustment_log = normalize_history(history, adjustments)
    assumptions = derive_operating_assumptions(normalized, peers, config, overrides)
    h = normalized.filter(like="Normalized ").copy(); h.columns = h.columns.str.replace("Normalized ", "", regex=False)
    scale_available = h[["Revenue", "EBITDA", "EBIT"]].notna().any().any() and (h[["Revenue", "EBITDA", "EBIT"]].fillna(0).abs().sum().sum() > 0)
    if not scale_available:
        return {"status": "benchmarks_only", "normalized_history": normalized, "adjustment_log": adjustment_log,
                "assumptions": assumptions, "peers": peers, "warning": "Monetary valuation requires current Revenue, EBITDA, EBIT, FCFF, or a credible forecast.",
                "overall_confidence": "Low"}
    latest = h.dropna(how="all").iloc[-1]
    peer_margin = pd.to_numeric(peers.get("EBITDA Margin"), errors="coerce").median()
    if not np.isfinite(latest.get("Revenue", np.nan)) or latest.get("Revenue", 0) <= 0:
        if np.isfinite(latest.get("EBITDA", np.nan)) and latest["EBITDA"] > 0 and np.isfinite(peer_margin) and peer_margin > 0:
            latest["Revenue"] = latest["EBITDA"] / peer_margin
            inferred_revenue = True
        else:
            raise ValueError("Parasal değerleme için güncel hasılat veya hasılatı türetecek güvenilir EBITDA gereklidir.")
    else:
        inferred_revenue = False
    if not np.isfinite(latest.get("EBITDA", np.nan)):
        latest["EBITDA"] = latest["Revenue"] * assumptions.loc["Initial EBITDA Margin", "Value"]
    beta, beta_table, beta_exclusions = private_beta(peers, config.tax_rate, config.target_debt_weight)
    cost_equity_base = config.risk_free_rate + beta * config.equity_risk_premium + config.country_risk_premium
    cost_equity = cost_equity_base + config.additional_risk_adjustment
    after_tax_debt = config.pre_tax_cost_of_debt * (1 - config.tax_rate)
    wacc_base = (1 - config.target_debt_weight) * cost_equity_base + config.target_debt_weight * after_tax_debt
    wacc = (1 - config.target_debt_weight) * cost_equity + config.target_debt_weight * after_tax_debt
    if wacc <= config.terminal_growth_rate:
        raise ValueError("WACC terminal büyüme oranından büyük olmalıdır.")
    years = pd.Index(range(1, config.forecast_years + 1), name="Forecast Year")
    growth = np.linspace(assumptions.loc["Initial Revenue Growth", "Value"], assumptions.loc["Mature Revenue Growth", "Value"], config.forecast_years)
    margins = np.linspace(assumptions.loc["Initial EBITDA Margin", "Value"], assumptions.loc["Mature EBITDA Margin", "Value"], config.forecast_years)
    revenue = latest["Revenue"] * np.cumprod(1 + growth); ebitda = revenue * margins
    da = revenue * assumptions.loc["D&A / Revenue", "Value"]; ebit = ebitda - da
    nopat = ebit * (1 - config.tax_rate); capex = revenue * assumptions.loc["Capex / Revenue", "Value"]
    nwc = revenue * assumptions.loc["NWC / Revenue", "Value"]
    opening_nwc = latest.get("NWC", 0) if np.isfinite(latest.get("NWC", np.nan)) else 0
    change_nwc = np.diff(np.r_[opening_nwc, nwc]); fcff = nopat + da - capex - change_nwc
    forecast = pd.DataFrame({"Revenue Growth": growth, "Revenue": revenue, "EBITDA Margin": margins, "EBITDA": ebitda,
                             "D&A": da, "EBIT": ebit, "Tax Rate": config.tax_rate, "NOPAT": nopat, "Capex": capex,
                             "NWC": nwc, "Change in NWC": change_nwc, "FCFF": fcff}, index=years)
    periods = np.arange(1, config.forecast_years + 1) - (0.5 if config.mid_year_discounting else 0)
    factors = 1 / (1 + wacc) ** periods; pv_fcff = fcff * factors
    tv_pg = fcff[-1] * (1 + config.terminal_growth_rate) / (wacc - config.terminal_growth_rate)
    cleaned_exit = pd.to_numeric(peers.get("EV/EBITDA"), errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    exit_multiple = config.exit_multiple if config.exit_multiple is not None else float(cleaned_exit.median())
    tv_exit = ebitda[-1] * exit_multiple
    pv_tv_pg = tv_pg * factors[-1]; pv_tv_exit = tv_exit * factors[-1]
    ev_pg = float(pv_fcff.sum() + pv_tv_pg); ev_exit = float(pv_fcff.sum() + pv_tv_exit)
    cash = float(balance_adjustments.get("Cash", 0)); nonop = float(balance_adjustments.get("Non-operating Assets", 0))
    debt = float(balance_adjustments.get("Debt", 0)); debt_like = float(balance_adjustments.get("Debt-like Liabilities", 0))
    bridge = pd.DataFrame({"Adjustment": ["Enterprise Value", "Cash and Cash Equivalents", "Non-operating Assets", "Interest-bearing Debt", "Debt-like Liabilities"],
                           "Perpetuity Growth": [ev_pg, cash, nonop, -debt, -debt_like], "Exit Multiple": [ev_exit, cash, nonop, -debt, -debt_like]})
    equity_pg = ev_pg + cash + nonop - debt - debt_like; equity_exit = ev_exit + cash + nonop - debt - debt_like
    bridge.loc[len(bridge)] = ["Equity Value", equity_pg, equity_exit]
    adjustment = shareholder_adjustment or {"enabled": False, "percent": 0.0, "reason": ""}
    selected_equity = float(np.median([equity_pg, equity_exit])); adjusted_equity = selected_equity
    if adjustment.get("enabled"):
        adjusted_equity *= 1 + float(adjustment.get("percent", 0))
    hist_years = int(h["Revenue"].notna().sum()); estimated_count = int((assumptions["Confidence"] == "Low").sum())
    overall_confidence = "High" if hist_years >= 3 and estimated_count == 0 else ("Medium" if hist_years >= 2 and estimated_count <= 2 else "Low")
    peer_growth_dispersion = pd.to_numeric(peers.get("Revenue Growth"), errors="coerce").std()
    hist_growth_dispersion = h["Revenue"].pct_change().std()
    growth_shock = float(np.nanmedian([peer_growth_dispersion, hist_growth_dispersion, .02])); growth_shock = float(np.clip(growth_shock, .01, .08))
    margin_shock = float(np.clip(pd.to_numeric(peers.get("EBITDA Margin"), errors="coerce").std(), .01, .08))
    wacc_shock = .01 if overall_confidence != "Low" else .02
    scenario_rows = []
    for name, sign in [("Bear", -1), ("Base", 0), ("Bull", 1)]:
        case_growth = growth + sign * growth_shock; case_margin = margins + sign * margin_shock
        case_revenue = latest["Revenue"] * np.cumprod(1 + case_growth); case_ebitda = case_revenue * case_margin
        case_fcff = case_ebitda * (1 - config.tax_rate) + case_revenue * assumptions.loc["D&A / Revenue", "Value"] * config.tax_rate - case_revenue * assumptions.loc["Capex / Revenue", "Value"] - np.diff(np.r_[opening_nwc, case_revenue * assumptions.loc["NWC / Revenue", "Value"]])
        case_wacc = wacc - sign * wacc_shock; case_g = config.terminal_growth_rate + sign * min(growth_shock / 4, .01)
        case_factors = 1 / (1 + case_wacc) ** periods
        case_tv = case_fcff[-1] * (1 + case_g) / (case_wacc - case_g)
        case_ev = float((case_fcff * case_factors).sum() + case_tv * case_factors[-1])
        scenario_rows.append({"Scenario": name, "Growth Shift": sign * growth_shock, "Margin Shift": sign * margin_shock,
                              "WACC": case_wacc, "Terminal Growth": case_g, "Enterprise Value": case_ev,
                              "Equity Value": case_ev + cash + nonop - debt - debt_like})
    scenarios = pd.DataFrame(scenario_rows)
    wacc_grid = np.linspace(max(config.terminal_growth_rate + .01, wacc - .02), wacc + .02, 5)
    growth_grid = np.linspace(config.terminal_growth_rate - .01, config.terminal_growth_rate + .01, 5)
    sensitivity = pd.DataFrame(index=pd.Index(wacc_grid, name="WACC"), columns=pd.Index(growth_grid, name="Terminal Growth"), dtype=float)
    for wr in wacc_grid:
        wf = 1 / (1 + wr) ** periods
        for tg in growth_grid:
            sensitivity.loc[wr, tg] = (fcff * wf).sum() + fcff[-1] * (1 + tg) / (wr - tg) * wf[-1] if wr > tg else np.nan
    wacc_table = pd.DataFrame({"Component": ["Risk-free Rate", "Relevered Beta", "Equity Risk Premium", "Country Risk Premium", "Additional Risk Adjustment", "Cost of Equity", "After-tax Cost of Debt", "Target Debt Weight", "WACC without Additional Risk", "WACC"],
                               "Value": [config.risk_free_rate, beta, config.equity_risk_premium, config.country_risk_premium,
                                         config.additional_risk_adjustment, cost_equity, after_tax_debt, config.target_debt_weight, wacc_base, wacc],
                               "Source": ["Macro-derived", "Comparable-company-derived", "Macro-derived", "Macro-derived", "Manually adjusted" if config.additional_risk_adjustment else "Not applied", "Calculated", "Company/benchmark-derived", "Comparable/target-derived", "Calculated", "Calculated"]})
    return {"status": "valued", "normalized_history": normalized, "adjustment_log": adjustment_log, "assumptions": assumptions,
            "peers": peers,
            "forecast": forecast, "beta": beta, "beta_table": beta_table, "beta_exclusions": beta_exclusions,
            "wacc": wacc, "wacc_base": wacc_base, "wacc_table": wacc_table, "exit_multiple": exit_multiple,
            "dcf": pd.DataFrame([{"Method": "Perpetuity Growth", "Terminal Value": tv_pg, "PV Terminal Value": pv_tv_pg, "Enterprise Value": ev_pg, "Equity Value": equity_pg, "Terminal Value % EV": pv_tv_pg / ev_pg},
                                  {"Method": "Exit Multiple", "Terminal Value": tv_exit, "PV Terminal Value": pv_tv_exit, "Enterprise Value": ev_exit, "Equity Value": equity_exit, "Terminal Value % EV": pv_tv_exit / ev_exit}]),
            "bridge": bridge, "scenarios": scenarios, "sensitivity": sensitivity, "overall_confidence": overall_confidence,
            "confidence_factors": {"Historical years": hist_years, "Low-confidence assumptions": estimated_count, "Revenue inferred": inferred_revenue},
            "shareholder_adjustment": {**adjustment, "Value before adjustment": selected_equity, "Value after adjustment": adjusted_equity},
            "warning": "Private-company value is model-derived, unaudited, and not investment advice."}
