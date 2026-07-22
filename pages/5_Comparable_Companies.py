"""Comparable-company analysis page."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.formatting import percent
from src.ui import footer, page_header, require_results, section
from src.visualizations import COLORS, layout, peer_heatmap, peer_scatter


page_header("Benzer Şirketler", "Ticari çarpanlar, aykırı değerler, prim/iskonto ve ima edilen değerler.")
r = require_results()
if r is None: footer(); st.stop()
peers = r["peer_multiples"]
section("Benzer Şirket Tablosu")
st.dataframe(peers, use_container_width=True, height=390)
if not r["failed_peers"].empty:
    st.warning("İndirilemeyen şirketler diğer geçerli şirketleri durdurmadı.")
    st.dataframe(r["failed_peers"], use_container_width=True)
tabs = st.tabs(["Dahil Edilenler", "Hariç Tutulan Gözlemler", "Özet İstatistikler"])
with tabs[0]: st.dataframe(r["clean_peers"], use_container_width=True)
with tabs[1]:
    if r["exclusions"].empty: st.success("Seçilen çarpanlarda hariç tutulan gözlem yok.")
    else: st.dataframe(r["exclusions"], use_container_width=True)
with tabs[2]:
    cols = [x for x in r["comparable_config"].selected_multiples if x in peers]
    summary = peers[cols].describe(percentiles=[.25, .5, .75]).T.rename(columns={"min": "Minimum", "25%": "25. Yüzdelik", "50%": "Medyan", "mean": "Ortalama", "75%": "75. Yüzdelik", "max": "Maksimum"})
    st.dataframe(summary[["Minimum", "25. Yüzdelik", "Medyan", "Ortalama", "75. Yüzdelik", "Maksimum"]], use_container_width=True)
section("Piyasa Görselleri")
st.plotly_chart(peer_heatmap(peers), use_container_width=True, key="comp_heat")
c1, c2 = st.columns(2)
with c1: st.plotly_chart(peer_scatter(peers, "Revenue Growth", "EV/Revenue", "Hasılat Büyümesi ve EV/Hasılat"), use_container_width=True, key="comp_growth")
with c2: st.plotly_chart(peer_scatter(peers, "EBITDA Margin", "EV/EBITDA", "EBITDA Marjı ve EV/EBITDA"), use_container_width=True, key="comp_margin")
cols = ["EV/Revenue", "EV/EBITDA", "P/E"]
fig = go.Figure()
for index, metric in enumerate(cols):
    fig.add_trace(go.Box(x=peers[metric], name=metric, boxpoints="all", marker_color=[COLORS["blue"], COLORS["teal"], COLORS["purple"]][index]))
st.plotly_chart(layout(fig, "Çarpan Dağılımları"), use_container_width=True, key="comp_boxes")
selected = [x for x in r["comparable_config"].selected_multiples if x in peers]
target_row = r["target_multiple"]
premiums = [target_row.get(metric, np.nan) / r["clean_peers"][metric].median() - 1 for metric in selected]
fig = go.Figure(go.Bar(x=selected, y=premiums,
                       marker_color=[COLORS["green"] if value >= 0 else COLORS["red"] for value in premiums],
                       text=[percent(value) for value in premiums]))
st.plotly_chart(layout(fig, "Hedef Şirketin Benzer Medyanına Primi / İskontosu", y_format=".1%"), use_container_width=True, key="comp_premium")
section("İma Edilen Değerleme")
st.dataframe(r["implied_values"].style.format({"Selected Multiple": "{:.1f}x", "Implied EV": "${:,.0f}", "Net Debt Adjustment": "${:,.0f}", "Implied Equity": "${:,.0f}", "Implied Price": "${:,.2f}", "Upside": "{:.1%}"}), use_container_width=True, height=420)
footer()
