"""Historical performance analysis page."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.ui import footer, page_header, require_results, section
from src.visualizations import COLORS, layout, margin_chart, revenue_ebitda


page_header("Tarihsel Performans", "Büyüme, marj, nakit dönüşümü, yatırım yoğunluğu ve sermaye getirisi.")
r = require_results()
if r is None: footer(); st.stop()
f, m = r["financials"], r["historical_metrics"]
mode = st.segmented_control("Görünüm", ["Mutlak Değer", "Yüzde", "Endeks (İlk Yıl = 100)"], default="Mutlak Değer")
section("Finansal Tablolar")
tabs = st.tabs(["Gelir Tablosu", "Bilanço Özeti", "Nakit Akışı", "Oranlar"])
def view(frame: pd.DataFrame) -> pd.DataFrame:
    if mode == "Yüzde":
        return frame.div(f["Revenue"], axis=0)
    if mode == "Endeks (İlk Yıl = 100)":
        return frame.div(frame.iloc[0].replace(0, np.nan), axis=1) * 100
    return frame
with tabs[0]: st.dataframe(view(f[["Revenue", "Gross Profit", "EBITDA", "EBIT", "Net Income"]]).T, use_container_width=True)
with tabs[1]: st.dataframe(view(f[["Cash", "Debt", "Net Debt", "Equity", "NWC"]]).T, use_container_width=True)
with tabs[2]: st.dataframe(view(pd.concat([f[["D&A", "Capital Expenditure"]], m[["Free Cash Flow"]]], axis=1)).T, use_container_width=True)
with tabs[3]: st.dataframe(m.T, use_container_width=True)
section("Operasyonel Gelişim")
c1, c2 = st.columns(2)
with c1: st.plotly_chart(revenue_ebitda(f), use_container_width=True, key="hist_revenue")
with c2:
    fig = go.Figure(go.Bar(x=m.index.year.astype(str), y=m["Revenue Growth"], marker_color=COLORS["teal"], text=[f"{x:.1%}" if np.isfinite(x) else "-" for x in m["Revenue Growth"]]))
    st.plotly_chart(layout(fig, "Hasılat Büyümesi", y_format=".1%"), use_container_width=True, key="hist_growth")
c1, c2 = st.columns(2)
with c1: st.plotly_chart(margin_chart(m, r["forecast"]), use_container_width=True, key="hist_margins")
with c2:
    fig = go.Figure()
    fig.add_scatter(x=m.index.year.astype(str), y=m["Cash Conversion"], name="Nakit dönüşümü", mode="lines+markers", line={"color": COLORS["green"]})
    fig.add_scatter(x=m.index.year.astype(str), y=m["FCF Margin"], name="FCF marjı", mode="lines+markers", line={"color": COLORS["blue"]})
    st.plotly_chart(layout(fig, "Serbest Nakit Akışı Dönüşümü", y_format=".1%"), use_container_width=True, key="hist_cash")
c1, c2 = st.columns(2)
with c1:
    fig = go.Figure([go.Bar(x=f.index.year.astype(str), y=f["Capital Expenditure"] / 1e9, name="Capex", marker_color=COLORS["purple"]),
                     go.Bar(x=f.index.year.astype(str), y=f["D&A"] / 1e9, name="D&A", marker_color=COLORS["teal"])])
    st.plotly_chart(layout(fig, "Capex ve D&A (milyar)"), use_container_width=True, key="hist_capex")
with c2:
    fig = go.Figure(go.Bar(x=m.index.year.astype(str), y=m["Net Debt"] / 1e9, marker_color=[COLORS["red"] if x > 0 else COLORS["green"] for x in m["Net Debt"]]))
    st.plotly_chart(layout(fig, "Net Borç Gelişimi (milyar)"), use_container_width=True, key="hist_debt")
st.caption(f"Kaynak: Yahoo Finance | Alım zamanı: {r['market']['Retrieved At'][:19]} | Birimler aksi belirtilmedikçe raporlanan para birimidir. Eksik değerler doldurulmamıştır.")
footer()
