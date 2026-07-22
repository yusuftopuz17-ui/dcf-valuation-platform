"""Streamlit-aware cached market-data adapters."""

from __future__ import annotations

import streamlit as st

from valuation_platform.data import download_company


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def cached_company(ticker: str, historical_years: int):
    """Cache each company independently for six hours."""
    return download_company(ticker, historical_years)


def clear_market_cache() -> None:
    cached_company.clear()

