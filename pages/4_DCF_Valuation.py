"""DCF valuation workspace."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.formatting import money, percent
from src.ui import banner, footer, kpi, page_header, require_results, section
from src.visualizations import COLORS, bridge_chart, layout, valuation_comparison


page_header("DCF Değerleme", "WACC, iskonto edilen UFCF, terminal değer ve özsermaye köprüsü.")
r = require_results()
if r is None: footer(); st.stop()
market = r["market"]
section("WACC Modülü")
c1, c2 = st.columns([1, 1.3])
with c1:
    st.dataframe(r["wacc_bridge"].style.format({"Oran": "{:.2%}", "Ağırlık": "{:.2%}", "Katkı": "{:.2%}"}), use_container_width=True)
with c2:
    parts = r["wacc_bridge"].query("Bileşen in ['Özsermaye Maliyeti','Vergi Sonrası Borç Maliyeti']")
    fig = go.Figure(go.Bar(x=parts["Bileşen"], y=parts["Katkı"], marker_color=[COLORS["teal"], COLORS["purple"]]))
    fig.add_hline(y=r["wacc"], line_dash="dash", line_color=COLORS["amber"], annotation_text=f"WACC {r['wacc']:.1%}")
    st.plotly_chart(layout(fig, "WACC Katkı Köprüsü", y_format=".1%"), use_container_width=True, key="dcf_wacc")
st.plotly_chart(layout(go.Figure(go.Pie(labels=["Özsermaye", "Borç"], values=[market["Market Cap"], market["Debt"]], hole=.62,
                                             marker_colors=[COLORS["teal"], COLORS["purple"]])), "Sermaye Yapısı"),
                use_container_width=True, key="dcf_capital_structure")
section("DCF Hesabı")
method = st.segmented_control("Terminal yöntem", ["Sürekli Büyüme", "Çıkış Çarpanı"], default="Sürekli Büyüme")
result = r["dcf_pg"] if method == "Sürekli Büyüme" else r["dcf_exit"]
c1, c2, c3, c4 = st.columns(4)
with c1: kpi("İma Edilen Hisse Değeri", money(result["Implied Price"], market["Currency"]), percent(result["Upside"]), "positive" if result["Upside"] >= 0 else "negative")
with c2: kpi("İşletme Değeri", money(result["Enterprise Value"], market["Currency"], True), "PV UFCF + PV terminal", "info")
with c3: kpi("Özsermaye Değeri", money(result["Equity Value"], market["Currency"], True), "Net borç sonrası", "info")
with c4: kpi("Terminal Değer Katkısı", percent(result["Terminal Value % EV"]), "İşletme değerine oran", "neutral")
discount = pd.DataFrame({"UFCF": r["forecast"]["UFCF"], "İskonto Dönemi": np.arange(1, len(r["forecast"]) + 1) - (.5 if r["config"].mid_year_discounting else 0),
                         "İskonto Faktörü": result["Discount Factors"], "UFCF Bugünkü Değeri": result["PV UFCF"]})
st.dataframe(discount.style.format({"UFCF": "${:,.0f}", "İskonto Dönemi": "{:.1f}", "İskonto Faktörü": "{:.4f}", "UFCF Bugünkü Değeri": "${:,.0f}"}), use_container_width=True)
c1, c2 = st.columns(2)
with c1:
    fig = go.Figure(go.Bar(x=["Tahmin UFCF PV", "Terminal Değer PV"], y=[result["PV Forecast UFCF"], result["PV Terminal Value"]], marker_color=[COLORS["teal"], COLORS["purple"]]))
    st.plotly_chart(layout(fig, "Bugünkü Değer Ayrışımı"), use_container_width=True, key="dcf_pv")
with c2: st.plotly_chart(bridge_chart(r["bridge"]), use_container_width=True, key="dcf_bridge")
st.plotly_chart(valuation_comparison(r), use_container_width=True, key="dcf_compare")
warnings = r["checks"].query("Durum != 'OK'")
if not warnings.empty:
    banner("Model Uyarıları", " | ".join(f"{row.Kontrol}: {row.Sonuç}" for row in warnings.itertuples()))
footer()
