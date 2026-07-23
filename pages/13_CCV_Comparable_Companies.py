"""Detailed deterministic comparable-company analysis."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.ccv_ui import active_filter_chips, ccv_page_navigation
from src.ui import banner, footer, page_header, section
from src.visualizations import COLORS, football_field, layout


page_header("CCV · Benzer Şirketler", "Puanlama bileşenleri, dahil/hariç şirketler, çarpanlar, aykırı değerler ve ima edilen değerler.")
st.caption("Adım 4/4 · Ayrıntılı analiz")
result = st.session_state.get("ccv_results")
if not result:
    st.info("Önce CCV analizini çalıştırın."); ccv_page_navigation("pages/10_CCV_Setup.py", None); footer(); st.stop()

target = result["target"]
section("Hedef Şirket Profili")
st.dataframe(pd.DataFrame([target]), use_container_width=True, hide_index=True,
             column_config={"Source URL": st.column_config.LinkColumn("Kaynak")})
active_filter_chips(result["project"].get("boundaries", {}))
st.caption("Benzerlik ağırlıkları: " + " · ".join(f"{key} %{value*100:.1f}" for key, value in result["project"]["similarity_weights"].items()))

section("Sıralanmış Peer Seti")
selected = result["selected_peers"]
display_columns = [column for column in ["Company", "Exchange", "Country", "Sector", "Subsector", "Business Description",
                                          "Revenue", "EBITDA", "Revenue Growth", "EBITDA Margin", "Market Cap",
                                          "Enterprise Value", "Similarity Score", "Selection Reason", "Data Source",
                                          "Financial Period", "Retrieved At", "Manual Status"] if column in selected]
st.dataframe(selected[display_columns], use_container_width=True,
             column_config={"Similarity Score": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=1),
                            "Source URL": st.column_config.LinkColumn("Kaynak")})
st.download_button("Peer Tablosunu CSV İndir", selected.to_csv().encode("utf-8-sig"), "ccv_selected_peers.csv", "text/csv")

tabs = st.tabs(["Dahil Edilenler", "Reddedilenler", "İşlem Çarpanları", "Özet İstatistikler", "Aykırı Değer Analizi", "İma Edilen Değer"])
with tabs[0]:
    st.dataframe(selected, use_container_width=True)
with tabs[1]:
    rejected = result["rejected_candidates"]
    if rejected.empty:
        st.success("Reddedilen aday bulunmuyor.")
    else:
        st.dataframe(rejected, use_container_width=True)
        banner("Filtreleri genişletme", "Sistem hedef sayıya ulaşmak için sınırları kendiliğinden gevşetmez. Reddedilme gerekçelerini inceleyip CCV Kurulumu sayfasında sınırları açıkça değiştirin.")
with tabs[2]:
    multiples = result["clean_peers"][["EV/Revenue", "EV/EBITDA", "EV/EBIT", "P/E"]]
    formatted = multiples.copy().astype(object)
    for column in formatted:
        formatted[column] = multiples[column].map(lambda value: "N/M" if pd.isna(value) else f"{value:.1f}x")
    st.dataframe(formatted, use_container_width=True)
    st.caption("EV = Piyasa Değeri + Borç + İmtiyazlı Özsermaye + Kontrol Gücü Olmayan Paylar − Nakit. Negatif veya sıfır paydalı çarpanlar N/M'dir.")
with tabs[3]:
    stats = result["summary_statistics"]
    st.dataframe(stats, use_container_width=True)
    if (stats["Valid Observations"] < 3).any():
        st.warning("En az bir çarpanda üçten az gözlem vardır; bu istatistikler düşük güvenlidir.")
with tabs[4]:
    st.dataframe(result["outlier_summary"], use_container_width=True)
    st.dataframe(result["outlier_audit"], use_container_width=True, hide_index=True)
with tabs[5]:
    implied = result["implied_valuations"]
    if implied.empty:
        st.warning("Hedef şirkette kullanılabilir finansal ölçü olmadığı için parasal değerleme yapılmadı.")
    else:
        st.dataframe(implied, use_container_width=True, hide_index=True)

section("Peer Karşılaştırma Grafikleri")
chart = go.Figure()
for multiple, color in zip(["EV/Revenue", "EV/EBITDA", "EV/EBIT", "P/E"],
                           [COLORS["blue"], COLORS["teal"], COLORS["purple"], COLORS["green"]]):
    chart.add_trace(go.Box(y=result["clean_peers"][multiple], name=multiple, boxpoints="all", marker_color=color))
st.plotly_chart(layout(chart, "Temizlenmiş Çarpan Dağılımları"), use_container_width=True)

implied = result["implied_valuations"]
if not implied.empty:
    football_rows = []
    value_column = "Implied Value Per Share" if implied["Implied Value Per Share"].notna().any() else (
        "Implied Equity Value" if implied["Implied Equity Value"].notna().any() else "Implied Enterprise Value")
    for multiple, group in implied.groupby("Multiple"):
        values = group.set_index("Statistic")[value_column]
        if {"25th Percentile", "Median", "75th Percentile"}.issubset(values.index):
            football_rows.append({"Method": multiple, "Low": values["25th Percentile"],
                                  "Median": values["Median"], "High": values["75th Percentile"]})
    if football_rows:
        st.plotly_chart(football_field(pd.DataFrame(football_rows)), use_container_width=True)

section("Metodoloji ve Kaynaklar")
st.write("Her aday önce kullanıcı sınırlarından geçirilir; ardından sektör, alt sektör, iş modeli, müşteri yapısı, coğrafya, ölçek, büyüme, kârlılık ve hasılat modeli bileşenleriyle puanlanır. Matematiksel sonuçlarda yapay zekâ kullanılmaz.")
source_columns = [column for column in ["Company", "Data Source", "Source URL", "Financial Period", "Financial Date", "Retrieved At"] if column in selected]
st.dataframe(selected[source_columns], use_container_width=True,
             column_config={"Source URL": st.column_config.LinkColumn("Kaynak")})
if not result["provider_failures"].empty:
    st.error("Sağlayıcı hataları")
    st.dataframe(result["provider_failures"], use_container_width=True, hide_index=True)

ccv_page_navigation("pages/12_CCV_Historical_Performance.py", "pages/14_CCV_Report_Center.py")
footer()
