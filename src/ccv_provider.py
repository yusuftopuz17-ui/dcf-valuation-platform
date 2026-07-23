"""Replaceable public-market provider adapter for the CCV workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np
import pandas as pd
import streamlit as st

from valuation_platform.data import DataError, snapshot, standardize
from .data_loader import cached_company


class PublicMarketProvider(Protocol):
    def search(self, query: str) -> list[dict[str, Any]]: ...
    def discover(self, sector: str, limit: int = 20) -> list[str]: ...
    def company(self, ticker: str, years: int = 5, period: str = "TTM") -> dict[str, Any]: ...


@dataclass(frozen=True)
class YahooFinanceProvider:
    name: str = "Yahoo Finance"

    def search(self, query: str) -> list[dict[str, Any]]:
        return search_yahoo(query)

    def discover(self, sector: str, limit: int = 20) -> list[str]:
        return discover_yahoo_candidates(sector, limit)

    def company(self, ticker: str, years: int = 5, period: str = "TTM") -> dict[str, Any]:
        return company_record(ticker, years, period)


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def search_yahoo(query: str) -> list[dict[str, Any]]:
    """Resolve names/tickers without silently choosing an ambiguous match."""
    if not query.strip():
        return []
    try:
        import yfinance as yf
        quotes = yf.Search(query.strip(), max_results=10).quotes
    except Exception as exc:
        raise DataError(f"Şirket araması başarısız: {exc}") from exc
    rows = []
    for quote in quotes:
        if quote.get("quoteType") not in {"EQUITY", None} or not quote.get("symbol"):
            continue
        rows.append({
            "Company": quote.get("longname") or quote.get("shortname") or quote["symbol"],
            "Ticker": quote["symbol"],
            "Exchange": quote.get("exchange") or quote.get("exchDisp") or "Bilinmiyor",
            "Country": quote.get("country") or "Bilinmiyor",
            "Sector": quote.get("sector") or "Bilinmiyor",
            "Currency": quote.get("currency") or "Bilinmiyor",
        })
    return rows


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def discover_yahoo_candidates(sector: str, limit: int = 20) -> list[str]:
    """Discover real listed candidates through Yahoo's equity screener."""
    sector_map = {
        "Industrials": "Industrials", "Construction & Commercial Trades": "Industrials",
        "Manufacturing": "Industrials", "Consumer": "Consumer Cyclical", "Healthcare": "Healthcare",
        "Technology": "Technology", "Business Services": "Industrials",
        "Transportation & Logistics": "Industrials", "Residential Trades": "Consumer Cyclical",
        "Energy & Environment": "Energy",
    }
    provider_sector = sector_map.get(sector, sector)
    if not provider_sector or provider_sector == "Other":
        raise DataError("Otomatik tarama için standart bir sektör seçin veya aday sembolleri manuel girin.")
    try:
        import yfinance as yf
        query = yf.EquityQuery("eq", ["sector", provider_sector])
        response = yf.screen(query, size=min(max(limit, 5), 50), sortField="intradaymarketcap", sortAsc=False)
        quotes = response.get("quotes", [])
        symbols = [quote.get("symbol") for quote in quotes if quote.get("symbol")]
    except Exception as exc:
        raise DataError(f"Yahoo sektör taraması başarısız: {exc}") from exc
    if not symbols:
        raise DataError(f"{provider_sector} sektörü için doğrulanmış aday bulunamadı.")
    return list(dict.fromkeys(symbols))


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def company_record(ticker: str, years: int = 5, period: str = "TTM") -> dict[str, Any]:
    """Return a normalized CCV company record and historical table."""
    raw = cached_company(ticker.upper(), years)
    financials = standardize(raw, years)
    market = snapshot(raw, financials)
    latest = financials.iloc[-1]
    info = raw.get("profile", {})
    revenue = float(latest["Revenue"]) if np.isfinite(latest["Revenue"]) else np.nan
    ebitda = float(latest["EBITDA"]) if np.isfinite(latest["EBITDA"]) else np.nan
    record = {
        "Ticker": ticker.upper(), "Company": market["Company"],
        "Exchange": info.get("exchange") or info.get("fullExchangeName") or "Bilinmiyor",
        "Country": info.get("country") or "Bilinmiyor", "Sector": market["Sector"],
        "Subsector": market["Industry"], "Business Description": info.get("longBusinessSummary") or "Mevcut değil",
        "Business Model": [], "Customer Structure": [], "Geography": [info.get("country")] if info.get("country") else [],
        "Revenue Model": [], "Revenue": revenue, "EBITDA": ebitda,
        "Revenue Growth": float(financials["Revenue"].pct_change().iloc[-1]),
        "EBITDA Margin": ebitda / revenue if revenue > 0 and np.isfinite(ebitda) else np.nan,
        "EBIT": float(latest["EBIT"]) if np.isfinite(latest["EBIT"]) else np.nan,
        "Net Income": float(latest["Net Income"]) if np.isfinite(latest["Net Income"]) else np.nan,
        "Cash": market["Cash"], "Debt": market["Debt"], "Preferred Equity": 0.0,
        "Non-Controlling Interest": 0.0, "Diluted Shares": market["Shares"],
        "Market Cap": market["Market Cap"], "Enterprise Value": market["Enterprise Value"],
        "Current Price": market["Current Price"], "Currency": market["Currency"],
        "Employees": pd.to_numeric(info.get("fullTimeEmployees"), errors="coerce"),
        "Financial Period": f"{period} / sağlayıcıdaki son kullanılabilir mali dönem",
        "Financial Date": str(financials.index[-1].date()), "Price Date": market["Price Date"],
        "Data Source": "Yahoo Finance", "Source URL": market["Source URL"],
        "Retrieved At": market["Retrieved At"],
    }
    return {"record": record, "historical": financials, "raw": raw}


def load_candidate_records(tickers: list[str], years: int = 5, period: str = "TTM") -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    rows, failures, histories = [], [], {}
    for ticker in dict.fromkeys(item.strip().upper() for item in tickers if item.strip()):
        try:
            package = company_record(ticker, years, period)
            rows.append(package["record"])
            histories[ticker] = package["historical"]
        except Exception as exc:
            failures.append({"Ticker": ticker, "Error": str(exc), "Status": "Provider failure"})
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.set_index("Ticker")
    return frame, pd.DataFrame(failures), histories
