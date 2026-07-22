"""Core historical, forecast, WACC, DCF, comparable, and scenario calculations."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np
import pandas as pd

from .config import ForecastAssumptions, TerminalAssumptions, WACCAssumptions


def divide(a: Any, b: Any) -> Any:
    a_arr, b_arr = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    shape = np.broadcast_shapes(a_arr.shape, b_arr.shape)
    out = np.full(shape, np.nan)
    np.divide(a_arr, b_arr, out=out, where=np.isfinite(b_arr) & (b_arr != 0))
    return float(out) if out.ndim == 0 else out


def historical_metrics(f: pd.DataFrame) -> pd.DataFrame:
    """Calculate operating, return, cash-conversion, and leverage metrics."""
    m = pd.DataFrame(index=f.index)
    m["Revenue Growth"] = f["Revenue"].pct_change()
    m["EBITDA Growth"] = f["EBITDA"].pct_change()
    m["Gross Margin"] = divide(f["Gross Profit"], f["Revenue"])
    m["EBITDA Margin"] = divide(f["EBITDA"], f["Revenue"])
    m["EBIT Margin"] = divide(f["EBIT"], f["Revenue"])
    m["Net Margin"] = divide(f["Net Income"], f["Revenue"])
    effective_tax = pd.Series(divide(f["Tax Expense"], f["EBIT"]), index=f.index).clip(0, 0.5).fillna(0.21)
    m["Effective Tax Rate"] = effective_tax
    m["Capex Intensity"] = divide(f["Capital Expenditure"], f["Revenue"])
    m["D&A Intensity"] = divide(f["D&A"], f["Revenue"])
    m["NWC Intensity"] = divide(f["NWC"], f["Revenue"])
    m["Free Cash Flow"] = f["EBIT"] * (1 - effective_tax) + f["D&A"] - f["Capital Expenditure"] - f["NWC"].diff()
    m["FCF Margin"] = divide(m["Free Cash Flow"], f["Revenue"])
    invested = f["Debt"] + f["Equity"] - f["Cash"]
    m["ROIC"] = divide(f["EBIT"] * (1 - effective_tax), invested.rolling(2).mean())
    m["Net Debt"] = f["Net Debt"]
    m["Net Debt / EBITDA"] = divide(f["Net Debt"], f["EBITDA"])
    m["Interest Coverage"] = divide(f["EBIT"], f["Interest Expense"].abs())
    m["Cash Conversion"] = divide(m["Free Cash Flow"], f["Net Income"])
    return m


def forecast(last: pd.Series, assumptions: ForecastAssumptions, years: int) -> pd.DataFrame:
    """Forecast revenue through unlevered free cash flow."""
    assumptions.validate(years)
    index = pd.Index(range(pd.Timestamp(last.name).year + 1, pd.Timestamp(last.name).year + years + 1), name="Fiscal Year")
    growth = np.asarray(assumptions.revenue_growth)
    revenue = float(last["Revenue"]) * np.cumprod(1 + growth)
    margin = np.asarray(assumptions.ebitda_margin)
    ebitda = revenue * margin
    da = revenue * assumptions.depreciation_as_percent_revenue
    ebit = ebitda - da
    taxes = np.maximum(ebit, 0) * assumptions.tax_rate
    nopat = ebit - taxes
    capex = revenue * assumptions.capex_as_percent_revenue
    nwc = revenue * assumptions.nwc_as_percent_revenue
    opening_nwc = float(last.get("NWC", 0))
    delta_nwc = np.diff(np.r_[opening_nwc, nwc])
    ufcf = nopat + da - capex - delta_nwc
    return pd.DataFrame({"Revenue Growth": growth, "Revenue": revenue, "EBITDA Margin": margin,
                         "EBITDA": ebitda, "D&A": da, "EBIT": ebit, "Tax Rate": assumptions.tax_rate,
                         "NOPAT": nopat, "Capex": capex, "NWC": nwc, "Change in NWC": delta_nwc,
                         "UFCF": ufcf}, index=index)


def wacc(assumptions: WACCAssumptions, beta: float, market_cap: float, debt: float, tax_rate: float) -> tuple[float, pd.DataFrame]:
    """Calculate current or target-capital-structure WACC and bridge."""
    selected_beta = assumptions.beta if assumptions.beta is not None else beta
    if not np.isfinite(selected_beta) or selected_beta <= 0 or market_cap <= 0 or debt < 0:
        raise ValueError("WACC için beta, piyasa değeri veya borç verisi geçersiz.")
    cost_equity = assumptions.risk_free_rate + selected_beta * assumptions.equity_risk_premium + assumptions.country_risk_premium
    after_tax_debt = assumptions.pre_tax_cost_of_debt * (1 - tax_rate)
    debt_weight = assumptions.target_debt_weight if assumptions.target_debt_weight is not None else debt / (market_cap + debt)
    equity_weight = 1 - debt_weight
    result = equity_weight * cost_equity + debt_weight * after_tax_debt
    bridge = pd.DataFrame({"Bileşen": ["Risksiz Faiz", "Beta x Hisse Risk Primi", "Ülke Risk Primi", "Özsermaye Maliyeti", "Vergi Sonrası Borç Maliyeti", "WACC"],
                           "Oran": [assumptions.risk_free_rate, selected_beta * assumptions.equity_risk_premium,
                                    assumptions.country_risk_premium, cost_equity, after_tax_debt, result],
                           "Ağırlık": [np.nan, np.nan, np.nan, equity_weight, debt_weight, 1.0],
                           "Katkı": [assumptions.risk_free_rate, selected_beta * assumptions.equity_risk_premium,
                                     assumptions.country_risk_premium, equity_weight * cost_equity, debt_weight * after_tax_debt, result]})
    return float(result), bridge


def discount_factors(rate: float, years: int, mid_year: bool) -> np.ndarray:
    periods = np.arange(1, years + 1) - (0.5 if mid_year else 0)
    return 1 / (1 + rate) ** periods


def dcf(model: pd.DataFrame, rate: float, terminal: TerminalAssumptions, market: dict[str, Any], mid_year: bool, method: str) -> dict[str, Any]:
    """Perform perpetuity-growth or exit-multiple DCF valuation."""
    factors = discount_factors(rate, len(model), mid_year)
    pv_ufcf = model["UFCF"].to_numpy() * factors
    if method == "perpetuity":
        if rate <= terminal.terminal_growth_rate:
            raise ValueError("WACC terminal büyüme oranından büyük olmalıdır.")
        tv = model["UFCF"].iloc[-1] * (1 + terminal.terminal_growth_rate) / (rate - terminal.terminal_growth_rate)
    elif method == "exit_multiple":
        tv = model["EBITDA"].iloc[-1] * terminal.exit_ebitda_multiple
    else:
        raise ValueError("Geçersiz terminal değer yöntemi.")
    pv_tv = float(tv * factors[-1]); enterprise = float(pv_ufcf.sum() + pv_tv)
    equity = enterprise - market["Debt"] + market["Cash"]
    implied = equity / market["Shares"]
    return {"Method": method, "WACC": rate, "Terminal Growth": terminal.terminal_growth_rate,
            "Exit Multiple": terminal.exit_ebitda_multiple, "PV Forecast UFCF": float(pv_ufcf.sum()),
            "Terminal Value": float(tv), "PV Terminal Value": pv_tv, "Enterprise Value": enterprise,
            "Net Debt": market["Net Debt"], "Equity Value": equity, "Diluted Shares": market["Shares"],
            "Implied Price": implied, "Current Price": market["Current Price"],
            "Upside": implied / market["Current Price"] - 1, "Terminal Value % EV": pv_tv / enterprise,
            "Discount Factors": factors, "PV UFCF": pv_ufcf}


def sensitivities(model: pd.DataFrame, base_wacc: float, terminal: TerminalAssumptions, market: dict[str, Any], mid_year: bool) -> dict[str, pd.DataFrame]:
    """Create fully recalculated DCF sensitivity grids."""
    rates = np.linspace(max(0.01, base_wacc - 0.02), base_wacc + 0.02, 5)
    growths = np.minimum(np.linspace(terminal.terminal_growth_rate - 0.01, terminal.terminal_growth_rate + 0.01, 5), rates.min() - 0.001)
    multiples = np.linspace(max(1, terminal.exit_ebitda_multiple - 4), terminal.exit_ebitda_multiple + 4, 5)
    periods = np.arange(1, len(model) + 1) - (0.5 if mid_year else 0)
    factors = 1 / (1 + rates[:, None]) ** periods[None, :]
    pv_fcf = factors @ model["UFCF"].to_numpy()
    tv_pg = model["UFCF"].iloc[-1] * (1 + growths[None, :]) / (rates[:, None] - growths[None, :])
    tv_exit = model["EBITDA"].iloc[-1] * multiples[None, :]
    pg = (pv_fcf[:, None] + tv_pg * factors[:, -1, None] - market["Net Debt"]) / market["Shares"]
    ex = (pv_fcf[:, None] + tv_exit * factors[:, -1, None] - market["Net Debt"]) / market["Shares"]
    return {"WACC / Terminal Growth": pd.DataFrame(pg, index=pd.Index(rates, name="WACC"), columns=pd.Index(growths, name="Terminal Growth")),
            "WACC / Exit Multiple": pd.DataFrame(ex, index=pd.Index(rates, name="WACC"), columns=pd.Index(multiples, name="Exit Multiple"))}


def operating_sensitivity(last: pd.Series, assumptions: ForecastAssumptions, rate: float, terminal: TerminalAssumptions,
                          market: dict[str, Any], mid_year: bool) -> pd.DataFrame:
    growth_shocks, margin_shocks = np.linspace(-0.04, 0.04, 5), np.linspace(-0.04, 0.04, 5)
    values = np.empty((5, 5))
    for i, growth_shift in enumerate(growth_shocks):
        for j, margin_shift in enumerate(margin_shocks):
            case = replace(assumptions, revenue_growth=[x + growth_shift for x in assumptions.revenue_growth],
                           ebitda_margin=[x + margin_shift for x in assumptions.ebitda_margin])
            values[i, j] = dcf(forecast(last, case, len(case.revenue_growth)), rate, terminal, market, mid_year, "perpetuity")["Implied Price"]
    return pd.DataFrame(values, index=pd.Index(np.asarray(assumptions.revenue_growth)[0] + growth_shocks, name="Year 1 Growth"),
                        columns=pd.Index(np.asarray(assumptions.ebitda_margin)[-1] + margin_shocks, name="Terminal EBITDA Margin"))


def peer_multiples(peer_data: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """Calculate valid trading multiples and flag negative denominators as missing."""
    rows = []
    for ticker, data in peer_data.items():
        f, market = data["financials"], data["market"]
        latest = f.iloc[-1]; revenue, ebitda, ebit, net_income = latest[["Revenue", "EBITDA", "EBIT", "Net Income"]]
        fcf = ebit * 0.79 + latest["D&A"] - latest["Capital Expenditure"] - f["NWC"].diff().iloc[-1]
        rows.append({"Ticker": ticker, "Company": market["Company"], "Sector": market["Sector"], "Market Cap": market["Market Cap"],
                     "Enterprise Value": market["Enterprise Value"], "Revenue": revenue, "Revenue Growth": f["Revenue"].pct_change().iloc[-1],
                     "EBITDA": ebitda, "EBITDA Margin": divide(ebitda, revenue), "EBIT": ebit, "Net Income": net_income,
                     "Net Debt": latest["Net Debt"], "EV/Revenue": divide(market["Enterprise Value"], revenue) if revenue > 0 else np.nan,
                     "EV/EBITDA": divide(market["Enterprise Value"], ebitda) if ebitda > 0 else np.nan,
                     "EV/EBIT": divide(market["Enterprise Value"], ebit) if ebit > 0 else np.nan,
                     "P/E": divide(market["Market Cap"], net_income) if net_income > 0 else np.nan,
                     "P/B": divide(market["Market Cap"], latest["Equity"]) if latest["Equity"] > 0 else np.nan,
                     "Price/Sales": divide(market["Market Cap"], revenue) if revenue > 0 else np.nan,
                     "FCF Yield": divide(fcf, market["Market Cap"]), "Net Debt / EBITDA": divide(latest["Net Debt"], ebitda) if ebitda > 0 else np.nan,
                     "Currency": market["Currency"]})
    return pd.DataFrame(rows).set_index("Ticker")


def outliers(peers: pd.DataFrame, metrics: list[str], method: str, threshold: float, manual: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Flag rather than silently delete missing, invalid, statistical, and manual exclusions."""
    clean = peers.copy(); rows = []
    for metric in metrics:
        series = pd.to_numeric(peers[metric], errors="coerce")
        invalid = ~np.isfinite(series) | (series <= 0)
        if method == "iqr":
            q1, q3 = series.quantile([0.25, 0.75]); spread = q3 - q1
            statistical = (series < q1 - threshold * spread) | (series > q3 + threshold * spread)
        elif method == "zscore":
            statistical = ((series - series.mean()) / series.std(ddof=0)).abs() > threshold
        elif method == "mad":
            median = series.median(); mad = (series - median).abs().median()
            statistical = 0.6745 * (series - median).abs() / mad > threshold if mad else pd.Series(False, index=series.index)
        else:
            statistical = pd.Series(False, index=series.index)
        excluded = invalid | statistical.fillna(False) | series.index.isin(manual)
        for ticker in series.index[excluded]:
            reason = "Manuel hariç tutma" if ticker in manual else ("Eksik/negatif payda" if invalid.loc[ticker] else f"{method.upper()} aykırı değer")
            rows.append({"Ticker": ticker, "Metric": metric, "Value": series.loc[ticker], "Reason": reason})
        clean.loc[excluded, metric] = np.nan
    return clean, pd.DataFrame(rows, columns=["Ticker", "Metric", "Value", "Reason"])


def implied_values(peers: pd.DataFrame, target: pd.Series, market: dict[str, Any], selected: list[str]) -> pd.DataFrame:
    metric_map = {"EV/Revenue": "Revenue", "EV/EBITDA": "EBITDA", "EV/EBIT": "EBIT", "P/E": "Net Income", "P/B": "Equity", "Price/Sales": "Revenue"}
    enterprise = {"EV/Revenue", "EV/EBITDA", "EV/EBIT"}; rows = []
    for multiple in selected:
        valid = peers[multiple].dropna()
        for statistic, value in (("25th Percentile", valid.quantile(.25)), ("Median", valid.median()), ("Mean", valid.mean()), ("75th Percentile", valid.quantile(.75))):
            metric = float(target[metric_map[multiple]])
            implied_ev = metric * value if multiple in enterprise else metric * value + market["Net Debt"]
            equity = implied_ev - market["Net Debt"]
            rows.append({"Multiple": multiple, "Statistic": statistic, "Selected Multiple": value, "Target Metric": metric,
                         "Implied EV": implied_ev, "Net Debt Adjustment": -market["Net Debt"], "Implied Equity": equity,
                         "Implied Price": equity / market["Shares"], "Upside": equity / market["Shares"] / market["Current Price"] - 1})
    return pd.DataFrame(rows)


def scenarios(last: pd.Series, base: ForecastAssumptions, rate: float, terminal: TerminalAssumptions,
              market: dict[str, Any], mid_year: bool) -> pd.DataFrame:
    rows = []
    for name, g, m, w, tg, em in (("Bear", -.03, -.03, .015, -.005, -2), ("Base", 0, 0, 0, 0, 0), ("Bull", .03, .03, -.01, .005, 2)):
        assumptions = replace(base, revenue_growth=[x + g for x in base.revenue_growth], ebitda_margin=[x + m for x in base.ebitda_margin])
        term = replace(terminal, terminal_growth_rate=terminal.terminal_growth_rate + tg, exit_ebitda_multiple=terminal.exit_ebitda_multiple + em)
        result = dcf(forecast(last, assumptions, len(assumptions.revenue_growth)), rate + w, term, market, mid_year, "perpetuity")
        rows.append({"Scenario": name, "Year 1 Growth": assumptions.revenue_growth[0], "Final EBITDA Margin": assumptions.ebitda_margin[-1],
                     "WACC": rate + w, "Terminal Growth": term.terminal_growth_rate, "Exit Multiple": term.exit_ebitda_multiple,
                     "Enterprise Value": result["Enterprise Value"], "Equity Value": result["Equity Value"],
                     "Implied Price": result["Implied Price"], "Upside": result["Upside"], "Terminal Value % EV": result["Terminal Value % EV"]})
    return pd.DataFrame(rows)


def commentary(results: dict[str, Any]) -> list[str]:
    """Generate concise rule-based institutional commentary."""
    dcf_result, market = results["dcf_pg"], results["market"]
    direction = "yukarı potansiyel" if dcf_result["Upside"] >= 0 else "aşağı yönlü fark"
    lines = [f"Baz senaryo DCF, hisse başına {dcf_result['Implied Price']:,.2f} {market['Currency']} tahmini değer ve mevcut fiyata göre %{abs(dcf_result['Upside'])*100:.1f} {direction} göstermektedir.",
             f"Terminal değer işletme değerinin %{dcf_result['Terminal Value % EV']*100:.1f}'ini oluşturmakta; sonuç uzun vadeli varsayımlara duyarlıdır."]
    premium = results["premium_discount"]
    if np.isfinite(premium):
        lines.append(f"Hedef şirket medyan benzer şirket EV/EBITDA çarpanına göre %{abs(premium)*100:.1f} {'primli' if premium >= 0 else 'iskontolu'} işlem görmektedir.")
    scenario = results["scenarios"].set_index("Scenario")["Implied Price"]
    lines.append(f"Ayı ve boğa senaryoları arasındaki modellenmiş değer farkı hisse başına {scenario['Bull'] - scenario['Bear']:,.2f} {market['Currency']} seviyesindedir.")
    if results["target_multiple"].get("EBITDA Margin", np.nan) > results["clean_peers"]["EBITDA Margin"].median():
        lines.append("Hedef şirketin tarihsel EBITDA marjı benzer şirket medyanının üzerindedir; bu durum değerleme primini kısmen açıklayabilir.")
    return lines
