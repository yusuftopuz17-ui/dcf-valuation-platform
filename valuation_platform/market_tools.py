"""Lightweight forward/reverse DCF and market-comparable calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd


def project_fcf(base_fcf: float, growth: float, years: int, terminal_growth: float,
                fade_growth: bool) -> np.ndarray:
    """Project free cash flow, optionally fading growth toward the terminal rate."""
    if base_fcf <= 0 or years not in {5, 10}:
        raise ValueError("Base free cash flow must be positive and the forecast period must be 5 or 10 years.")
    rates = np.linspace(growth, terminal_growth, years) if fade_growth else np.repeat(growth, years)
    return base_fcf * np.cumprod(1 + rates)


def forward_dcf(base_fcf: float, growth: float, terminal_growth: float, wacc: float,
                years: int, shares: float, net_debt: float = 0.0,
                current_price: float | None = None, mid_year: bool = False,
                fade_growth: bool = False) -> dict:
    """Calculate a perpetuity-growth DCF with an explicit EV-to-equity bridge."""
    if wacc <= terminal_growth:
        raise ValueError("WACC must be greater than the terminal growth rate.")
    if shares <= 0:
        raise ValueError("Diluted shares outstanding must be positive.")
    flows = project_fcf(base_fcf, growth, years, terminal_growth, fade_growth)
    periods = np.arange(1, years + 1, dtype=float) - (0.5 if mid_year else 0.0)
    factors = 1 / (1 + wacc) ** periods
    pv_flows = flows * factors
    terminal_value = flows[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
    pv_terminal = terminal_value * factors[-1]
    enterprise_value = float(pv_flows.sum() + pv_terminal)
    equity_value = enterprise_value - net_debt
    per_share = equity_value / shares
    upside = per_share / current_price - 1 if current_price and current_price > 0 else np.nan
    schedule = pd.DataFrame({
        "Year": np.arange(1, years + 1), "Growth": np.r_[flows[0] / base_fcf - 1, flows[1:] / flows[:-1] - 1],
        "Free Cash Flow": flows, "Discount Factor": factors, "Present Value": pv_flows,
    })
    return {
        "Enterprise Value": enterprise_value, "Net Debt": net_debt, "Equity Value": equity_value,
        "Per Share": per_share, "Current Price": current_price, "Upside": upside,
        "Terminal Value": float(terminal_value), "PV Terminal": float(pv_terminal),
        "Terminal Share": float(pv_terminal / enterprise_value), "Schedule": schedule,
    }


def reverse_dcf(target_price: float, base_fcf: float, terminal_growth: float, wacc: float,
                years: int, shares: float, net_debt: float = 0.0,
                mid_year: bool = False, fade_growth: bool = False) -> float:
    """Solve the annual FCF growth rate implied by the current share price."""
    low, high = -0.95, 2.0
    for _ in range(100):
        midpoint = (low + high) / 2
        value = forward_dcf(base_fcf, midpoint, terminal_growth, wacc, years, shares,
                            net_debt, target_price, mid_year, fade_growth)["Per Share"]
        if value < target_price:
            low = midpoint
        else:
            high = midpoint
    return (low + high) / 2


def reverse_dcf_sensitivity(target_price: float, base_fcf: float, terminal_growth: float,
                            wacc: float, years: int, shares: float, net_debt: float = 0.0,
                            mid_year: bool = False, fade_growth: bool = False) -> pd.DataFrame:
    """Return the implied growth rate across a compact WACC × terminal-growth grid."""
    rates = np.array([max(.01, wacc - .02), wacc, wacc + .02])
    terminals = np.array([max(-.01, terminal_growth - .01), terminal_growth, terminal_growth + .01])
    values = []
    for rate in rates:
        row = []
        for terminal in terminals:
            if rate <= terminal:
                row.append(np.nan)
            else:
                row.append(reverse_dcf(target_price, base_fcf, terminal, rate, years, shares,
                                       net_debt, mid_year, fade_growth))
        values.append(row)
    return pd.DataFrame(values, index=pd.Index(rates, name="WACC"),
                        columns=pd.Index(terminals, name="Terminal Growth"))


def dcf_sensitivity(base_fcf: float, growth: float, terminal_growth: float, wacc: float,
                    years: int, shares: float, net_debt: float, mid_year: bool,
                    fade_growth: bool, points: int = 9) -> pd.DataFrame:
    """Return a WACC × terminal-growth per-share sensitivity grid."""
    rates = np.linspace(max(terminal_growth + .0125, wacc - .02), wacc + .02, points)
    growths = np.linspace(max(-.01, terminal_growth - .01), terminal_growth + .01, points)
    values = []
    for rate in rates:
        row = []
        for terminal in growths:
            row.append(forward_dcf(base_fcf, growth, terminal, rate, years, shares, net_debt,
                                   None, mid_year, fade_growth)["Per Share"])
        values.append(row)
    return pd.DataFrame(values, index=pd.Index(rates, name="WACC"),
                        columns=pd.Index(growths, name="Terminal Growth"))


def scenario_table(base_fcf: float, growth: float, terminal_growth: float, wacc: float,
                   years: int, shares: float, net_debt: float, current_price: float,
                   mid_year: bool, fade_growth: bool) -> pd.DataFrame:
    """Calculate transparent bear/base/bull cases."""
    cases = [("Bear", growth - .06, wacc + .02), ("Base", growth, wacc), ("Bull", growth + .06, wacc - .02)]
    rows = []
    for name, case_growth, case_wacc in cases:
        case_wacc = max(case_wacc, terminal_growth + .005)
        result = forward_dcf(base_fcf, case_growth, terminal_growth, case_wacc, years, shares,
                             net_debt, current_price, mid_year, fade_growth)
        rows.append({"Scenario": name, "FCF Growth": case_growth, "WACC": case_wacc,
                     "Value Per Share": result["Per Share"], "Upside / Downside": result["Upside"]})
    return pd.DataFrame(rows).set_index("Scenario")


def comparable_implied_prices(target: pd.Series, peers: pd.DataFrame) -> pd.DataFrame:
    """Apply peer quartiles/medians to target fundamentals and bridge EV to equity."""
    definitions = {
        "EV/EBITDA": ("EBITDA", True), "P/E": ("Net Income", False),
        "P/S": ("Revenue", False), "P/B": ("Equity", False),
    }
    # Provider feeds can occasionally mix a foreign quote currency with financial
    # statements reported in another currency. Exclude clearly non-economic
    # observations from the valuation median while keeping raw tables auditable.
    sensible_ceiling = {"EV/EBITDA": 250.0, "P/E": 500.0, "P/S": 100.0, "P/B": 100.0}
    rows = []
    shares = float(target.get("Diluted Shares", np.nan))
    for multiple, (metric, is_enterprise) in definitions.items():
        observations = (
            pd.to_numeric(peers.get(multiple), errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )
        observations = observations[(observations > 0) & (observations <= sensible_ceiling[multiple])]
        q1, median, mean, q3 = observations.quantile(.25), observations.median(), observations.mean(), observations.quantile(.75)
        fundamental = float(target.get(metric, np.nan))
        if not np.isfinite(median) or not np.isfinite(fundamental) or fundamental <= 0 or shares <= 0:
            continue
        net_debt = float(target.get("Net Debt", 0))
        value = median * fundamental if is_enterprise else median * fundamental + net_debt
        equity = value - net_debt
        price = equity / shares
        q1_value = q1 * fundamental if is_enterprise else q1 * fundamental + net_debt
        q3_value = q3 * fundamental if is_enterprise else q3 * fundamental + net_debt
        q1_price = (q1_value - net_debt) / shares
        q3_price = (q3_value - net_debt) / shares
        current = float(target.get("Current Price", np.nan))
        rows.append({
            "Multiple": multiple,
            "Peer 25th Percentile": q1,
            "Peer Median": median,
            "Peer Mean": mean,
            "Peer 75th Percentile": q3,
            "Target Multiple": float(target.get(multiple, np.nan)),
            "Target Metric": fundamental,
            "Implied Enterprise Value": value,
            "Net Debt Adjustment": -net_debt,
            "Implied Equity Value": equity,
            "Implied Price at 25th Percentile": q1_price,
            "Implied Price": price,
            "Implied Price at 75th Percentile": q3_price,
            "Current Price": current,
            "Premium / Discount": price / current - 1 if current > 0 else np.nan,
        })
    return pd.DataFrame(rows).set_index("Multiple") if rows else pd.DataFrame()
