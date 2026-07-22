"""Financial and market-data ingestion with explicit data-quality behavior."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


class DataError(RuntimeError):
    """Financially meaningful data-ingestion error."""


LABELS = {
    "Revenue": ("Total Revenue", "Operating Revenue"),
    "Gross Profit": ("Gross Profit",),
    "EBITDA": ("EBITDA", "Normalized EBITDA"),
    "EBIT": ("EBIT", "Operating Income"),
    "Operating Income": ("Operating Income",),
    "Net Income": ("Net Income", "Net Income Common Stockholders"),
    "Tax Expense": ("Tax Provision",),
    "Interest Expense": ("Interest Expense", "Interest Expense Non Operating"),
    "Diluted Shares": ("Diluted Average Shares", "Ordinary Shares Number"),
    "D&A": ("Reconciled Depreciation", "Depreciation And Amortization", "Depreciation"),
    "Capital Expenditure": ("Capital Expenditure", "Capital Expenditures"),
    "Cash": ("Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"),
    "Debt": ("Total Debt", "Long Term Debt And Capital Lease Obligation", "Long Term Debt"),
    "Equity": ("Stockholders Equity", "Total Equity Gross Minority Interest"),
    "Accounts Receivable": ("Accounts Receivable", "Receivables"),
    "Inventory": ("Inventory",),
    "Accounts Payable": ("Accounts Payable", "Payables"),
}


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    out = frame.copy()
    out.columns = pd.to_datetime(out.columns, errors="coerce")
    return out.loc[:, ~out.columns.isna()].loc[:, ~out.columns.duplicated()].sort_index(axis=1)


def _row(frame: pd.DataFrame, labels: tuple[str, ...]) -> pd.Series:
    for label in labels:
        if label in frame.index:
            return pd.to_numeric(frame.loc[label], errors="coerce")
    return pd.Series(dtype=float)


def download_company(ticker: str, historical_years: int = 5, raw_dir: str | Path | None = None) -> dict[str, Any]:
    """Download annual statements, profile, and price history from Yahoo Finance."""
    try:
        import yfinance as yf
        obj = yf.Ticker(ticker)
        income = _normalize(obj.financials)
        balance = _normalize(obj.balance_sheet)
        cashflow = _normalize(obj.cashflow)
        profile = obj.info or {}
        history = obj.history(period=f"{max(historical_years + 1, 6)}y", auto_adjust=False)
    except Exception as exc:
        raise DataError(f"{ticker} için Yahoo Finance bağlantısı başarısız: {exc}") from exc
    missing = [name for name, frame in (("gelir tablosu", income), ("bilanço", balance), ("nakit akışı", cashflow)) if frame.empty]
    if missing:
        raise DataError(f"{ticker} için eksik finansal tablolar: {', '.join(missing)}")
    if history.empty or "Close" not in history:
        raise DataError(f"{ticker} için güncel fiyat bulunamadı.")
    retrieved = datetime.now(UTC).isoformat()
    if raw_dir:
        root = Path(raw_dir); root.mkdir(parents=True, exist_ok=True)
        income.T.to_csv(root / f"{ticker}_income.csv", index_label="Period")
        balance.T.to_csv(root / f"{ticker}_balance.csv", index_label="Period")
        cashflow.T.to_csv(root / f"{ticker}_cashflow.csv", index_label="Period")
        history.to_csv(root / f"{ticker}_prices.csv", index_label="Date")
    return {"ticker": ticker, "income": income, "balance": balance, "cashflow": cashflow,
            "profile": profile, "history": history, "retrieved_at": retrieved,
            "source_url": f"https://finance.yahoo.com/quote/{ticker}"}


def standardize(raw: dict[str, Any], historical_years: int = 5) -> pd.DataFrame:
    """Standardize heterogeneous provider labels without silently filling material fields."""
    income, balance, cashflow = raw["income"], raw["balance"], raw["cashflow"]
    periods = sorted(set(income.columns) | set(balance.columns) | set(cashflow.columns))[-historical_years:]
    statement = {
        "Revenue": income, "Gross Profit": income, "EBITDA": income, "EBIT": income,
        "Operating Income": income, "Net Income": income, "Tax Expense": income,
        "Interest Expense": income, "Diluted Shares": income, "D&A": cashflow,
        "Capital Expenditure": cashflow, "Cash": balance, "Debt": balance, "Equity": balance,
        "Accounts Receivable": balance, "Inventory": balance, "Accounts Payable": balance,
    }
    out = pd.DataFrame(index=pd.DatetimeIndex(periods, name="Period"))
    for metric, source in statement.items():
        series = _row(source, LABELS[metric])
        out[metric] = series.reindex(periods).to_numpy(dtype=float) if not series.empty else np.nan
    out["Capital Expenditure"] = out["Capital Expenditure"].abs()
    out["EBIT"] = out["EBIT"].fillna(out["Operating Income"])
    out["EBITDA"] = out["EBITDA"].fillna(out["EBIT"] + out["D&A"])
    out["NWC"] = out["Accounts Receivable"].fillna(0) + out["Inventory"].fillna(0) - out["Accounts Payable"].fillna(0)
    out["Net Debt"] = out["Debt"] - out["Cash"]
    if out["Revenue"].notna().sum() < 3:
        raise DataError(f"{raw['ticker']} için en az üç yıllık hasılat bulunamadı.")
    return out.sort_index()


def snapshot(raw: dict[str, Any], financials: pd.DataFrame) -> dict[str, Any]:
    """Construct a market-value snapshot with transparent statement fallbacks."""
    info = raw["profile"]
    close = pd.to_numeric(raw["history"]["Close"], errors="coerce").dropna()
    current_price = float(close.iloc[-1])
    def number(key: str, fallback: float) -> float:
        value = pd.to_numeric(info.get(key), errors="coerce")
        return float(value) if np.isfinite(value) else float(fallback)
    shares_history = financials["Diluted Shares"].dropna()
    if info.get("sharesOutstanding") is None and shares_history.empty:
        raise DataError(f"{raw['ticker']} için seyreltilmiş hisse sayısı bulunamadı.")
    shares = number("sharesOutstanding", shares_history.iloc[-1] if not shares_history.empty else np.nan)
    debt = float(financials["Debt"].dropna().iloc[-1]) if financials["Debt"].notna().any() else number("totalDebt", 0)
    cash = float(financials["Cash"].dropna().iloc[-1]) if financials["Cash"].notna().any() else number("totalCash", 0)
    market_cap = number("marketCap", current_price * shares)
    return {"Ticker": raw["ticker"], "Company": info.get("longName", raw["ticker"]),
            "Sector": info.get("sector", "Bilinmiyor"), "Industry": info.get("industry", "Bilinmiyor"),
            "Currency": info.get("currency", "USD"), "Current Price": current_price,
            "Price Date": str(close.index[-1].date()), "Shares": shares, "Market Cap": market_cap,
            "Debt": debt, "Cash": cash, "Net Debt": debt - cash,
            "Enterprise Value": number("enterpriseValue", market_cap + debt - cash),
            "Beta": number("beta", 1.0), "Retrieved At": raw["retrieved_at"], "Source URL": raw["source_url"]}


def quality_checks(financials: pd.DataFrame, market: dict[str, Any], expected_currency: str) -> pd.DataFrame:
    """Return visible completeness and consistency controls."""
    rows = []
    for metric in ["Revenue", "EBITDA", "EBIT", "Net Income", "D&A", "Capital Expenditure", "Cash", "Debt", "Diluted Shares"]:
        missing = int(financials[metric].isna().sum())
        rows.append({"Kontrol": f"{metric} eksik dönem", "Sonuç": missing, "Durum": "OK" if missing == 0 else "İNCELE"})
    price_age = (pd.Timestamp.now(tz="UTC").normalize() - pd.Timestamp(market["Price Date"], tz="UTC")).days
    rows += [
        {"Kontrol": "Para birimi", "Sonuç": market["Currency"], "Durum": "OK" if market["Currency"] == expected_currency else "İNCELE"},
        {"Kontrol": "Hisse sayısı", "Sonuç": market["Shares"], "Durum": "OK" if market["Shares"] > 0 else "HATA"},
        {"Kontrol": "Güncel fiyat", "Sonuç": market["Current Price"], "Durum": "OK" if market["Current Price"] > 0 else "HATA"},
        {"Kontrol": "Fiyat verisi yaşı", "Sonuç": f"{price_age} gün", "Durum": "OK" if price_age <= 10 else "İNCELE"},
    ]
    return pd.DataFrame(rows)
