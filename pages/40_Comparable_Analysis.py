"""Fast, evidence-linked public-company comparable analysis."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from src.ccv_provider import company_record, discover_yahoo_candidates, load_candidate_records
from src.ui import banner, footer, kpi, page_header, section
from valuation_platform.ccv import calculate_multiples
from valuation_platform.market_tools import comparable_implied_prices


PEER_PRESETS = {
    "MSFT": ["AAPL", "GOOGL", "ORCL", "CRM", "ADBE", "NOW", "IBM"],
    "AAPL": ["MSFT", "GOOGL", "AMZN", "META", "DELL", "HPQ", "SONY"],
    "GOOGL": ["META", "MSFT", "AMZN", "SNAP", "PINS", "TTD", "BIDU"],
}

SECTOR_PRESETS = {
    "Technology": ["MSFT", "AAPL", "GOOGL", "ORCL", "CRM", "ADBE", "NOW", "IBM"],
    "Communication Services": ["GOOGL", "META", "NFLX", "DIS", "TMUS", "VZ", "T"],
    "Consumer Cyclical": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW"],
    "Consumer Defensive": ["WMT", "COST", "PG", "KO", "PEP", "PM", "CL"],
    "Healthcare": ["LLY", "JNJ", "ABBV", "MRK", "PFE", "TMO", "ABT"],
    "Financial Services": ["JPM", "BAC", "WFC", "C", "GS", "MS", "AXP"],
    "Industrials": ["GE", "CAT", "HON", "RTX", "UPS", "DE", "ETN"],
    "Energy": ["XOM", "CVX", "COP", "EOG", "SLB", "MPC", "PSX"],
}


def _candidate_universe(ticker: str, sector: str, manual: list[str]) -> list[str]:
    """Prefer stable primary listings; fall back to Yahoo sector discovery."""
    if manual:
        return manual
    candidates = PEER_PRESETS.get(ticker) or SECTOR_PRESETS.get(sector)
    if candidates:
        return [item for item in candidates if item != ticker]
    return [item for item in discover_yahoo_candidates(sector, 20) if item != ticker]


def _fmt_money(value: float, currency: str) -> str:
    if not np.isfinite(value):
        return "N/M"
    for divisor, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(value) >= divisor:
            return f"{currency} {value/divisor:,.1f}{suffix}"
    return f"{currency} {value:,.0f}"


def _display_table(target: pd.Series, peers: pd.DataFrame, view: str) -> pd.DataFrame:
    frame = pd.concat([target.to_frame().T, peers], axis=0)
    frame["P/E"] = np.where(frame["Net Income"] > 0, frame["Market Cap"] / frame["Net Income"], np.nan)
    frame["EV/EBITDA"] = np.where(frame["EBITDA"] > 0, frame["Enterprise Value"] / frame["EBITDA"], np.nan)
    columns = ["Company", "Market Cap", "P/E", "EV/EBITDA", "P/S", "P/B",
               "Revenue Growth", "Net Margin"]
    if view == "Trailing + Forward":
        columns += ["Forward P/E", "PEG", "EPS Growth"]
    return frame[columns]


st.session_state.setdefault("quick_comp_ticker", "MSFT")
st.session_state.setdefault("quick_comp_manual", "")
st.session_state.setdefault("quick_comp_package", None)

page_header("Comparable Company Analysis", "Benchmark the target against sector peers and estimate its implied price from median trading multiples.")
left, right = st.columns([3, 1])
left.text_input("Ticker Symbol", key="quick_comp_ticker", placeholder="e.g., MSFT")
run = right.button("Analyze", type="primary", use_container_width=True)
st.text_input("Optional Manual Peers", key="quick_comp_manual",
              placeholder="e.g., AAPL, GOOGL, ORCL — leave blank for automatic sector screening")

if run:
    ticker = st.session_state.quick_comp_ticker.strip().upper()
    try:
        with st.spinner("Retrieving target and peer-company data from Yahoo Finance..."):
            target_package = company_record(ticker)
            target_record = target_package["record"]
            manual = [item.strip().upper() for item in st.session_state.quick_comp_manual.split(",") if item.strip()]
            universe = _candidate_universe(ticker, target_record["Sector"], manual)[:8]
            peer_frame, failures, histories = load_candidate_records(universe)
            if not peer_frame.empty:
                same_currency = peer_frame["Currency"].eq(target_record["Currency"])
                same_country = peer_frame["Country"].eq(target_record["Country"])
                peer_frame = peer_frame.loc[same_currency & same_country]
            if len(peer_frame) < 3:
                raise ValueError(
                    "At least three peers in the same country and currency are required for a reliable median. "
                    "Enter primary-listing tickers in the manual peer field."
                )
            st.session_state.quick_comp_package = {
                "target": target_record, "peers": peer_frame, "failures": failures,
                "source": target_record["Data Source"], "retrieved": target_record["Retrieved At"],
            }
    except Exception as exc:
        st.session_state.quick_comp_package = None
        st.error(f"Analysis could not be completed: {exc}")

package = st.session_state.quick_comp_package
if not package:
    banner("How It Works", "Enter a ticker and select Analyze. The tool identifies sector peers and compares trading multiples, growth, and profitability in one table.")
    st.caption("Data is retrieved only when you select Analyze. Source: Yahoo Finance. Results are not investment advice.")
    footer()
    st.stop()

target = pd.Series(package["target"], name=package["target"]["Ticker"])
peers = calculate_multiples(package["peers"])
peers["P/S"] = peers.get("P/S")
peers["P/B"] = peers.get("P/B")
target_calc = calculate_multiples(target.to_frame().T).iloc[0]
target_calc.name = target.name
target_calc["P/S"], target_calc["P/B"] = target["P/S"], target["P/B"]
implied = comparable_implied_prices(target_calc, peers)
currency = str(target["Currency"])

section(f"{target['Company']} ({target.name})")
top_metrics = [
    ("Current Price", f"{currency} {target['Current Price']:,.2f}", str(target["Price Date"])),
    ("Market Capitalization", _fmt_money(float(target["Market Cap"]), currency), "Equity value"),
    ("Revenue Growth", f"{target['Revenue Growth']*100:,.1f}%", "Latest reported period"),
    ("Net Profit Margin", f"{target['Net Margin']*100:,.1f}%", "Latest reported period"),
]
st.markdown(
    "<div class='br-shell comp-kpi-grid'><div class='br-grid'>"
    + "".join(
        f"<div class='br-stat'><span>{label}</span><strong>{value}</strong><small>{note}</small></div>"
        for label, value, note in top_metrics
    )
    + "</div></div>",
    unsafe_allow_html=True,
)

view = st.radio("View", ["Trailing", "Trailing + Forward"], horizontal=True)
comparison = _display_table(target_calc, peers, view)
numeric_columns = [column for column in comparison.columns if column != "Company"]
numeric_peers = comparison.iloc[1:][numeric_columns].apply(pd.to_numeric, errors="coerce")
median = numeric_peers.median()
median_row = pd.DataFrame([{**{"Company": "Peer Median"}, **median.to_dict()}], index=["MEDIAN"])
comparison = pd.concat([comparison, median_row])

percent_columns = [name for name in ["Revenue Growth", "Net Margin", "EPS Growth"] if name in comparison]
formats = {column: "{:.1f}x" for column in ["P/E", "EV/EBITDA", "P/S", "P/B", "Forward P/E", "PEG"] if column in comparison}
formats.update({column: "{:.1%}" for column in percent_columns})
formats["Market Cap"] = "{:,.0f}"
st.dataframe(comparison.style.format(formats, na_rep="N/M")
             .background_gradient(subset=[c for c in ["P/E", "EV/EBITDA", "P/S", "P/B"] if c in comparison],
                                  cmap="RdYlGn_r"),
             use_container_width=True, height=min(490, 75 + 36 * len(comparison)))
st.caption(f"Source: {package['source']} · Target financial period: {target['Financial Date']} · "
           f"Price date: {target['Price Date']} · Peer count: {len(peers)}")

section("Peer Company Medians")
median_items = [
    ("P/E", median.get("P/E"), "x"),
    ("EV/EBITDA", median.get("EV/EBITDA"), "x"),
    ("P/Sales", median.get("P/S"), "x"),
    ("P/Book", median.get("P/B"), "x"),
    ("Revenue Growth", median.get("Revenue Growth"), "%"),
    ("Net Profit Margin", median.get("Net Margin"), "%"),
]
median_cards = []
for label, value, unit in median_items:
    if pd.isna(value):
        rendered = "N/M"
    elif unit == "%":
        rendered = f"{float(value)*100:.1f}%"
    else:
        rendered = f"{float(value):.1f}x"
    median_cards.append(
        f"<div class='br-stat'><span>{label}</span><strong>{rendered}</strong></div>"
    )
st.markdown(
    "<div class='br-shell median-panel'><div class='br-grid'>"
    + "".join(median_cards)
    + "</div></div>",
    unsafe_allow_html=True,
)

section("Multiple-Implied Share Price")
if implied.empty:
    st.warning("No valid combination of trading multiples and positive target fundamentals was available.")
else:
    st.dataframe(implied.style.format({
        "Peer Median": "{:.1f}x", "Implied Price": f"{currency} {{:,.2f}}",
        "Current Price": f"{currency} {{:,.2f}}", "Premium / Discount": "{:+.1%}",
    }), use_container_width=True)
    prices = implied["Implied Price"]
    blended = prices.median()
    result_metrics = [
        ("Blended Midpoint", f"{currency} {blended:,.2f}", f"{blended/target['Current Price']-1:+.1%} vs. current price"),
        ("Valuation Range", f"{currency} {prices.min():,.2f} – {prices.max():,.2f}", "Low to high implied price"),
        ("Valid Methods", str(len(prices)), "Enterprise- and equity-value multiples"),
    ]
    st.markdown(
        "<div class='br-shell comp-result-grid'><div class='br-grid'>"
        + "".join(
            f"<div class='br-stat'><span>{label}</span><strong>{value}</strong><small>{note}</small></div>"
            for label, value, note in result_metrics
        )
        + "</div></div>",
        unsafe_allow_html=True,
    )
    expensive = int((target_calc[implied.index] > implied["Peer Median"]).sum())
    verdict = "premium" if blended < target["Current Price"] else "discount"
    banner("Analyst Interpretation", f"The target appears to trade at an approximate "
           f"{abs(blended/target['Current Price']-1)*100:.1f}% {verdict} to the blended peer-implied value. "
           f"It is more expensive than the peer median on {expensive} of {len(implied)} valid multiples. "
           "The result should not be used without considering differences in growth, margins, reporting periods, and business models.")

with st.expander("Methodology and Usage Notes"):
    st.markdown("""
- **P/E:** Compares equity value for companies with positive net income.
- **EV/EBITDA:** Compares enterprise value while reducing capital-structure and depreciation differences.
- **P/Sales:** Provides an additional reference for growth companies whose profitability has not yet normalized.
- **P/Book:** Is generally more relevant for banks and asset-intensive businesses.
- Implied price is calculated by applying each peer median multiple to the target company's corresponding financial metric.
- Red and green cells indicate relative expensiveness or cheapness only; they are not investment recommendations.
""")
if not package["failures"].empty:
    with st.expander("Candidates With Unavailable Data"):
        st.dataframe(package["failures"], use_container_width=True)
footer()
