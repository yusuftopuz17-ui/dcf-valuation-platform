"""Reusable CCV setup and navigation controls."""

from __future__ import annotations

from typing import Any

import numpy as np
import streamlit as st

from valuation_platform.ccv import BOUNDARY_FIELDS, DEFAULT_WEIGHTS, normalize_value


def select_other(label: str, options: list[str], key: str) -> str:
    choices = [item for item in options if item != "Other"] + ["Other"]
    selected = st.selectbox(label, choices, key=key)
    if selected == "Other":
        return st.text_input(f"{label} · Diğer", key=f"{key}_other").strip()
    return selected


def multi_other(label: str, options: list[str], key: str) -> list[str]:
    choices = [item for item in options if item != "Other"] + ["Other"]
    selected = st.multiselect(label, choices, key=key)
    if "Other" in selected:
        custom = st.text_input(f"{label} · Diğer", key=f"{key}_other").strip()
        return [item for item in selected if item != "Other"] + ([custom] if custom else [])
    return selected


def render_weights(existing: dict[str, float]) -> dict[str, float]:
    st.caption("Ağırlıkların toplamı %100 olmalıdır. Puanlar tamamen deterministik hesaplanır.")
    values: dict[str, float] = {}
    columns = st.columns(3)
    for index, (name, default) in enumerate(DEFAULT_WEIGHTS.items()):
        values[name] = columns[index % 3].number_input(
            f"{name} %", min_value=0.0, max_value=100.0,
            value=float(existing.get(name, default) * 100), step=2.5, key=f"weight_{name}",
        ) / 100
    total = sum(values.values())
    st.metric("Ağırlık toplamı", f"%{total * 100:.1f}", border=True)
    if not np.isclose(total, 1.0):
        st.error("Benzerlik ağırlıklarının toplamı %100 olmalıdır.")
    return values


def render_boundaries(existing: dict[str, Any]) -> dict[str, Any]:
    """Render normalized min/max inputs while preserving blank boundaries."""
    values: dict[str, Any] = {}
    money_fields = {"Revenue", "EBITDA", "Market Cap", "Enterprise Value"}
    percent_fields = {"Revenue Growth", "EBITDA Margin"}
    for field in BOUNDARY_FIELDS:
        st.markdown(f"**{field}**")
        c1, c2, c3, c4 = st.columns([1, 1, .8, .8])
        current_min, current_max = existing.get(f"min_{field}"), existing.get(f"max_{field}")
        stored_unit = existing.get(f"unit_{field}", "millions" if field in money_fields else "actual")
        display_factor = {"actual": 1, "thousands": 1e3, "millions": 1e6, "billions": 1e9}[stored_unit]
        min_text = c1.text_input("Minimum", "" if current_min is None else str(current_min / display_factor),
                                 key=f"boundary_min_{field}", label_visibility="collapsed", placeholder="Minimum")
        max_text = c2.text_input("Maksimum", "" if current_max is None else str(current_max / display_factor),
                                 key=f"boundary_max_{field}", label_visibility="collapsed", placeholder="Maksimum")
        unit = "actual"
        if field in money_fields:
            currencies = ["USD", "EUR", "TRY", "GBP"]
            selected_currency = c3.selectbox("Para birimi", currencies,
                                             index=currencies.index(existing.get(f"currency_{field}", "USD")),
                                             key=f"boundary_currency_{field}",
                                             label_visibility="collapsed")
            units = ["actual", "thousands", "millions", "billions"]
            unit = c4.selectbox("Birim", units, index=units.index(stored_unit),
                                key=f"boundary_unit_{field}", label_visibility="collapsed")
            values[f"currency_{field}"] = selected_currency
            values[f"unit_{field}"] = unit
        elif field in percent_fields:
            c3.caption("Yüzde olarak girin")
        try:
            minimum = None if not min_text.strip() else float(min_text.replace(",", ".")) / (100 if field in percent_fields else 1)
            maximum = None if not max_text.strip() else float(max_text.replace(",", ".")) / (100 if field in percent_fields else 1)
            values[f"min_{field}"] = None if minimum is None else normalize_value(minimum, unit)
            values[f"max_{field}"] = None if maximum is None else normalize_value(maximum, unit)
        except ValueError:
            st.error(f"{field} sınırları sayısal olmalıdır.")
            values[f"min_{field}"] = values[f"max_{field}"] = None
    return values


def active_filter_chips(boundaries: dict[str, Any]) -> None:
    labels = []
    for field in BOUNDARY_FIELDS:
        minimum, maximum = boundaries.get(f"min_{field}"), boundaries.get(f"max_{field}")
        if minimum is not None:
            labels.append(f"{field} ≥ {minimum:,.2f}")
        if maximum is not None:
            labels.append(f"{field} ≤ {maximum:,.2f}")
    if labels:
        st.markdown(" ".join(f"<span class='iv-chip'>{label}</span>" for label in labels), unsafe_allow_html=True)
    else:
        st.caption("Aktif sayısal sınır bulunmuyor.")


def ccv_page_navigation(previous_page: str | None, next_page: str | None) -> None:
    left, _, right = st.columns([1, 2, 1])
    if previous_page:
        left.page_link(previous_page, label="← Önceki", use_container_width=True)
    if next_page:
        right.page_link(next_page, label="Sonraki →", use_container_width=True)
