"""End-to-end valuation orchestration shared by every Streamlit page."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from .config import ComparableConfig, ForecastAssumptions, TerminalAssumptions, ValuationConfig, WACCAssumptions
from .data import DataError, download_company, quality_checks, snapshot, standardize
from .model import (commentary, dcf, forecast, historical_metrics, implied_values, operating_sensitivity,
                    outliers, peer_multiples, scenarios, sensitivities, wacc)


def run_valuation(
    config: ValuationConfig,
    forecast_assumptions: ForecastAssumptions,
    wacc_assumptions: WACCAssumptions,
    terminal_assumptions: TerminalAssumptions,
    comparable_config: ComparableConfig,
    *,
    company_loader: Callable[[str, int], dict[str, Any]] | None = None,
    progress: Callable[[int, str], None] | None = None,
    raw_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run the complete valuation while continuing past individual peer failures."""
    forecast_assumptions.validate(config.forecast_years)
    loader = company_loader or (lambda ticker, years: download_company(ticker, years, raw_dir))
    if progress: progress(3, f"{config.target_ticker} finansalları indiriliyor")
    target_raw = loader(config.target_ticker, config.historical_years)
    target_financials = standardize(target_raw, config.historical_years)
    target_market = snapshot(target_raw, target_financials)
    if progress: progress(18, "Geçmiş finansallar standartlaştırılıyor")
    hist_metrics = historical_metrics(target_financials)
    forecast_model = forecast(target_financials.iloc[-1], forecast_assumptions, config.forecast_years)
    wacc_value, wacc_bridge = wacc(wacc_assumptions, target_market["Beta"], target_market["Market Cap"],
                                   max(target_market["Debt"], 0), forecast_assumptions.tax_rate)
    pg = dcf(forecast_model, wacc_value, terminal_assumptions, target_market, config.mid_year_discounting, "perpetuity")
    exit_result = dcf(forecast_model, wacc_value, terminal_assumptions, target_market, config.mid_year_discounting, "exit_multiple")
    if progress: progress(35, "Benzer şirketler indiriliyor")
    peer_data: dict[str, dict[str, Any]] = {}; failed = []
    for index, ticker in enumerate(config.peer_tickers):
        try:
            raw = loader(ticker, config.historical_years)
            financials = standardize(raw, config.historical_years)
            peer_data[ticker] = {"raw": raw, "financials": financials, "market": snapshot(raw, financials)}
        except Exception as exc:
            failed.append({"Ticker": ticker, "Error": str(exc)})
        if progress: progress(35 + int(35 * (index + 1) / max(len(config.peer_tickers), 1)), f"{ticker} işlendi")
    if len(peer_data) < 2:
        raise DataError(f"Değerleme için en az iki geçerli benzer şirket gerekir. Hatalar: {failed}")
    peer_table = peer_multiples(peer_data)
    clean_peers, exclusions = outliers(peer_table, comparable_config.selected_multiples,
                                       comparable_config.outlier_method, comparable_config.outlier_threshold,
                                       comparable_config.manual_exclusions)
    target_multiple = peer_multiples({config.target_ticker: {"financials": target_financials, "market": target_market}}).iloc[0]
    implied = implied_values(clean_peers, target_financials.iloc[-1], target_market, comparable_config.selected_multiples)
    peer_median_price = float(implied.loc[implied["Statistic"].eq("Median"), "Implied Price"].median())
    premium_discount = target_multiple.get("EV/EBITDA", np.nan) / clean_peers["EV/EBITDA"].median() - 1
    sens = sensitivities(forecast_model, wacc_value, terminal_assumptions, target_market, config.mid_year_discounting)
    op_sens = operating_sensitivity(target_financials.iloc[-1], forecast_assumptions, wacc_value,
                                    terminal_assumptions, target_market, config.mid_year_discounting)
    scenario_table = scenarios(target_financials.iloc[-1], forecast_assumptions, wacc_value,
                               terminal_assumptions, target_market, config.mid_year_discounting)
    football_rows = []
    for label, table in (("DCF - Perpetuity Growth", sens["WACC / Terminal Growth"]),
                         ("DCF - Exit Multiple", sens["WACC / Exit Multiple"])):
        values = table.to_numpy().ravel()
        football_rows.append({"Method": label, "Low": np.nanpercentile(values, 25),
                              "Median": np.nanmedian(values), "High": np.nanpercentile(values, 75)})
    for multiple in comparable_config.selected_multiples:
        table = implied[implied["Multiple"].eq(multiple)].set_index("Statistic")["Implied Price"]
        if {"25th Percentile", "Median", "75th Percentile"}.issubset(table.index):
            football_rows.append({"Method": multiple, "Low": table["25th Percentile"],
                                  "Median": table["Median"], "High": table["75th Percentile"]})
    football = pd.DataFrame(football_rows)
    blended = float(np.nanmedian([pg["Implied Price"], exit_result["Implied Price"], peer_median_price]))
    bridge = pd.DataFrame({"Item": ["Enterprise Value", "Debt", "Cash", "Equity Value"],
                           "Value": [pg["Enterprise Value"], -target_market["Debt"], target_market["Cash"], pg["Equity Value"]]})
    sources = pd.DataFrame([{"Item": "Target company", "Ticker": config.target_ticker, "Source": "Yahoo Finance",
                             "URL": target_market["Source URL"], "Retrieved At": target_market["Retrieved At"]}] +
                           [{"Item": "Comparable company", "Ticker": ticker, "Source": "Yahoo Finance",
                             "URL": data["market"]["Source URL"], "Retrieved At": data["market"]["Retrieved At"]}
                            for ticker, data in peer_data.items()])
    checks = quality_checks(target_financials, target_market, config.base_currency)
    extra_checks = pd.DataFrame([
        {"Kontrol": "WACC > terminal büyüme", "Sonuç": wacc_value - terminal_assumptions.terminal_growth_rate,
         "Durum": "OK" if wacc_value > terminal_assumptions.terminal_growth_rate else "HATA"},
        {"Kontrol": "Terminal değer katkısı", "Sonuç": pg["Terminal Value % EV"],
         "Durum": "OK" if pg["Terminal Value % EV"] <= config.terminal_value_warning_threshold else "İNCELE"},
        {"Kontrol": "Özsermaye değeri", "Sonuç": pg["Equity Value"], "Durum": "OK" if pg["Equity Value"] > 0 else "HATA"},
    ])
    result = {"config": config, "forecast_assumptions": forecast_assumptions, "wacc_assumptions": wacc_assumptions,
              "terminal_assumptions": terminal_assumptions, "comparable_config": comparable_config,
              "target_raw": target_raw, "financials": target_financials, "historical_metrics": hist_metrics,
              "market": target_market, "forecast": forecast_model, "wacc": wacc_value, "wacc_bridge": wacc_bridge,
              "dcf_pg": pg, "dcf_exit": exit_result, "peer_data": peer_data, "peer_multiples": peer_table,
              "clean_peers": clean_peers, "exclusions": exclusions, "failed_peers": pd.DataFrame(failed),
              "target_multiple": target_multiple, "implied_values": implied, "peer_median_price": peer_median_price,
              "premium_discount": premium_discount, "sensitivities": sens, "operating_sensitivity": op_sens,
              "scenarios": scenario_table, "football": football, "bridge": bridge, "blended_value": blended,
              "upside": blended / target_market["Current Price"] - 1, "sources": sources,
              "checks": pd.concat([checks, extra_checks], ignore_index=True), "generated_at": datetime.now(UTC).isoformat()}
    result["commentary"] = commentary(result)
    if progress: progress(100, "Değerleme tamamlandı")
    return result
