"""Initial valuation-method selection screen."""

import streamlit as st

from src.ccv_state import method_card, new_project
from src.ui import footer, page_header


page_header("Select a Valuation Method", "Start with a comparable company analysis or a forward/reverse DCF.")
columns = st.columns(2)
with columns[0]:
    method_card("Comparable Company Analysis", "Estimates a valuation range from the trading multiples of public peers.",
                "Publicly traded companies", "Target ticker; peers can be discovered automatically or entered manually",
                "Comparable Companies")
with columns[1]:
    method_card("Discounted Cash Flow (DCF)", "Discounts forecast free cash flows to their present value.",
                "Companies with reasonably predictable cash flows", "Financial forecasts, WACC, and terminal value assumptions", "DCF")
st.divider()
if st.button("Start a New Blank Valuation", use_container_width=False):
    new_project()
    st.rerun()
footer()
