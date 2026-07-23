"""CCV historical performance without DCF forecasts."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.ccv_state import get_project
from src.ccv_ui import ccv_page_navigation
from src.ui import footer, page_header, section
from src.visualizations import COLORS, layout


project = get_project()
page_header("CCV · Tarihsel Performans", "Raporlanan, TTM ve kullanıcı girdisi verileri; bu sayfa DCF tahmini üretmez.")
st.caption("Adım 3/4 · Finansal performans")
result = st.session_state.get("ccv_results")
if not result:
    st.info("Önce CCV analizini çalıştırın."); ccv_page_navigation("pages/10_CCV_Setup.py", None); footer(); st.stop()

if project.company_type == "Private":
    section("Özel Şirket Tarihsel Veri Girişi")
    uploaded = st.file_uploader("CSV yükle · isteğe bağlı", type=["csv"], help="Year, Revenue, EBITDA, EBIT, Net Income, Cash, Debt")
    default = st.session_state.get("private_ccv_history")
    if default is None:
        default = pd.DataFrame({"Year": [None] * 3, "Revenue": [None] * 3, "EBITDA": [None] * 3,
                                "EBIT": [None] * 3, "Net Income": [None] * 3, "Cash": [None] * 3, "Debt": [None] * 3,
                                "Data Status": ["User-entered"] * 3})
    if uploaded is not None:
        try:
            default = pd.read_csv(uploaded)
        except Exception as exc:
            st.error(f"Dosya okunamadı: {exc}")
    history = st.data_editor(default, num_rows="dynamic", use_container_width=True, key="private_ccv_history_editor")
    if st.button("Tarihsel Veriyi Kaydet"):
        st.session_state.private_ccv_history = history
        st.success("Tarihsel veriler aktif proje oturumuna kaydedildi.")
else:
    section("Halka Açık Şirket Finansalları")
    history = result.get("historical", pd.DataFrame()).copy()
    if history.empty:
        st.warning("Sağlayıcıdan tarihsel tablo alınamadı.")
    else:
        history["Revenue Growth"] = history["Revenue"].pct_change()
        history["EBITDA Margin"] = history["EBITDA"] / history["Revenue"]
        history["EBIT Margin"] = history["EBIT"] / history["Revenue"]
        history["Net Income Margin"] = history["Net Income"] / history["Revenue"]
        history["Enterprise Value"] = np.nan
        display = history[["Revenue", "Revenue Growth", "EBITDA", "EBITDA Margin", "EBIT", "EBIT Margin",
                           "Net Income", "Net Income Margin", "Cash", "Debt", "Enterprise Value"]]
        st.caption(f"Kaynak: {result['target'].get('Data Source')} · Finansal dönem: {result['target'].get('Financial Period')} · Tarih: {result['target'].get('Financial Date')}")
        st.dataframe(display, use_container_width=True)
        figure = go.Figure()
        for metric, color in [("Revenue", COLORS["blue"]), ("EBITDA", COLORS["teal"]), ("EBIT", COLORS["purple"]), ("Net Income", COLORS["green"])]:
            figure.add_trace(go.Bar(x=display.index, y=display[metric], name=metric, marker_color=color))
        st.plotly_chart(layout(figure, "Tarihsel Hasılat ve Kârlılık"), use_container_width=True)
        margins = go.Figure()
        for metric, color in [("EBITDA Margin", COLORS["teal"]), ("EBIT Margin", COLORS["purple"]), ("Net Income Margin", COLORS["green"])]:
            margins.add_trace(go.Scatter(x=display.index, y=display[metric], name=metric, mode="lines+markers", line_color=color))
        st.plotly_chart(layout(margins, "Tarihsel Marjlar", y_format=".1%"), use_container_width=True)

ccv_page_navigation("pages/11_CCV_Executive_Summary.py", "pages/13_CCV_Comparable_Companies.py")
footer()
