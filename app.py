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
    pages = [
        st.Page("pages/10_CCV_Setup.py", title="CCV Kurulumu", icon="⚙️", default=True),
        st.Page("pages/11_CCV_Executive_Summary.py", title="Yönetici Özeti", icon="📊"),
        st.Page("pages/12_CCV_Historical_Performance.py", title="Tarihsel Performans", icon="🕰️"),
        st.Page("pages/13_CCV_Comparable_Companies.py", title="Benzer Şirketler", icon="🏢"),
        st.Page("pages/14_CCV_Report_Center.py", title="Rapor Merkezi", icon="📥"),
    ]
elif project.selected_method == "DCF":
    render_method_tabs()
    pages = [st.Page("pages/20_DCF_Coming_Soon.py", title="DCF", icon="📈", default=True)]
else:
    render_method_tabs()
    pages = [st.Page("pages/30_Precedent_Coming_Soon.py", title="Emsal İşlemler", icon="🤝", default=True)]

navigation = st.navigation(pages, position="sidebar")
navigation.run()
