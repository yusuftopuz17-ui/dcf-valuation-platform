"""Sensitivity and scenario analysis page."""

import streamlit as st

from src.formatting import money, percent
from src.ui import comments, footer, kpi, page_header, require_results, section
from src.visualizations import heatmap, scenarios_chart


page_header("Duyarlılık ve Senaryolar", "WACC, terminal değer, büyüme ve marj belirsizliklerinin değer üzerindeki etkisi.")
r = require_results()
if r is None: footer(); st.stop()
current = r["market"]["Current Price"]
section("DCF Duyarlılıkları")
tabs = st.tabs(["WACC / Terminal Büyüme", "WACC / Çıkış Çarpanı", "Hasılat Büyümesi / EBITDA Marjı"])
with tabs[0]: st.plotly_chart(heatmap(r["sensitivities"]["WACC / Terminal Growth"], "WACC ve Terminal Büyüme", current), use_container_width=True, key="sens_pg")
with tabs[1]: st.plotly_chart(heatmap(r["sensitivities"]["WACC / Exit Multiple"], "WACC ve Çıkış EV/EBITDA", current), use_container_width=True, key="sens_exit")
with tabs[2]: st.plotly_chart(heatmap(r["operating_sensitivity"], "Hasılat Büyümesi ve EBITDA Marjı", current), use_container_width=True, key="sens_ops")
comments(["Düşük WACC ve yüksek terminal büyüme kombinasyonu en yüksek DCF değerlerini üretir; iki değişken birlikte terminal değer üzerinde bileşik etki yaratır.",
          "Operasyonel duyarlılık tablosu yalnızca sonuç hücresini değiştirmez; her büyüme ve marj kombinasyonunda tahmin modeli ve DCF yeniden hesaplanır.",
          f"Mevcut hisse fiyatı {money(current, r['market']['Currency'])}; ısı haritalarındaki renk merkezi bu referans fiyattır."])
section("Senaryo Analizi")
scenario = r["scenarios"]
for column, (_, row) in zip(st.columns(3), scenario.iterrows()):
    with column:
        kpi(row["Scenario"], money(row["Implied Price"], r["market"]["Currency"]), f"Fark {percent(row['Upside'])} | TV/EV {percent(row['Terminal Value % EV'])}",
            "positive" if row["Scenario"] == "Bull" else ("negative" if row["Scenario"] == "Bear" else "info"))
st.plotly_chart(scenarios_chart(scenario, current), use_container_width=True, key="scenario_chart")
st.dataframe(scenario.style.format({"Year 1 Growth": "{:.1%}", "Final EBITDA Margin": "{:.1%}", "WACC": "{:.1%}", "Terminal Growth": "{:.1%}", "Exit Multiple": "{:.1f}x", "Enterprise Value": "${:,.0f}", "Equity Value": "${:,.0f}", "Implied Price": "${:,.2f}", "Upside": "{:.1%}", "Terminal Value % EV": "{:.1%}"}), use_container_width=True)
footer()
