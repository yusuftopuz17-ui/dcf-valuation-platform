"""Consolidated CCV-only report center."""

import pandas as pd
import streamlit as st

from src.ccv_reporting import build_ccv_csv, build_ccv_excel, build_ccv_pdf
from src.ccv_ui import ccv_page_navigation
from src.ui import footer, page_header, section


page_header("CCV · Rapor Merkezi", "Yalnızca benzer şirket metodolojisi ve sonuçlarını içeren konsolide rapor.")
result = st.session_state.get("ccv_results")
if not result:
    st.info("Önce CCV analizini çalıştırın."); ccv_page_navigation("pages/10_CCV_Setup.py", None); footer(); st.stop()

section("Rapor Önizleme")
target = result["target"]
st.markdown(f"### {target.get('Company')} · Comparable Company Valuation")
st.write(f"**Değerleme tarihi:** {result['project'].get('manual_overrides', {}).get('valuation_date')}  \n"
         f"**Oluşturulma:** {result['generated_at']}  \n"
         f"**Veri dönemi:** {result['project'].get('manual_overrides', {}).get('period')}  \n"
         f"**Güven:** {result['confidence']['Level']} — {result['confidence']['Explanation']}")
preview_tabs = st.tabs(["Yönetici Özeti", "Peer Tablosu", "Çarpanlar", "Değerleme", "Kaynaklar ve Sınırlamalar"])
with preview_tabs[0]:
    st.dataframe(pd.DataFrame([target]), use_container_width=True, hide_index=True)
with preview_tabs[1]:
    st.dataframe(result["selected_peers"], use_container_width=True)
with preview_tabs[2]:
    st.dataframe(result["summary_statistics"], use_container_width=True)
with preview_tabs[3]:
    st.dataframe(result["implied_valuations"], use_container_width=True, hide_index=True)
with preview_tabs[4]:
    source_columns = [column for column in ["Company", "Data Source", "Source URL", "Financial Period", "Retrieved At"] if column in result["selected_peers"]]
    st.dataframe(result["selected_peers"][source_columns], use_container_width=True)
    st.warning("Eksik değerler uydurulmamıştır. Muhasebe politikaları, para birimi, dönem ve şirket seçimi karşılaştırılabilirliği etkileyebilir. Çıktı yatırım tavsiyesi veya fairness opinion değildir.")

section("Dışa Aktarım")
try:
    excel_data, csv_data, pdf_data = build_ccv_excel(result), build_ccv_csv(result), build_ccv_pdf(result)
    columns = st.columns(3)
    columns[0].download_button("CCV Excel Raporu", excel_data, "ccv_valuation_report.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    columns[1].download_button("CCV CSV Paketi", csv_data, "ccv_valuation_tables.zip", "application/zip", use_container_width=True)
    columns[2].download_button("CCV PDF Raporu", pdf_data, "ccv_valuation_report.pdf", "application/pdf", use_container_width=True)
except Exception as exc:
    st.error(f"Rapor üretilemedi: {exc}")

ccv_page_navigation("pages/13_CCV_Comparable_Companies.py", None)
footer()
