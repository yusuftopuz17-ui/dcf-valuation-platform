"""Session-state helpers for independent valuation workflows."""

from __future__ import annotations

import streamlit as st

from valuation_platform.ccv import ValuationProject


METHODS = ["Comparable Companies", "DCF"]
METHOD_LABELS = {"Comparable Companies": "Comparable Companies", "DCF": "DCF"}


def initialize_project() -> ValuationProject:
    project = ValuationProject.from_dict(st.session_state.get("valuation_project"))
    st.session_state.setdefault("ccv_results", None)
    st.session_state.setdefault("ccv_histories", {})
    st.session_state.setdefault("public_search_results", [])
    st.session_state["valuation_project"] = project.to_dict()
    return project


def get_project() -> ValuationProject:
    return ValuationProject.from_dict(st.session_state.get("valuation_project"))


def save_project(project: ValuationProject) -> None:
    st.session_state["valuation_project"] = project.to_dict()


def select_method(method: str) -> None:
    project = get_project()
    project.selected_method = method
    save_project(project)


def new_project() -> None:
    preserved = {key: value for key, value in st.session_state.items() if key.startswith("_")}
    st.session_state.clear()
    st.session_state.update(preserved)
    initialize_project()


def render_method_tabs() -> None:
    project = get_project()
    if not project.selected_method:
        return
    columns = st.columns([1, 1, .65])
    for column, method in zip(columns[:2], METHODS):
        active = project.selected_method == method
        if column.button(("● " if active else "") + METHOD_LABELS[method], key=f"method_tab_{method}",
                         type="primary" if active else "secondary", use_container_width=True):
            select_method(method)
            st.rerun()
    if columns[2].button("View Methods", use_container_width=True):
        project.selected_method = None
        save_project(project)
        st.rerun()


def method_card(title: str, description: str, use_cases: str, inputs: str, method: str) -> None:
    with st.container(border=True):
        st.markdown(f"### {title}")
        st.write(description)
        st.caption(f"**Best suited for:** {use_cases}")
        st.caption(f"**Key inputs:** {inputs}")
        if st.button("Select Method", key=f"select_{method}", type="primary", use_container_width=True):
            select_method(method)
            st.rerun()
