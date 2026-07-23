"""Interactive forward and reverse DCF workspace with live market context."""

from __future__ import annotations

import html
import json

import numpy as np
import pandas as pd
import streamlit as st

from src.ccv_provider import company_record
from src.ui import footer, page_header, section
from valuation_platform.market_tools import (
    dcf_sensitivity,
    forward_dcf,
    reverse_dcf,
    reverse_dcf_sensitivity,
    scenario_table,
)
from valuation_platform.model import historical_metrics


def _money(value: float, currency: str, decimals: int = 1) -> str:
    if not np.isfinite(value):
        return "N/M"
    for divisor, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(value) >= divisor:
            return f"{currency} {value/divisor:,.{decimals}f}{suffix}"
    return f"{currency} {value:,.2f}"


def _grouped_number(value: float, decimals: int = 0) -> str:
    """Format editable values with comma thousands separators."""
    return f"{float(value):,.{decimals}f}"


def _parse_grouped_number(value: str) -> float:
    """Parse values rendered by `_grouped_number`."""
    cleaned = value.strip().replace(" ", "").replace(",", "")
    return float(cleaned)


def _set_grouped_display(key: str, value: float, decimals: int = 0) -> None:
    st.session_state[key] = float(value)
    st.session_state[f"{key}_display"] = _grouped_number(value, decimals)


def _grouped_number_input(label: str, key: str, decimals: int = 0, help_text: str | None = None) -> float:
    """Use a text field because HTML number inputs cannot show thousands groups."""
    display_key = f"{key}_display"
    st.session_state.setdefault(display_key, _grouped_number(st.session_state[key], decimals))
    raw = st.text_input(label, key=display_key, help=help_text)
    try:
        parsed = _parse_grouped_number(raw)
        st.session_state[key] = parsed
    except ValueError:
        st.error(f"{label} must be a valid number.")
    return float(st.session_state[key])


def _result_card(result: dict, company: str, currency: str) -> None:
    upside = result["Upside"]
    tone = "br-danger" if np.isfinite(upside) and upside < 0 else ""
    direction = "downside" if np.isfinite(upside) and upside < 0 else "upside"
    delta = f"{abs(upside)*100:.1f}% {direction}" if np.isfinite(upside) else "No current price"
    st.markdown(
        f"""<div class="br-result {tone}">
        <div class="br-kicker">{html.escape(company)}</div>
        <div class="br-note">DCF-implied equity value</div>
        <div class="br-big">{_money(result['Equity Value'], currency)}</div>
        <div class="br-grid">
          <div class="br-stat"><span>Per Share</span><strong>{currency} {result['Per Share']:,.2f}</strong></div>
          <div class="br-stat"><span>Current Price</span><strong>{currency} {(result['Current Price'] or 0):,.2f}</strong></div>
          <div class="br-stat"><span>Price Difference</span><strong>{delta}</strong></div>
        </div>
        <p class="br-note" style="margin-top:18px">Terminal value represents {result['Terminal Share']*100:.1f}% of enterprise value.
        Equity value equals enterprise value less net debt.</p>
        </div>""",
        unsafe_allow_html=True,
    )


def _assumption_inputs(include_growth: bool) -> None:
    st.markdown("<div class='br-kicker'>Core Data</div>", unsafe_allow_html=True)
    _grouped_number_input("Current Share Price", "dcf_price", 2)
    _grouped_number_input(
        "Free Cash Flow (Latest Period)", "dcf_base_fcf",
        help_text="Uses provider free cash flow when available; otherwise calculates unlevered free cash flow from the financial statements.",
    )
    _grouped_number_input("Diluted Shares Outstanding", "dcf_shares")
    _grouped_number_input(
        "Net Debt", "dcf_net_debt",
        help_text="Debt less cash. Enter a net cash position as a negative amount.",
    )
    st.divider()
    st.markdown("<div class='br-kicker'>Model Assumptions</div>", unsafe_allow_html=True)
    if include_growth:
        st.slider("FCF Growth (Years 1–5/10) %", 0.0, 50.0, step=.5, key="dcf_growth")
    st.slider("Terminal Growth Rate %", 0.0, 5.0, step=.1, key="dcf_terminal")
    st.slider("Discount Rate (WACC) %", 1.0, 25.0, step=.5, key="dcf_wacc")
    st.radio("Forecast Period", [5, 10], horizontal=True, key="dcf_years")
    st.toggle("Fade Growth Toward the Terminal Rate", key="dcf_fade",
              help="Linearly fades the forecast growth rate toward the terminal rate over the explicit forecast period.")
    st.toggle("Mid-Year Discounting", key="dcf_midyear")


defaults = {
    "dcf_quick_ticker": "MSFT", "dcf_quick_package": None,
    "dcf_base_fcf": 100_000_000_000.0, "dcf_shares": 7_500_000_000.0,
    "dcf_net_debt": 0.0, "dcf_price": 0.0, "dcf_growth": 10.0,
    "dcf_terminal": 2.5, "dcf_wacc": 9.0, "dcf_years": 5,
    "dcf_midyear": True, "dcf_fade": False, "dcf_mode": "Forward DCF — Fair Value",
}
for key, value in defaults.items():
    st.session_state.setdefault(key, value)

if not st.session_state.get("dcf_query_loaded"):
    query = st.query_params
    conversions = {
        "g": ("dcf_growth", float), "tg": ("dcf_terminal", float), "w": ("dcf_wacc", float),
        "y": ("dcf_years", int), "fcf": ("dcf_base_fcf", float), "sh": ("dcf_shares", float),
        "nd": ("dcf_net_debt", float), "px": ("dcf_price", float),
        "mid": ("dcf_midyear", lambda value: value == "1"),
        "fade": ("dcf_fade", lambda value: value == "1"),
    }
    for parameter, (state_key, converter) in conversions.items():
        if parameter in query:
            try:
                st.session_state[state_key] = converter(query[parameter])
            except (TypeError, ValueError):
                pass
    st.session_state.dcf_query_loaded = True

page_header("DCF Valuation Laboratory",
            "Estimate a company's fair value or solve for the growth implied by its market price.")
st.radio("Analysis Mode", ["Forward DCF — Fair Value", "Reverse DCF — Implied Growth"],
         horizontal=True, key="dcf_mode", label_visibility="collapsed")

search_left, search_right = st.columns([4, 1])
search_left.text_input("Ticker Symbol", key="dcf_quick_ticker", placeholder="e.g., AAPL")
load = search_right.button("Load Data", type="primary", width="stretch")

if load:
    try:
        with st.spinner("Retrieving market and financial data..."):
            package = company_record(st.session_state.dcf_quick_ticker.strip().upper())
            record = package["record"]
            provider_fcf = float(pd.to_numeric(record.get("Free Cash Flow"), errors="coerce"))
            if not np.isfinite(provider_fcf) or provider_fcf <= 0:
                fcf_series = historical_metrics(package["historical"])["Free Cash Flow"].replace(
                    [np.inf, -np.inf], np.nan).dropna()
                if fcf_series.empty or fcf_series.iloc[-1] <= 0:
                    raise ValueError("No positive free cash flow was available; use manual input.")
                provider_fcf = float(fcf_series.iloc[-1])
            st.session_state.dcf_quick_package = package
            _set_grouped_display("dcf_base_fcf", provider_fcf)
            _set_grouped_display("dcf_shares", float(record["Diluted Shares"]))
            _set_grouped_display("dcf_net_debt", float(record["Net Debt"]))
            _set_grouped_display("dcf_price", float(record["Current Price"]), 2)
            eps_growth = float(pd.to_numeric(record.get("EPS Growth"), errors="coerce"))
            if np.isfinite(eps_growth) and eps_growth > 0:
                st.session_state.dcf_growth = float(np.clip(eps_growth * 75, 1, 50))
    except Exception as exc:
        st.error(f"Data could not be loaded: {exc}")

package = st.session_state.dcf_quick_package
record = package["record"] if package else {}
company = str(record.get("Company") or st.session_state.dcf_quick_ticker.upper())
currency = str(record.get("Currency") or "USD")
if package:
    st.caption(f"{company} · Near-live provider data · Price date: {record['Price Date']} · "
               f"Financial period: {record['Financial Date']} · Source: Yahoo Finance")
else:
    st.info("Load a ticker or enter your own data below. Results update immediately as assumptions change.")

growth = st.session_state.dcf_growth / 100
terminal = st.session_state.dcf_terminal / 100
rate = st.session_state.dcf_wacc / 100

if st.session_state.dcf_mode.startswith("Forward"):
    input_col, output_col = st.columns([.38, .62], gap="large")
    with input_col:
        with st.container(border=True):
            _assumption_inputs(include_growth=True)
    try:
        result = forward_dcf(
            st.session_state.dcf_base_fcf, growth, terminal, rate,
            st.session_state.dcf_years, st.session_state.dcf_shares,
            st.session_state.dcf_net_debt, st.session_state.dcf_price or None,
            st.session_state.dcf_midyear, st.session_state.dcf_fade,
        )
    except Exception as exc:
        output_col.error(f"DCF could not be calculated: {exc}")
        footer()
        st.stop()

    scenarios = scenario_table(
        st.session_state.dcf_base_fcf, growth, terminal, rate,
        st.session_state.dcf_years, st.session_state.dcf_shares,
        st.session_state.dcf_net_debt, st.session_state.dcf_price or result["Per Share"],
        st.session_state.dcf_midyear, st.session_state.dcf_fade,
    )
    scenario_spread = scenarios["Value Per Share"].max() - scenarios["Value Per Share"].min()
    spread_ratio = scenario_spread / max(st.session_state.dcf_price, result["Per Share"], 1)
    sensitivity_label = "Low" if spread_ratio < .30 else ("Moderate" if spread_ratio < .75 else "High")

    with output_col:
        if result["Terminal Share"] > .75:
            st.warning(f"Terminal value represents {result['Terminal Share']*100:.1f}% of enterprise value; "
                       "the model is highly sensitive to long-term assumptions.")
        st.info(f"{sensitivity_label} sensitivity · Bear/bull spread equals {spread_ratio*100:.0f}% of the current price")
        _result_card(result, company, currency)
        if np.isfinite(result["Upside"]):
            if result["Upside"] >= 0:
                safety = 1 - st.session_state.dcf_price / result["Per Share"]
                st.success(f"Margin of safety: {safety*100:.1f}%")
                st.progress(float(np.clip(safety, 0, 1)))
            else:
                premium = st.session_state.dcf_price / result["Per Share"] - 1
                st.error(f"The shares trade {premium*100:.1f}% above the DCF value under these assumptions.")
                st.progress(float(np.clip(premium, 0, 1)))
        verdict = ("The model produces a value above the market price. Test the resilience of the growth and "
                   "WACC assumptions in the sensitivity table." if result["Upside"] >= 0 else
                   "The market is pricing higher growth or lower risk than your model. That premium must be "
                   "supported by operating performance.")
        st.markdown(f"<div class='br-verdict'><b>What This Means</b><br>{verdict}</div>",
                    unsafe_allow_html=True)

    section("WACC × Terminal Growth Sensitivity")
    sensitivity = dcf_sensitivity(
        st.session_state.dcf_base_fcf, growth, terminal, rate,
        st.session_state.dcf_years, st.session_state.dcf_shares,
        st.session_state.dcf_net_debt, st.session_state.dcf_midyear,
        st.session_state.dcf_fade,
    ).T
    sensitivity.index = [f"%{item*100:.1f}" for item in sensitivity.index]
    sensitivity.index.name = "Terminal Growth"
    sensitivity.columns = [f"WACC {item*100:.1f}%" for item in sensitivity.columns]
    sensitivity_display = sensitivity.reset_index()
    st.dataframe(
        sensitivity_display.style.format(
            {column: f"{currency} {{:,.2f}}" for column in sensitivity.columns}
        ).background_gradient(subset=list(sensitivity.columns), cmap="RdYlGn"),
        column_config={
            "Terminal Growth": st.column_config.TextColumn(
                "Terminal Growth", width="medium",
            )
        },
        hide_index=True,
        width="stretch",
    )
    st.caption("Green cells indicate higher implied values and red cells indicate lower implied values. "
               "Assess whether the conclusion remains robust across a broad range of assumptions.")

    section("Scenario Comparison")
    cards = st.columns(3)
    scenario_tones = {"Bear": "br-danger", "Base": "", "Bull": ""}
    for column, (name, row) in zip(cards, scenarios.iterrows()):
        with column:
            st.markdown(
                f"""<div class="br-result {scenario_tones[name]}">
                <div class="br-kicker">{name} Case</div>
                <div class="br-big" style="font-size:2.1rem">{currency} {row['Value Per Share']:,.2f}</div>
                <div class="br-note">Growth {row['FCF Growth']*100:.1f}% · WACC {row['WACC']*100:.1f}%<br>
                Upside / downside {row['Upside / Downside']:+.1%}</div></div>""",
                unsafe_allow_html=True,
            )

    section("Present Value Breakdown")
    schedule = result["Schedule"].copy()
    pv_chart = schedule.set_index("Year")[["Present Value"]]
    pv_chart.index = [f"Year {year}" for year in pv_chart.index]
    pv_chart.loc["Terminal Value"] = result["PV Terminal"]
    pv_chart["Share of Present Value"] = pv_chart["Present Value"] / pv_chart["Present Value"].sum()
    st.bar_chart(pv_chart[["Share of Present Value"]], height=360)
    st.caption("The chart displays each component as a share of total present value so Years 1–5/10 remain visible even when terminal value is dominant.")
    st.dataframe(schedule.style.format({
        "Growth": "{:.1%}", "Free Cash Flow": f"{currency} {{:,.0f}}",
        "Discount Factor": "{:.4f}", "Present Value": f"{currency} {{:,.0f}}",
    }), hide_index=True, width="stretch")

    if package:
        analyst_target = float(pd.to_numeric(record.get("Analyst Target"), errors="coerce"))
        analyst_count = float(pd.to_numeric(record.get("Analyst Count"), errors="coerce"))
        if np.isfinite(analyst_target):
            section("Market · Analyst · DCF")
            analyst_note = f"{int(analyst_count)} analysts" if np.isfinite(analyst_count) else "Consensus target"
            st.markdown(
                f"""<div class="br-shell market-triad"><div class="br-grid">
                <div class="br-stat"><span>Mean Analyst Target</span>
                <strong>{currency} {analyst_target:,.2f}</strong><small>{analyst_note}</small></div>
                <div class="br-stat"><span>Current Price</span>
                <strong>{currency} {st.session_state.dcf_price:,.2f}</strong><small>Market price</small></div>
                <div class="br-stat"><span>DCF Fair Value</span>
                <strong>{currency} {result['Per Share']:,.2f}</strong><small>{result['Upside']:+.1%}</small></div>
                </div></div>""",
                unsafe_allow_html=True,
            )
else:
    input_col, output_col = st.columns([.38, .62], gap="large")
    with input_col:
        with st.container(border=True):
            _assumption_inputs(include_growth=False)
    if st.session_state.dcf_price <= 0:
        output_col.info("A current share price is required for reverse DCF.")
        footer()
        st.stop()
    implied_growth = reverse_dcf(
        st.session_state.dcf_price, st.session_state.dcf_base_fcf, terminal, rate,
        st.session_state.dcf_years, st.session_state.dcf_shares,
        st.session_state.dcf_net_debt, st.session_state.dcf_midyear,
        st.session_state.dcf_fade,
    )
    consensus = float(pd.to_numeric(record.get("EPS Growth"), errors="coerce")) if package else np.nan
    risk = "Reasonable Expectation" if implied_growth <= .10 else (
        "High Expectation" if implied_growth <= .25 else "Aggressive Growth Priced In")
    tone = "" if implied_growth <= .25 else "br-danger"
    with output_col:
        st.markdown(
            f"""<div class="br-result {tone}" style="text-align:center">
            <div class="br-kicker">{html.escape(company)}</div>
            <div class="br-note">Implied {st.session_state.dcf_years}-year FCF growth</div>
            <div class="br-big">{implied_growth*100:.1f}%</div>
            <div class="br-kicker">{risk}</div>
            <div class="br-grid">
              <div class="br-stat"><span>Share Price</span><strong>{currency} {st.session_state.dcf_price:,.2f}</strong></div>
              <div class="br-stat"><span>Market Capitalization</span><strong>{_money(st.session_state.dcf_price*st.session_state.dcf_shares,currency)}</strong></div>
              <div class="br-stat"><span>Current FCF</span><strong>{_money(st.session_state.dcf_base_fcf,currency)}</strong></div>
            </div></div>""",
            unsafe_allow_html=True,
        )
        if np.isfinite(consensus):
            difference = implied_growth - consensus
            st.metric("Analyst Growth Consensus", f"{consensus*100:.1f}%",
                      f"Implied growth difference {difference*100:+.1f} percentage points")
        st.markdown(
            f"<div class='br-verdict'>At the selected WACC and terminal growth rate, the market price requires "
            f"approximately <b>{implied_growth*100:.1f}%</b> annual FCF growth. "
            "Compare this rate with the company's historical growth, industry outlook, and analyst expectations.</div>",
            unsafe_allow_html=True,
        )

    section("Implied Growth Sensitivity")
    reverse_grid = reverse_dcf_sensitivity(
        st.session_state.dcf_price, st.session_state.dcf_base_fcf, terminal, rate,
        st.session_state.dcf_years, st.session_state.dcf_shares,
        st.session_state.dcf_net_debt, st.session_state.dcf_midyear,
        st.session_state.dcf_fade,
    )
    reverse_grid.index = [f"WACC {item*100:.1f}%" for item in reverse_grid.index]
    reverse_grid.columns = [f"Terminal {item*100:.1f}%" for item in reverse_grid.columns]
    st.dataframe(reverse_grid.style.format("{:.1%}").background_gradient(cmap="RdYlGn_r"),
                 width="stretch")
    st.caption("A higher implied growth rate represents a more demanding operating expectation embedded in the current price.")

section("How to Interpret a DCF")
lesson_cols = st.columns(2)
lessons = [
    ("1 · Free Cash Flow", "Subtract capital expenditures from cash flow from operations. For volatile businesses, use a normalized multi-year average rather than a single period."),
    ("2 · Growth Assumption", "Use historical growth as a starting point and recognize that high growth becomes harder to sustain as the company scales."),
    ("3 · WACC", "WACC is the return required by capital providers. As risk and WACC rise, present value falls."),
    ("4 · Sensitivity", "A single fair-value estimate can create false precision. The investment thesis should remain credible across multiple WACC and terminal-growth assumptions."),
]
for index, (title, text) in enumerate(lessons):
    with lesson_cols[index % 2]:
        st.markdown(f"<div class='br-lesson'><h3>{title}</h3><p class='br-note'>{text}</p></div>",
                    unsafe_allow_html=True)

with st.expander("Formulas, Limitations, and Frequently Asked Questions"):
    st.markdown("""
#### Core formulas

`Enterprise Value = Present value of explicit-period FCF + Present value of terminal value`

`Terminal Value = FCFₙ × (1 + g) / (WACC − g)`

`Equity Value = Enterprise Value − Net Debt`

#### When is DCF less reliable?

- Early-stage companies with negative or unpredictable cash flow,
- Commodity and heavy-industry businesses at a cyclical peak or trough,
- Banks and insurers, where debt is an operating input,
- Models in which terminal value represents an excessive share of total value.

#### What is an appropriate margin of safety?

There is no universal threshold. The greater the uncertainty in the business model and forecasts, the larger the required margin of safety should be.
""")

export_result = {
    "ticker": record.get("Ticker") if package else None,
    "mode": st.session_state.dcf_mode,
    "assumptions": {
        "base_fcf": st.session_state.dcf_base_fcf, "growth": growth,
        "terminal_growth": terminal, "wacc": rate, "years": st.session_state.dcf_years,
        "shares": st.session_state.dcf_shares, "net_debt": st.session_state.dcf_net_debt,
        "current_price": st.session_state.dcf_price, "mid_year": st.session_state.dcf_midyear,
        "fade_growth": st.session_state.dcf_fade,
    },
}
download_col, share_col = st.columns(2)
download_col.download_button(
    "Download Analysis as JSON", json.dumps(export_result, ensure_ascii=False, indent=2, default=float),
    "dcf_analysis.json", "application/json", width="stretch",
)
if share_col.button("Add Assumptions to URL", width="stretch"):
    st.query_params.update({
        "g": str(st.session_state.dcf_growth), "tg": str(st.session_state.dcf_terminal),
        "w": str(st.session_state.dcf_wacc), "y": str(st.session_state.dcf_years),
        "fcf": str(st.session_state.dcf_base_fcf), "sh": str(st.session_state.dcf_shares),
        "nd": str(st.session_state.dcf_net_debt), "px": str(st.session_state.dcf_price),
        "mid": "1" if st.session_state.dcf_midyear else "0",
        "fade": "1" if st.session_state.dcf_fade else "0",
    })
    st.success("Assumptions were added to the address bar; you can now copy the link.")
footer()
