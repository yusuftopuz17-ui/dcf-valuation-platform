"""Executive summary page."""

import streamlit as st

from src.formatting import money, percent
from src.ui import banner, comments, footer, kpi, page_header, recommendation, require_results, section
from src.visualizations import bridge_chart, football_field, historical_forecast, scenarios_chart, valuation_comparison


page_header("Yönetici Özeti", "Değerleme sonuçları, fiyat farkı, aralık ve temel riskler tek görünümde.")
results = require_results()
if results is None:
    footer(); st.stop()
market = results["market"]; currency = market["Currency"]
st.caption(f"{market['Company']} | {market['Ticker']} | {market['Sector']} | {market['Industry']} | Veri tarihi: {market['Price Date']} | Alım zamanı: {market['Retrieved At'][:19]}")

columns = st.columns(3)
with columns[0]: kpi("Mevcut Hisse Fiyatı", money(market["Current Price"], currency), market["Price Date"], "info")
with columns[1]: kpi("DCF - Sürekli Büyüme", money(results["dcf_pg"]["Implied Price"], currency), percent(results["dcf_pg"]["Upside"]), "positive" if results["dcf_pg"]["Upside"] >= 0 else "negative")
with columns[2]: kpi("Benzer Şirketler", money(results["peer_median_price"], currency), "Medyan çarpanlar", "info")
columns = st.columns(3)
with columns[0]: kpi("Harmanlanmış Değer", money(results["blended_value"], currency), percent(results["upside"]), "positive" if results["upside"] >= 0 else "negative")
with columns[1]: kpi("İşletme Değeri", money(results["dcf_pg"]["Enterprise Value"], currency, True), "DCF - sürekli büyüme", "info")
with columns[2]: kpi("Özsermaye Değeri", money(results["dcf_pg"]["Equity Value"], currency, True), "Borç ve nakit sonrası", "info")
columns = st.columns(3)
with columns[0]: kpi("WACC", percent(results["wacc"]), "Ağırlıklı sermaye maliyeti", "neutral")
with columns[1]: kpi("Terminal Değer / EV", percent(results["dcf_pg"]["Terminal Value % EV"]), "Uzun vadeli varsayım yoğunluğu", "neutral")
with columns[2]: kpi("DCF - Çıkış Çarpanı", money(results["dcf_exit"]["Implied Price"], currency), f"{results['dcf_exit']['Exit Multiple']:.1f}x", "info")

label, text = recommendation(results); banner(label, text)
section("Değerleme Görselleri")
st.plotly_chart(football_field(results["football"], market["Current Price"], results["blended_value"]), use_container_width=True, key="exec_football")
c1, c2 = st.columns(2)
with c1: st.plotly_chart(historical_forecast(results["financials"], results["forecast"]), use_container_width=True, key="exec_revenue")
with c2: st.plotly_chart(valuation_comparison(results), use_container_width=True, key="exec_methods")
c1, c2 = st.columns(2)
with c1: st.plotly_chart(bridge_chart(results["bridge"]), use_container_width=True, key="exec_bridge")
with c2: st.plotly_chart(scenarios_chart(results["scenarios"], market["Current Price"]), use_container_width=True, key="exec_scenarios")
section("Temel Bulgular")
comments(results["commentary"])
footer()

