"""Multi-method institutional valuation platform."""

import streamlit as st

from src.ccv_state import initialize_project, render_method_tabs
from src.ui import page_setup


page_setup("Şirket Değerleme Platformu", "📈")
project = initialize_project()

if project.selected_method is None:
    pages = [st.Page("pages/0_Method_Selection.py", title="Değerleme Yöntemi", icon="🧭", default=True)]
elif project.selected_method == "Comparable Companies":
    render_method_tabs()
    pages = [st.Page("pages/40_Comparable_Analysis.py", title="Benzer Şirket Analizi", icon="🏢", default=True)]
elif project.selected_method == "DCF":
    render_method_tabs()
    pages = [st.Page("pages/50_DCF_Analysis.py", title="DCF Analizi", icon="📈", default=True)]

navigation = st.navigation(pages, position="sidebar")
navigation.run()
