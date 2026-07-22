"""Institutional DCF and comparable-company valuation Streamlit application."""

import streamlit as st

from src.ui import page_setup, render_sidebar


page_setup("Kurumsal Değerleme Platformu", "📈")

pages = [
    st.Page("pages/1_Executive_Summary.py", title="Yönetici Özeti", icon="📊", default=True),
    st.Page("pages/2_Historical_Performance.py", title="Tarihsel Performans", icon="🕰️"),
    st.Page("pages/3_Forecast_Model.py", title="Tahmin Modeli", icon="📈"),
    st.Page("pages/4_DCF_Valuation.py", title="DCF Değerleme", icon="🧮"),
    st.Page("pages/5_Comparable_Companies.py", title="Benzer Şirketler", icon="🏢"),
    st.Page("pages/6_Sensitivity_and_Scenarios.py", title="Duyarlılık ve Senaryolar", icon="🎛️"),
    st.Page("pages/7_Report_Center.py", title="Rapor Merkezi", icon="📥"),
    st.Page("pages/8_Private_Company_DCF.py", title="Özel Şirket DCF", icon="🔒"),
]

navigation = st.navigation(pages, position="sidebar")
if navigation.title != "Özel Şirket DCF":
    render_sidebar()
navigation.run()
