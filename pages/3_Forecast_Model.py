"""Forecast operating model page."""

from dataclasses import replace

import pandas as pd
import streamlit as st

from src.formatting import percent
from src.ui import comments, footer, page_header, require_results, section
from src.visualizations import fcf_bridge, historical_forecast, margin_chart
from valuation_platform.model import forecast as build_forecast


page_header("Tahmin Modeli", "Kullanıcı varsayımlarını hasılat, kârlılık, yeniden yatırım ve UFCF'ye dönüştüren işletme modeli.")
r = require_results()
if r is None: footer(); st.stop()
scenario = st.segmented_control("Senaryo görünümü", ["Bear", "Base", "Bull"], default="Base")
shifts = {"Bear": (-.03, -.03), "Base": (0, 0), "Bull": (.03, .03)}
growth_shift, margin_shift = shifts[scenario]
case = replace(r["forecast_assumptions"],
               revenue_growth=[x + growth_shift for x in r["forecast_assumptions"].revenue_growth],
               ebitda_margin=[x + margin_shift for x in r["forecast_assumptions"].ebitda_margin])
selected_forecast = build_forecast(r["financials"].iloc[-1], case, r["config"].forecast_years)
section("Tarihsel ve Tahmini İşletme Modeli")
history = r["financials"][["Revenue", "EBITDA", "D&A", "EBIT", "Capital Expenditure", "NWC"]].copy()
history.columns = ["Revenue", "EBITDA", "D&A", "EBIT", "Capex", "NWC"]
history["Period Type"] = "Tarihsel"
forecast = selected_forecast.copy(); forecast["Period Type"] = f"{scenario} Tahmini"
st.dataframe(pd.concat([history, forecast], axis=0), use_container_width=True, height=420)
section("Tahmin Sürücüleri")
c1, c2, c3 = st.columns(3)
c1.metric("İlk Yıl Büyüme", percent(selected_forecast["Revenue Growth"].iloc[0]))
c2.metric("Son Yıl EBITDA Marjı", percent(selected_forecast["EBITDA Margin"].iloc[-1]))
c3.metric("Son Yıl UFCF", f"${selected_forecast['UFCF'].iloc[-1]/1e9:,.1f}B")
c1, c2 = st.columns(2)
with c1: st.plotly_chart(historical_forecast(r["financials"], selected_forecast), use_container_width=True, key="forecast_revenue")
with c2: st.plotly_chart(margin_chart(r["historical_metrics"], selected_forecast), use_container_width=True, key="forecast_margin")
st.plotly_chart(fcf_bridge(selected_forecast), use_container_width=True, key="forecast_fcf")
section("Model Yorumu")
comments([f"{scenario} senaryosunda hasılat büyümesi ilk tahmin yılında {percent(selected_forecast['Revenue Growth'].iloc[0])} seviyesinden son yılda {percent(selected_forecast['Revenue Growth'].iloc[-1])} seviyesine yakınsamaktadır.",
          f"EBITDA marjı tahmin döneminde {percent(selected_forecast['EBITDA Margin'].iloc[0])} ile başlayıp {percent(selected_forecast['EBITDA Margin'].iloc[-1])} seviyesine ulaşmaktadır.",
          "D&A, Capex ve net işletme sermayesi hasılat yüzdesi olarak modellenir; bu sürücüler UFCF dönüşümünü doğrudan etkiler."])
footer()
