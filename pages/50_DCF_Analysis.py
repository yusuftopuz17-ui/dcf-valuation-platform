"""Interactive forward and reverse discounted-cash-flow analysis."""

from __future__ import annotations

import json
import numpy as np
import pandas as pd
import streamlit as st

from src.ccv_provider import company_record
from src.ui import banner, footer, page_header, section
from valuation_platform.market_tools import dcf_sensitivity, forward_dcf, reverse_dcf, scenario_table
from valuation_platform.model import historical_metrics


def _money(value: float, currency: str) -> str:
    if not np.isfinite(value):
        return "N/M"
    for divisor, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(value) >= divisor:
            return f"{currency} {value/divisor:,.1f}{suffix}"
    return f"{currency} {value:,.2f}"


defaults = {
    "dcf_quick_ticker": "MSFT", "dcf_quick_package": None, "dcf_base_fcf": 100_000_000_000.0,
    "dcf_shares": 7_500_000_000.0, "dcf_net_debt": 0.0, "dcf_price": 0.0,
    "dcf_growth": 10.0, "dcf_terminal": 2.5, "dcf_wacc": 9.0,
    "dcf_years": 5, "dcf_midyear": True, "dcf_fade": False,
}
for key, value in defaults.items():
    st.session_state.setdefault(key, value)
if not st.session_state.get("dcf_query_loaded"):
    query = st.query_params
    conversions = {
        "g": ("dcf_growth", float), "tg": ("dcf_terminal", float), "w": ("dcf_wacc", float),
        "y": ("dcf_years", int), "fcf": ("dcf_base_fcf", float), "sh": ("dcf_shares", float),
        "nd": ("dcf_net_debt", float), "px": ("dcf_price", float),
        "mid": ("dcf_midyear", lambda value: value == "1"),
        "fade": ("dcf_fade", lambda value: value == "1"),
    }
    for parameter, (state_key, converter) in conversions.items():
        if parameter in query:
            try:
                st.session_state[state_key] = converter(query[parameter])
            except (TypeError, ValueError):
                pass
    st.session_state.dcf_query_loaded = True

page_header("İleri ve Ters DCF Analizi", "Serbest nakit akışından makul değeri veya piyasa fiyatının ima ettiği büyümeyi hesaplayın.")
top_left, top_right = st.columns([3, 1])
top_left.text_input("Borsa sembolü", key="dcf_quick_ticker", placeholder="Örn. MSFT")
load = top_right.button("Verileri Yükle", type="primary", use_container_width=True)
presets = st.columns([.6, .6, .6, 4])
for column, ticker in zip(presets[:3], ["AAPL", "GOOGL", "MSFT"]):
    if column.button(ticker, key=f"dcf_preset_{ticker}", use_container_width=True):
        st.session_state.dcf_quick_ticker = ticker
        st.rerun()

if load:
    try:
        with st.spinner("Finansal veriler Yahoo Finance üzerinden alınıyor..."):
            package = company_record(st.session_state.dcf_quick_ticker.strip().upper())
            metrics = historical_metrics(package["historical"])
            fcf_series = metrics["Free Cash Flow"].replace([np.inf, -np.inf], np.nan).dropna()
            if fcf_series.empty or fcf_series.iloc[-1] <= 0:
                raise ValueError("Pozitif serbest nakit akışı hesaplanamadı; manuel giriş kullanın.")
            record = package["record"]
            st.session_state.dcf_quick_package = package
            st.session_state.dcf_base_fcf = float(fcf_series.iloc[-1])
            st.session_state.dcf_shares = float(record["Diluted Shares"])
            st.session_state.dcf_net_debt = float(record["Net Debt"])
            st.session_state.dcf_price = float(record["Current Price"])
    except Exception as exc:
        st.error(f"Veriler yüklenemedi: {exc}")

package = st.session_state.dcf_quick_package
if package:
    record = package["record"]
    banner(f"{record['Company']} ({record['Ticker']})",
           f"Kaynak: Yahoo Finance · Finansal dönem: {record['Financial Date']} · "
           f"Fiyat: {record['Currency']} {record['Current Price']:,.2f} ({record['Price Date']})")
else:
    st.info("Sembol verisini otomatik yükleyebilir veya aşağıdaki alanlara kendi varsayımlarınızı girebilirsiniz.")

with st.expander("Temel Veriler ve Varsayımlar", expanded=True):
    c1, c2, c3, c4 = st.columns(4)
    c1.number_input("Serbest Nakit Akışı", min_value=1.0, step=1_000_000.0, format="%.2f", key="dcf_base_fcf",
                    help="Son kullanılabilir dönemin şirkete serbest nakit akışı (UFCF) başlangıç değeri.")
    c2.number_input("Seyreltilmiş Hisse Sayısı", min_value=1.0, step=1_000_000.0, format="%.2f", key="dcf_shares")
    c3.number_input("Net Borç", step=1_000_000.0, format="%.2f", key="dcf_net_debt",
                    help="Toplam borç eksi nakit. Net nakit varsa negatif olabilir.")
    c4.number_input("Güncel Hisse Fiyatı", min_value=0.0, step=1.0, format="%.2f", key="dcf_price")
    a, b, c, d = st.columns(4)
    a.number_input("FCF Büyümesi %", min_value=-50.0, max_value=100.0, step=.5, key="dcf_growth")
    b.number_input("Terminal Büyüme %", min_value=-2.0, max_value=6.0, step=.1, key="dcf_terminal")
    c.number_input("WACC %", min_value=1.0, max_value=30.0, step=.1, key="dcf_wacc")
    d.radio("Tahmin Dönemi", [5, 10], horizontal=True, key="dcf_years")
    t1, t2 = st.columns(2)
    t1.toggle("Büyümeyi terminal orana yaklaştır", key="dcf_fade",
              help="Büyüme oranı tahmin dönemi boyunca doğrusal biçimde terminal büyümeye yaklaşır.")
    t2.toggle("Yıl ortası iskonto", key="dcf_midyear",
              help="Nakit akışlarının yıl boyunca üretildiğini kabul eder.")

growth, terminal, rate = (st.session_state.dcf_growth / 100,
                          st.session_state.dcf_terminal / 100,
                          st.session_state.dcf_wacc / 100)
currency = package["record"]["Currency"] if package else "USD"
try:
    result = forward_dcf(st.session_state.dcf_base_fcf, growth, terminal, rate,
                         st.session_state.dcf_years, st.session_state.dcf_shares,
                         st.session_state.dcf_net_debt, st.session_state.dcf_price or None,
                         st.session_state.dcf_midyear, st.session_state.dcf_fade)
except Exception as exc:
    st.error(f"DCF hesaplanamadı: {exc}")
    footer()
    st.stop()

forward_tab, reverse_tab = st.tabs(["İleri DCF · Makul Değer", "Ters DCF · İma Edilen Büyüme"])
with forward_tab:
    section("Değerleme Sonucu")
    cols = st.columns(4)
    cols[0].metric("İşletme Değeri", _money(result["Enterprise Value"], currency))
    cols[1].metric("Özsermaye Değeri", _money(result["Equity Value"], currency),
                   f"Net borç köprüsü: {_money(result['Net Debt'], currency)}")
    cols[2].metric("Hisse Başına Değer", f"{currency} {result['Per Share']:,.2f}")
    delta = f"{result['Upside']:+.1%}" if np.isfinite(result["Upside"]) else None
    cols[3].metric("Güncel Fiyat", f"{currency} {st.session_state.dcf_price:,.2f}", delta)
    if result["Terminal Share"] > .75:
        st.warning(f"Terminal değer, işletme değerinin %{result['Terminal Share']*100:.1f}'ini oluşturuyor. "
                   "Sonuç WACC ve terminal büyümeye yüksek derecede duyarlıdır.")
    else:
        st.success(f"Terminal değerin işletme değeri içindeki payı: %{result['Terminal Share']*100:.1f}.")
    if package:
        analyst_target = float(pd.to_numeric(package["record"].get("Analyst Target"), errors="coerce"))
        analyst_count = float(pd.to_numeric(package["record"].get("Analyst Count"), errors="coerce"))
        if np.isfinite(analyst_target):
            section("Piyasa ve Analist Karşılaştırması")
            comparison = pd.DataFrame({
                "Fiyat": [st.session_state.dcf_price, analyst_target, result["Per Share"]],
            }, index=["Güncel Fiyat", "Analist Ortalama Hedefi", "DCF Değeri"])
            st.bar_chart(comparison, horizontal=True)
            st.caption(f"Analist ortalama hedefi: {currency} {analyst_target:,.2f}"
                       + (f" · Görüş sayısı: {int(analyst_count)}" if np.isfinite(analyst_count) else "")
                       + " · Sağlayıcıdaki son kullanılabilir konsensüs verisi")

    section("Ayı · Baz · Boğa Senaryoları")
    scenarios = scenario_table(st.session_state.dcf_base_fcf, growth, terminal, rate,
                               st.session_state.dcf_years, st.session_state.dcf_shares,
                               st.session_state.dcf_net_debt, st.session_state.dcf_price or result["Per Share"],
                               st.session_state.dcf_midyear, st.session_state.dcf_fade)
    st.dataframe(scenarios.style.format({
        "FCF Büyümesi": "{:.1%}", "WACC": "{:.1%}",
        "Hisse Başı Değer": f"{currency} {{:,.2f}}", "Fiyat Farkı": "{:+.1%}",
    }), use_container_width=True)

with reverse_tab:
    section("Piyasanın Fiyatladığı Büyüme")
    if st.session_state.dcf_price <= 0:
        st.info("Ters DCF için güncel hisse fiyatı girin.")
    else:
        implied_growth = reverse_dcf(st.session_state.dcf_price, st.session_state.dcf_base_fcf,
                                     terminal, rate, st.session_state.dcf_years,
                                     st.session_state.dcf_shares, st.session_state.dcf_net_debt,
                                     st.session_state.dcf_midyear, st.session_state.dcf_fade)
        st.metric("İma Edilen Yıllık FCF Büyümesi", f"%{implied_growth*100:,.1f}",
                  f"Model varsayımınız: %{growth*100:,.1f}")
        difference = implied_growth - growth
        banner("Piyasa Beklentisi", f"Mevcut fiyatın gerçekleşmesi için model, seçilen dönem boyunca yaklaşık "
               f"%{implied_growth*100:.1f} yıllık FCF büyümesi gerektiriyor. Bu oran sizin varsayımınızdan "
               f"{abs(difference)*100:.1f} puan {'yüksek' if difference > 0 else 'düşük'}.")

section("WACC × Terminal Büyüme Duyarlılığı")
sensitivity = dcf_sensitivity(st.session_state.dcf_base_fcf, growth, terminal, rate,
                              st.session_state.dcf_years, st.session_state.dcf_shares,
                              st.session_state.dcf_net_debt, st.session_state.dcf_midyear,
                              st.session_state.dcf_fade)
display_sensitivity = sensitivity.copy()
display_sensitivity.index = [f"%{item*100:.2f}" for item in display_sensitivity.index]
display_sensitivity.columns = [f"%{item*100:.2f}" for item in display_sensitivity.columns]
st.dataframe(display_sensitivity.style.format(f"{currency} {{:,.2f}}").background_gradient(cmap="RdYlGn"),
             use_container_width=True)

section("Nakit Akışı Bugünkü Değer Köprüsü")
schedule = result["Schedule"].copy()
st.dataframe(schedule.style.format({
    "Büyüme": "{:.1%}", "Serbest Nakit Akışı": f"{currency} {{:,.0f}}",
    "İskonto Faktörü": "{:.4f}", "Bugünkü Değer": f"{currency} {{:,.0f}}",
}), use_container_width=True)

export = {
    "ticker": package["record"]["Ticker"] if package else None,
    "assumptions": {"base_fcf": st.session_state.dcf_base_fcf, "growth": growth,
                    "terminal_growth": terminal, "wacc": rate, "years": st.session_state.dcf_years,
                    "shares": st.session_state.dcf_shares, "net_debt": st.session_state.dcf_net_debt,
                    "mid_year": st.session_state.dcf_midyear, "fade_growth": st.session_state.dcf_fade},
    "results": {key: value for key, value in result.items() if key != "Schedule"},
}
st.download_button("Analizi JSON Olarak İndir", json.dumps(export, ensure_ascii=False, indent=2, default=float),
                   "dcf_analysis.json", "application/json")
if st.button("Varsayımları Paylaşılabilir Bağlantıya Yaz"):
    st.query_params.update({
        "g": str(st.session_state.dcf_growth), "tg": str(st.session_state.dcf_terminal),
        "w": str(st.session_state.dcf_wacc), "y": str(st.session_state.dcf_years),
        "fcf": str(st.session_state.dcf_base_fcf), "sh": str(st.session_state.dcf_shares),
        "nd": str(st.session_state.dcf_net_debt), "px": str(st.session_state.dcf_price),
        "mid": "1" if st.session_state.dcf_midyear else "0",
        "fade": "1" if st.session_state.dcf_fade else "0",
    })
    st.success("Varsayımlar adres çubuğundaki bağlantıya eklendi. Tarayıcı bağlantısını kopyalayarak paylaşabilirsiniz.")
with st.expander("Metodoloji ve kullanım notları"):
    st.markdown("""
- Açık tahmin dönemi FCF'leri seçilen WACC ile bugünkü değere indirgenir.
- Terminal değer Gordon Büyüme yöntemiyle hesaplanır: `FCFₙ₊₁ / (WACC − g)`.
- İşletme değerinden net borç çıkarılarak özsermaye değerine, seyreltilmiş hisse sayısına bölünerek hisse başına değere ulaşılır.
- Ters DCF, güncel fiyatı sağlayan büyüme oranını ikili arama ile çözer; tahmin değil, piyasanın matematiksel beklentisidir.
- Duyarlılık tablosu her hücrede modeli yeniden hesaplar. WACC her zaman terminal büyümeden yüksek olmalıdır.
""")
footer()
