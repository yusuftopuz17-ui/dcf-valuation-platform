"""Fast, evidence-linked public-company comparable analysis."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from src.ccv_provider import company_record, discover_yahoo_candidates, load_candidate_records
from src.ui import banner, footer, kpi, page_header, section
from valuation_platform.ccv import calculate_multiples
from valuation_platform.market_tools import comparable_implied_prices
from valuation_platform.professional_analysis import (
    DEFAULT_SIMILARITY_WEIGHTS,
    SIMILARITY_CRITERIA,
    comparable_similarity,
    identify_multiple_outliers,
    peer_multiple_statistics,
)


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
            return f"{value/divisor:,.1f}{suffix}"
    return f"{value:,.0f}"


def _display_table(target: pd.Series, peers: pd.DataFrame, view: str) -> pd.DataFrame:
    frame = pd.concat([target.to_frame().T, peers], axis=0)
    frame["P/E"] = np.where(frame["Net Income"] > 0, frame["Market Cap"] / frame["Net Income"], np.nan)
    frame["EV/EBITDA"] = np.where(frame["EBITDA"] > 0, frame["Enterprise Value"] / frame["EBITDA"], np.nan)
    columns = ["Company", "Market Cap", "P/E", "EV/EBITDA", "P/S", "P/B",
               "Revenue Growth", "EBITDA Margin", "Net Margin"]
    if view == "Trailing + Forward":
        columns += ["Forward P/E", "PEG", "EPS Growth"]
    return frame[columns]


st.session_state.setdefault("quick_comp_ticker", "MSFT")
st.session_state.setdefault("quick_comp_manual", "")
st.session_state.setdefault("quick_comp_package", None)
for criterion, weight in DEFAULT_SIMILARITY_WEIGHTS.items():
    st.session_state.setdefault(f"similarity_weight_{criterion}", weight * 100)

page_header("Comparable Company Analysis", "Benchmark the target against sector peers and estimate its implied price from median trading multiples.")
left, right = st.columns([3, 1], vertical_alignment="bottom")
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
implied = implied.rename(columns={
    "Benzer Medyanı": "Peer Median",
    "İma Edilen Fiyat": "Implied Price",
    "Güncel Fiyat": "Current Price",
    "Prim / İskonto": "Premium / Discount",
})
implied.index.name = "Multiple"
currency = str(target["Currency"])

section(f"{target['Company']} ({target.name})")
top_metrics = [
    (f"Current Price (in {currency})", f"{target['Current Price']:,.2f}", str(target["Price Date"])),
    (f"Market Capitalization (in {currency})", _fmt_money(float(target["Market Cap"]), currency), "Equity value"),
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

percent_columns = [
    name for name in ["Revenue Growth", "EBITDA Margin", "Net Margin", "EPS Growth"]
    if name in comparison
]
market_cap_label = f"Market Capitalization (in {currency} millions)"
display_comparison = comparison.rename(columns={"Market Cap": market_cap_label}).copy()
display_comparison[market_cap_label] = pd.to_numeric(display_comparison[market_cap_label], errors="coerce") / 1_000_000
formats = {column: "{:.1f}x" for column in ["P/E", "EV/EBITDA", "P/S", "P/B", "Forward P/E", "PEG"] if column in display_comparison}
formats.update({column: "{:.1%}" for column in percent_columns})
formats[market_cap_label] = "{:,.1f}"
st.dataframe(display_comparison.style.format(formats, na_rep="N/M")
             .background_gradient(subset=[c for c in ["P/E", "EV/EBITDA", "P/S", "P/B"] if c in display_comparison],
                                  cmap="RdYlGn_r"),
             use_container_width=True, height=min(490, 75 + 36 * len(display_comparison)))
st.caption(f"Source: {package['source']} · Target financial period: {target['Financial Date']} · "
           f"Price date: {target['Price Date']} · Peer count: {len(peers)}")

section("Comparable Similarity")
st.caption(
    "Each available criterion is scored from 0% to 100%. The weighted total is divided by the "
    "available-weight denominator, so missing provider fields are excluded rather than assigned synthetic scores."
)
with st.expander("Similarity Weights", expanded=True):
    weight_columns = st.columns(4)
    similarity_weights = {}
    for index, criterion in enumerate(SIMILARITY_CRITERIA):
        with weight_columns[index % 4]:
            similarity_weights[criterion] = st.number_input(
                criterion,
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                key=f"similarity_weight_{criterion}",
                help="Weights must total 100%. Scores with unavailable source data are excluded from the peer-specific denominator.",
            ) / 100
    total_weight = sum(similarity_weights.values())
    st.metric("Total Weight", f"{total_weight:.1%}")

if not np.isclose(total_weight, 1.0, atol=1e-6):
    st.warning(f"Similarity weights must total 100%. Current total: {total_weight:.1%}.")
else:
    similarity = comparable_similarity(target.to_dict(), peers, similarity_weights)
    if similarity.empty:
        st.info("Comparable similarity could not be calculated because no peer observations were available.")
    else:
        unavailable = [
            criterion for criterion in SIMILARITY_CRITERIA
            if similarity[f"{criterion} Score"].isna().all()
        ]
        if unavailable:
            st.info(
                "Data unavailable across the peer set: "
                + ", ".join(unavailable)
                + ". These criteria are shown as Data unavailable and excluded from the score denominator."
            )
        similarity_display = similarity.reset_index()
        ordered_columns = ["Similarity Rank", "Ticker", "Comparable Company"]
        for criterion in SIMILARITY_CRITERIA:
            ordered_columns.extend([f"{criterion} Score", f"{criterion} Weight"])
        ordered_columns.extend(["Weighted Total", "Available Weight", "Overall Similarity"])
        similarity_display = similarity_display[ordered_columns]
        similarity_formats = {
            column: "{:.1%}" for column in similarity_display.columns
            if column.endswith(" Score") or column.endswith(" Weight")
        }
        similarity_formats.update({
            "Weighted Total": "{:.1%}",
            "Available Weight": "{:.1%}",
            "Overall Similarity": "{:.1%}",
        })
        st.dataframe(
            similarity_display.style.format(similarity_formats, na_rep="Data unavailable")
            .background_gradient(subset=["Overall Similarity"], cmap="YlGn"),
            hide_index=True,
            width="stretch",
        )

section("Peer Company Medians")
median_items = [
    ("P/E", median.get("P/E"), "x"),
    ("EV/EBITDA", median.get("EV/EBITDA"), "x"),
    ("P/Sales", median.get("P/S"), "x"),
    ("P/Book", median.get("P/B"), "x"),
    ("Revenue Growth", median.get("Revenue Growth"), "%"),
    ("EBITDA Margin", median.get("EBITDA Margin"), "%"),
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

section("Peer Multiple Distribution and Outliers")
multiple_stats = peer_multiple_statistics(peers)
if multiple_stats.empty:
    st.info("Peer quartiles and means are unavailable because no valid positive multiples were found.")
else:
    st.dataframe(
        multiple_stats.reset_index().style.format({
            "25th Percentile": "{:.1f}x",
            "Median": "{:.1f}x",
            "Mean": "{:.1f}x",
            "75th Percentile": "{:.1f}x",
        }, na_rep="N/M"),
        hide_index=True,
        width="stretch",
    )
    outlier_table = identify_multiple_outliers(peers)
    if outlier_table.empty:
        st.success("No extreme peer multiples were identified under the 1.5×IQR rule.")
    else:
        with st.expander("Identified Multiple Outliers"):
            st.dataframe(
                outlier_table.style.format({"Observed Value": "{:.1f}x"}),
                hide_index=True,
                width="stretch",
            )

section("Multiple-Implied Share Price")
if implied.empty:
    st.warning("No valid combination of trading multiples and positive target fundamentals was available.")
else:
    money_columns = {
        "Implied Enterprise Value": f"Implied Enterprise Value (in {currency} millions)",
        "Net Debt Adjustment": f"Net Debt Adjustment (in {currency} millions)",
        "Implied Equity Value": f"Implied Equity Value (in {currency} millions)",
        "Implied Price at 25th Percentile": f"Implied Price at 25th Percentile (in {currency} per share)",
        "Implied Price": f"Implied Price (in {currency} per share)",
        "Implied Price at 75th Percentile": f"Implied Price at 75th Percentile (in {currency} per share)",
        "Current Price": f"Current Price (in {currency} per share)",
    }
    present_money_columns = {
        source: label for source, label in money_columns.items() if source in implied.columns
    }
    implied_display = implied.rename(columns=present_money_columns).copy()
    for source in ["Implied Enterprise Value", "Net Debt Adjustment", "Implied Equity Value"]:
        if source in present_money_columns:
            label = present_money_columns[source]
            implied_display[label] = pd.to_numeric(implied_display[label], errors="coerce") / 1_000_000
    implied_formats = {
        "Peer 25th Percentile": "{:.1f}x",
        "Peer Median": "{:.1f}x",
        "Peer Mean": "{:.1f}x",
        "Peer 75th Percentile": "{:.1f}x",
        "Target Multiple": "{:.1f}x",
        "Premium / Discount": "{:+.1%}",
    }
    for source, label in present_money_columns.items():
        implied_formats[label] = "{:,.1f}" if source in {
            "Implied Enterprise Value",
            "Net Debt Adjustment",
            "Implied Equity Value",
        } else "{:,.2f}"
    st.dataframe(
        implied_display.style.format(implied_formats, na_rep="N/M"),
        width="stretch",
    )
    prices = implied["Implied Price"]
    blended = prices.median()
    result_metrics = [
        (f"Blended Midpoint (in {currency} per share)", f"{blended:,.2f}", f"{blended/target['Current Price']-1:+.1%} vs. current price"),
        (f"Valuation Range (in {currency} per share)", f"{prices.min():,.2f} – {prices.max():,.2f}", "Low to high implied price"),
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
    preferred_order = ["EV/EBITDA", "P/E", "P/S", "P/B"]
    selected_multiple = next((item for item in preferred_order if item in implied.index), None)
    if selected_multiple:
        selected = implied.loc[selected_multiple]
        selection_reason = {
            "EV/EBITDA": "selected because it reduces capital-structure differences and the target has positive EBITDA",
            "P/E": "selected because EV/EBITDA was unavailable and the target has positive net income",
            "P/S": "selected because earnings-based multiples were unavailable",
            "P/B": "selected as the remaining valid balance-sheet-based reference",
        }[selected_multiple]
        target_multiple = selected["Target Multiple"]
        premium_discount = target_multiple / selected["Peer Median"] - 1 if np.isfinite(target_multiple) else np.nan
        premium_text = f"{premium_discount:+.1%} versus peer median" if np.isfinite(premium_discount) else "Target multiple unavailable"
        banner(
            "Selected Multiple",
            f"{selected_multiple} at {selected['Peer Median']:.1f}x peer median; {selection_reason}. "
            f"Target trading multiple: {target_multiple:.1f}x ({premium_text}).",
        )
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
