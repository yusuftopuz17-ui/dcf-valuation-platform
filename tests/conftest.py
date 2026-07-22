"""Deterministic offline fixtures for valuation and reporting tests."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest


def fake_company(ticker: str, years: int):
    dates = pd.to_datetime(["2021-06-30", "2022-06-30", "2023-06-30", "2024-06-30", "2025-06-30"])
    factor = 1 + (sum(map(ord, ticker)) % 12) / 50
    revenue = np.array([1000, 1100, 1210, 1331, 1464.1]) * 1e6 * factor
    income = pd.DataFrame(index=["Total Revenue", "Gross Profit", "EBITDA", "EBIT", "Operating Income", "Net Income", "Tax Provision", "Interest Expense", "Diluted Average Shares"], columns=dates, dtype=float)
    income.loc["Total Revenue"] = revenue
    income.loc["Gross Profit"] = revenue * .70
    income.loc["EBITDA"] = revenue * (.42 + (factor-1)/10)
    income.loc["EBIT"] = revenue * .37
    income.loc["Operating Income"] = revenue * .37
    income.loc["Net Income"] = revenue * .29
    income.loc["Tax Provision"] = revenue * .08
    income.loc["Interest Expense"] = revenue * .006
    income.loc["Diluted Average Shares"] = 100e6
    balance = pd.DataFrame(index=["Cash Cash Equivalents And Short Term Investments", "Total Debt", "Stockholders Equity", "Accounts Receivable", "Inventory", "Accounts Payable"], columns=dates, dtype=float)
    balance.loc["Cash Cash Equivalents And Short Term Investments"] = revenue * .20
    balance.loc["Total Debt"] = revenue * .10
    balance.loc["Stockholders Equity"] = revenue * .55
    balance.loc["Accounts Receivable"] = revenue * .12
    balance.loc["Inventory"] = revenue * .02
    balance.loc["Accounts Payable"] = revenue * .08
    cashflow = pd.DataFrame(index=["Reconciled Depreciation", "Capital Expenditure"], columns=dates, dtype=float)
    cashflow.loc["Reconciled Depreciation"] = revenue * .04
    cashflow.loc["Capital Expenditure"] = -revenue * .05
    prices = pd.DataFrame({"Close": [20, 22, 25]}, index=pd.to_datetime(["2025-01-01", "2025-06-01", "2025-07-01"]))
    return {"ticker": ticker, "income": income, "balance": balance, "cashflow": cashflow,
            "profile": {"longName": f"{ticker} Corporation", "sector": "Technology", "industry": "Software",
                        "currency": "USD", "sharesOutstanding": 100e6, "marketCap": 2.5e9 * factor,
                        "enterpriseValue": 2.35e9 * factor, "beta": 1.05},
            "history": prices, "retrieved_at": datetime.now(UTC).isoformat(), "source_url": f"https://example.com/{ticker}"}


@pytest.fixture
def results():
    from valuation_platform import ComparableConfig, ForecastAssumptions, TerminalAssumptions, ValuationConfig, WACCAssumptions, run_valuation
    return run_valuation(ValuationConfig("TGT", ["AAA", "BBB", "CCC", "DDD", "EEE"]),
                         ForecastAssumptions([.10, .08, .06, .05, .04], [.44, .45, .46, .47, .48]),
                         WACCAssumptions(), TerminalAssumptions(.025, 14), ComparableConfig(), company_loader=fake_company)

