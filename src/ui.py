"""Reusable Streamlit components, state, controls, and error boundaries."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import streamlit as st

from valuation_platform import ComparableConfig, ForecastAssumptions, TerminalAssumptions, ValuationConfig, WACCAssumptions, run_valuation
from .data_loader import cached_company, clear_market_cache
from .formatting import money, percent


TOOLTIPS = {
    "WACC": "Şirketin borç ve özsermaye sağlayıcılarının talep ettiği ağırlıklı getiri oranı; DCF iskonto oranıdır.",
    "Beta": "Hissenin piyasa hareketlerine duyarlılığını gösterir. 1,0 piyasa ile aynı sistematik riski ifade eder.",
    "Terminal Growth": "Açık tahmin döneminden sonra nakit akışının uzun vadeli sabit büyüme varsayımıdır.",
    "Exit Multiple": "Son tahmin yılı EBITDA'sına uygulanan EV/EBITDA çarpanıdır.",
    "Mid-year": "Nakit akışlarının yıl boyunca üretildiğini varsayarak yarım dönem daha az iskonto uygular.",
    "UFCF": "Faiz ve finansman kararlarından önce işletmenin ürettiği serbest nakit akışıdır.",
}


DEFAULTS = {"target": "MSFT", "peers": "AAPL, GOOGL, ORCL, CRM, ADBE", "forecast_years": 5,
            "tax": 21.0, "da": 4.0, "capex": 5.0, "nwc": 3.0, "rf": 4.0, "erp": 5.5,
            "beta": 0.0, "cod": 4.5, "crp": 0.0, "debt_weight": 0.0, "tg": 2.5,
            "exit_multiple": 18.0, "mid_year": True, "outlier": "iqr", "threshold": 1.5,
            "multiples": ["EV/Revenue", "EV/EBITDA", "EV/EBIT", "P/E"], "manual_exclusions": "",
            "use_ttm": True, "base_currency": "USD", "valuation_date": date.today()}
DEFAULT_GROWTH = [12.0, 10.0, 8.0, 6.0, 5.0, 4.0, 4.0, 3.5, 3.0, 3.0]
DEFAULT_MARGIN = [47.0, 47.5, 48.0, 48.5, 49.0, 49.0, 49.0, 49.0, 49.0, 49.0]


def initialize_state() -> None:
    for key, value in DEFAULTS.items():
        st.session_state.setdefault(key, value)
    for index in range(10):
        st.session_state.setdefault(f"growth_{index}", DEFAULT_GROWTH[index])
        st.session_state.setdefault(f"margin_{index}", DEFAULT_MARGIN[index])
    st.session_state.setdefault("results", None)
    st.session_state.setdefault("saved_scenarios", {})


def reset_state() -> None:
    keys = list(DEFAULTS) + [f"growth_{i}" for i in range(10)] + [f"margin_{i}" for i in range(10)]
    for key in keys:
        st.session_state.pop(key, None)
    st.session_state["results"] = None
    initialize_state()


def page_setup(title: str, icon: str = "📊") -> None:
    st.set_page_config(page_title=f"{title} | Değerleme Platformu", page_icon=icon, layout="wide", initial_sidebar_state="expanded")
    css = (Path(__file__).resolve().parents[1] / "assets" / "styles.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    initialize_state()


def page_header(title: str, subtitle: str) -> None:
    st.markdown(f"<span class='iv-badge'>INSTITUTIONAL VALUATION</span><h1>{title}</h1><p style='color:#A7B0BC;margin-top:-10px'>{subtitle}</p>", unsafe_allow_html=True)


def section(title: str) -> None:
    st.markdown(f"<div class='iv-section'>{title}</div>", unsafe_allow_html=True)


def kpi(label: str, value: str, sub: str = "", tone: str = "neutral") -> None:
    tone_class = {"positive": "iv-up", "negative": "iv-down", "neutral": "iv-neutral", "info": ""}.get(tone, "")
    st.markdown(f"<div class='iv-card'><div class='iv-label'>{label}</div><div class='iv-value {tone_class}'>{value}</div><div class='iv-sub'>{sub}</div></div>", unsafe_allow_html=True)


def banner(title: str, text: str) -> None:
    st.markdown(f"<div class='iv-banner'><strong>{title}</strong><br>{text}</div>", unsafe_allow_html=True)


def comments(items: list[str]) -> None:
    for item in items:
        st.markdown(f"<div class='iv-comment'>{item}</div>", unsafe_allow_html=True)


def footer() -> None:
    st.markdown("<div class='iv-footer'>Sonuçlar tarihsel veriler, piyasa bilgileri, seçilen benzer şirketler ve kullanıcı varsayımlarından türetilen model bazlı tahminlerdir. Tahmin, garanti, fairness opinion veya yatırım tavsiyesi değildir.</div>", unsafe_allow_html=True)


def render_sidebar() -> None:
    initialize_state()
    st.sidebar.markdown("## Değerleme Kurulumu")
    st.sidebar.caption("Veri indirme yalnızca **Değerlemeyi Çalıştır** düğmesiyle başlar.")
    with st.sidebar.form("valuation_setup"):
        with st.expander("Şirket Seçimi", expanded=True):
            st.text_input("Hedef sembol", key="target", help="Örn. MSFT, AAPL, THYAO.IS")
            st.text_area("Benzer şirketler", key="peers", help="Virgülle ayrılmış borsa sembolleri")
            st.date_input("Değerleme tarihi", key="valuation_date")
            st.selectbox("Temel para birimi", ["USD", "EUR", "TRY", "GBP"], key="base_currency")
        with st.expander("Tahmin Varsayımları", expanded=True):
            st.slider("Tahmin dönemi", 3, 10, key="forecast_years")
            years = int(st.session_state.forecast_years)
            for i in range(years):
                c1, c2 = st.columns(2)
                c1.number_input(f"Y{i+1} büyüme %", -50.0, 100.0, step=.5, key=f"growth_{i}")
                c2.number_input(f"Y{i+1} EBITDA %", -50.0, 100.0, step=.5, key=f"margin_{i}")
            st.number_input("Vergi oranı %", 0.0, 60.0, step=.5, key="tax")
            st.number_input("D&A / Hasılat %", 0.0, 40.0, step=.5, key="da", help=TOOLTIPS["UFCF"])
            st.number_input("Capex / Hasılat %", 0.0, 50.0, step=.5, key="capex")
            st.number_input("NWC / Hasılat %", 0.0, 50.0, step=.5, key="nwc")
        with st.expander("WACC Varsayımları"):
            st.number_input("Risksiz faiz %", -5.0, 30.0, step=.1, key="rf", help=TOOLTIPS["WACC"])
            st.number_input("Hisse risk primi %", 0.0, 30.0, step=.1, key="erp")
            st.number_input("Beta (0 = piyasa verisi)", 0.0, 5.0, step=.05, key="beta", help=TOOLTIPS["Beta"])
            st.number_input("Vergi öncesi borç maliyeti %", 0.0, 30.0, step=.1, key="cod")
            st.number_input("Ülke risk primi %", 0.0, 30.0, step=.1, key="crp")
            st.number_input("Hedef borç ağırlığı % (0 = mevcut)", 0.0, 95.0, step=1.0, key="debt_weight")
        with st.expander("Terminal Değer"):
            st.number_input("Terminal büyüme %", -2.0, 6.0, step=.1, key="tg", help=TOOLTIPS["Terminal Growth"])
            st.number_input("Çıkış EV/EBITDA", 1.0, 50.0, step=.5, key="exit_multiple", help=TOOLTIPS["Exit Multiple"])
            st.toggle("Yıl ortası iskonto", key="mid_year", help=TOOLTIPS["Mid-year"])
        with st.expander("Benzer Şirketler"):
            st.multiselect("Çarpanlar", ["EV/Revenue", "EV/EBITDA", "EV/EBIT", "P/E", "P/B", "Price/Sales"], key="multiples")
            st.selectbox("Aykırı değer yöntemi", ["iqr", "zscore", "mad", "none"], key="outlier")
            st.number_input("Aykırı değer eşiği", .5, 5.0, step=.1, key="threshold")
            st.text_input("Manuel hariç tutmalar", key="manual_exclusions", help="Virgülle ayrılmış semboller")
            st.toggle("TTM kullan", key="use_ttm", help="Sağlayıcı TTM verisi eksikse son mali yıl kullanılır ve tabloda açıklanır.")
        submitted = st.form_submit_button("Değerlemeyi Çalıştır", use_container_width=True)
    c1, c2 = st.sidebar.columns(2)
    if c1.button("Sıfırla", use_container_width=True):
        reset_state(); clear_market_cache(); st.rerun()
    if c2.button("Senaryoyu Kaydet", use_container_width=True):
        name = f"Senaryo {len(st.session_state.saved_scenarios)+1}"
        st.session_state.saved_scenarios[name] = {key: st.session_state.get(key) for key in DEFAULTS if key != "valuation_date"}
        st.sidebar.success(f"{name} kaydedildi")
    if st.session_state.saved_scenarios:
        payload = json.dumps(st.session_state.saved_scenarios, indent=2, ensure_ascii=False)
        st.sidebar.download_button("Senaryoları İndir", payload, "valuation_scenarios.json", "application/json", use_container_width=True)
    if submitted:
        execute_valuation()


def execute_valuation() -> None:
    """Validate, run, and store results without exposing raw stack traces."""
    try:
        years = int(st.session_state.forecast_years)
        peers = [x.strip().upper() for x in st.session_state.peers.split(",") if x.strip()]
        exclusions = [x.strip().upper() for x in st.session_state.manual_exclusions.split(",") if x.strip()]
        config = ValuationConfig(target_ticker=st.session_state.target, peer_tickers=peers, forecast_years=years,
                                 historical_years=5, valuation_date=st.session_state.valuation_date.isoformat(),
                                 base_currency=st.session_state.base_currency, mid_year_discounting=st.session_state.mid_year)
        forecast_inputs = ForecastAssumptions([st.session_state[f"growth_{i}"] / 100 for i in range(years)],
                                              [st.session_state[f"margin_{i}"] / 100 for i in range(years)],
                                              st.session_state.tax / 100, st.session_state.da / 100,
                                              st.session_state.capex / 100, st.session_state.nwc / 100)
        wacc_inputs = WACCAssumptions(st.session_state.rf / 100, st.session_state.erp / 100,
                                     None if st.session_state.beta == 0 else st.session_state.beta,
                                     st.session_state.cod / 100, st.session_state.crp / 100,
                                     None if st.session_state.debt_weight == 0 else st.session_state.debt_weight / 100)
        terminal = TerminalAssumptions(st.session_state.tg / 100, st.session_state.exit_multiple)
        comps = ComparableConfig(st.session_state.multiples, st.session_state.outlier, st.session_state.threshold,
                                 st.session_state.use_ttm, exclusions)
        progress = st.sidebar.progress(0, text="Hazırlanıyor")
        def update(value: int, text: str) -> None:
            progress.progress(value, text=text)
        with st.spinner("Finansal veriler indiriliyor ve model hesaplanıyor..."):
            result = run_valuation(config, forecast_inputs, wacc_inputs, terminal, comps,
                                   company_loader=cached_company, progress=update)
        st.session_state.results = result
        progress.empty(); st.sidebar.success("Değerleme tamamlandı")
        st.rerun()
    except Exception as exc:
        st.session_state.results = None
        st.sidebar.error(f"Değerleme tamamlanamadı: {exc}")


def require_results() -> dict[str, Any] | None:
    result = st.session_state.get("results")
    if result is None:
        st.info("Sol panelde varsayımları kontrol edip **Değerlemeyi Çalıştır** düğmesine basın.")
        return None
    return result


def recommendation(results: dict[str, Any]) -> tuple[str, str]:
    upside = results["upside"]
    spread = results["football"]["High"].max() - results["football"]["Low"].min()
    price = results["market"]["Current Price"]
    if spread / price > .50:
        label = "Geniş değerleme aralığı"
    elif abs(upside) <= .05:
        label = "Yaklaşık makul değer"
    else:
        label = "İma edilen yukarı potansiyel" if upside > 0 else "İma edilen aşağı yönlü fark"
    text = f"Harmanlanmış model değeri mevcut fiyata göre {percent(upside)} fark göstermektedir. Sonuç WACC, terminal değer ve operasyonel varsayımlara duyarlıdır; doğrudan al/sat önerisi değildir."
    return label, text
