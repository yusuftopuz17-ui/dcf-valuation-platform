"""Dedicated private-company FCFF valuation workspace."""

from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.data_loader import cached_company
from src.formatting import money, percent
from src.ui import banner, comments, footer, kpi, page_header, section
from src.visualizations import COLORS, heatmap, layout
from valuation_platform.data import snapshot, standardize
from valuation_platform.private_company import PrivateCompanyConfig, run_private_dcf


def peer_benchmarks(tickers: list[str], years: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, failed = [], []
    for ticker in tickers:
        try:
            raw = cached_company(ticker, years); financials = standardize(raw, years); market = snapshot(raw, financials)
            latest = financials.iloc[-1]
            tax = float(np.clip(latest.get("Tax Expense", 0) / latest.get("EBIT", np.nan), 0, .50)) if latest.get("EBIT", 0) > 0 else .21
            rows.append({"Ticker": ticker, "Company": market["Company"], "Levered Beta": market["Beta"], "Debt": market["Debt"],
                         "Equity": market["Market Cap"], "Tax Rate": tax, "Revenue Growth": financials["Revenue"].pct_change().iloc[-1],
                         "EBITDA Margin": latest["EBITDA"] / latest["Revenue"], "EV/EBITDA": market["Enterprise Value"] / latest["EBITDA"] if latest["EBITDA"] > 0 else np.nan,
                         "Source": market["Source URL"], "Retrieved At": market["Retrieved At"]})
        except Exception as exc:
            failed.append({"Ticker": ticker, "Reason": str(exc)})
    if len(rows) < 2:
        raise ValueError("Savunulabilir özel şirket beta ve çarpanı için en az iki geçerli benzer şirket gerekir.")
    return pd.DataFrame(rows).set_index("Ticker"), pd.DataFrame(failed)


page_header("Özel Şirket DCF", "Raporlanan veriyi, normalizasyonları, benzer şirket tahminlerini ve manuel müdahaleleri açıkça ayıran FCFF değerlemesi.")
banner("Metodoloji sınırı", "Şirket adı veya açıklaması tek başına parasal değer üretmez. En az hasılat, EBITDA, EBIT, FCFF veya güvenilir yönetim tahmini gerekir; aksi durumda yalnızca benzer şirket göstergeleri sunulur.")

current_year = date.today().year
default_history = pd.DataFrame({"Year": range(current_year - 4, current_year + 1), "Revenue": [np.nan] * 5, "EBITDA": [np.nan] * 5,
                                "EBIT": [np.nan] * 5, "Taxes": [np.nan] * 5, "D&A": [np.nan] * 5, "Capex": [np.nan] * 5,
                                "NWC": [np.nan] * 5, "Debt": [np.nan] * 5, "Cash": [np.nan] * 5})
default_adjustments = pd.DataFrame({"Year": [current_year], "Metric": ["EBITDA"], "Amount": [0.0], "Reason": [""], "Approved": [False]})

section("1 · Şirket, Ölçek ve Tarihsel Finansallar")
st.caption("Tüm parasal girişleri seçilen para biriminin milyonları olarak girin. Boş alanlar tahmin edilmeye çalışılır ve kaynak etiketiyle gösterilir.")
c1, c2, c3 = st.columns([1.4, 1, 1])
company_name = c1.text_input("Özel şirket adı", placeholder="Örn. ABC Yazılım A.Ş.")
currency = c2.selectbox("Değerleme para birimi", ["USD", "EUR", "TRY", "GBP"])
forecast_years = c3.slider("Tahmin dönemi", 3, 10, 5)
uploaded = st.file_uploader("İsteğe bağlı tarihsel CSV", type=["csv"], help="Sütunlar: Year, Revenue, EBITDA, EBIT, Taxes, D&A, Capex, NWC, Debt, Cash")
if uploaded is not None:
    try: default_history = pd.read_csv(uploaded)
    except Exception as exc: st.error(f"CSV okunamadı: {exc}")
history = st.data_editor(default_history, width="stretch", num_rows="dynamic", key="private_history")

section("2 · Normalizasyon Düzeltmeleri")
st.caption("Pozitif tutar normalleştirilmiş kârı artırır, negatif tutar düşürür. Düzeltme yalnızca Onaylandı seçili ve gerekçe doluysa uygulanır.")
adjustments = st.data_editor(default_adjustments, width="stretch", num_rows="dynamic", key="private_adjustments",
                             column_config={"Metric": st.column_config.SelectboxColumn(options=["EBITDA", "EBIT", "Revenue"]), "Approved": st.column_config.CheckboxColumn("Onaylandı")})

section("3 · Benzer Şirketler ve Otomatik/Manuel Varsayımlar")
c1, c2 = st.columns([1.4, 1])
peer_text = c1.text_input("Halka açık benzer şirket sembolleri", "MSFT, AAPL, GOOGL, ORCL, CRM")
mode = c2.segmented_control("Varsayım modu", ["Otomatik", "Manuel"], default="Otomatik")
manual = mode == "Manuel"
c1, c2, c3, c4 = st.columns(4)
initial_growth = c1.number_input("İlk yıl büyüme %", -50.0, 100.0, 8.0, .5, disabled=not manual)
mature_growth = c2.number_input("Olgun büyüme %", -10.0, 30.0, 4.0, .5, disabled=not manual)
initial_margin = c3.number_input("İlk EBITDA marjı %", -50.0, 100.0, 20.0, .5, disabled=not manual)
mature_margin = c4.number_input("Olgun EBITDA marjı %", -50.0, 100.0, 22.0, .5, disabled=not manual)
c1, c2, c3 = st.columns(3)
da_ratio = c1.number_input("D&A / Hasılat %", 0.0, 50.0, 3.0, .5, disabled=not manual)
capex_ratio = c2.number_input("Capex / Hasılat %", 0.0, 80.0, 4.0, .5, disabled=not manual)
nwc_ratio = c3.number_input("NWC / Hasılat %", -50.0, 100.0, 5.0, .5, disabled=not manual)

section("4 · Özel Şirket Beta ve WACC")
c1, c2, c3, c4 = st.columns(4)
rf = c1.number_input("Risksiz faiz %", -5.0, 40.0, 4.0, .1)
erp = c2.number_input("Hisse risk primi %", 0.0, 40.0, 5.5, .1)
crp = c3.number_input("Ülke risk primi %", 0.0, 50.0, 0.0, .1)
tax = c4.number_input("Normalleştirilmiş vergi %", 0.0, 60.0, 21.0, .5)
c1, c2, c3 = st.columns(3)
cost_debt = c1.number_input("Vergi öncesi borç maliyeti %", 0.0, 60.0, 6.0, .1)
debt_weight = c2.number_input("Hedef borç ağırlığı %", 0.0, 90.0, 20.0, 1.0)
additional_risk = c3.number_input("Ek risk düzeltmesi %", 0.0, 20.0, 0.0, .25, help="Otomatik eklenmez; kullanılırsa ampirik gerekçe girin.")
additional_reason = st.text_input("Ek risk düzeltmesi gerekçesi", disabled=additional_risk == 0)

section("5 · Terminal Değer ve Özsermaye Köprüsü")
c1, c2, c3 = st.columns(3)
terminal_growth = c1.number_input("Terminal büyüme %", -2.0, 10.0, 2.5, .1)
auto_exit = c2.toggle("Çıkış çarpanını benzer medyanından al", True)
exit_multiple = c3.number_input("Manuel çıkış EV/EBITDA", .5, 50.0, 10.0, .5, disabled=auto_exit)
mid_year = st.toggle("Yıl ortası iskonto", True)
c1, c2, c3, c4 = st.columns(4)
cash = c1.number_input("Nakit", 0.0, value=0.0)
debt = c2.number_input("Faiz taşıyan borç", 0.0, value=0.0)
nonop = c3.number_input("Faaliyet dışı varlıklar", 0.0, value=0.0)
debt_like = c4.number_input("Borç benzeri yükümlülükler", 0.0, value=0.0)

section("6 · İsteğe Bağlı Hissedar / İşlem Düzeltmesi")
apply_shareholder = st.toggle("DLOM, kontrol veya azınlık düzeltmesi uygula", False)
c1, c2 = st.columns([1, 2])
shareholder_pct = c1.number_input("Düzeltme %", -90.0, 100.0, -15.0, 1.0, disabled=not apply_shareholder)
shareholder_reason = c2.text_input("Düzeltme gerekçesi", disabled=not apply_shareholder)

if st.button("Özel Şirket Değerlemesini Çalıştır", type="primary", width="stretch"):
    try:
        tickers = list(dict.fromkeys(x.strip().upper() for x in peer_text.split(",") if x.strip()))
        with st.spinner("Benzer şirket verileri indiriliyor, beta ayrıştırılıyor ve özel şirket DCF hesaplanıyor..."):
            peers, failed = peer_benchmarks(tickers)
            scale_cols = ["Revenue", "EBITDA", "EBIT", "Taxes", "D&A", "Capex", "NWC", "Debt", "Cash"]
            history_model = history.copy()
            for col in scale_cols: history_model[col] = pd.to_numeric(history_model.get(col), errors="coerce") * 1_000_000
            adjustments_model = adjustments.copy(); adjustments_model["Amount"] = pd.to_numeric(adjustments_model.get("Amount"), errors="coerce") * 1_000_000
            config = PrivateCompanyConfig(company_name, currency, forecast_years, tax / 100, rf / 100, erp / 100, crp / 100,
                                          additional_risk / 100, cost_debt / 100, debt_weight / 100, terminal_growth / 100,
                                          None if auto_exit else exit_multiple, mid_year)
            overrides = None if not manual else {"Initial Revenue Growth": initial_growth / 100, "Mature Revenue Growth": mature_growth / 100,
                                                  "Initial EBITDA Margin": initial_margin / 100, "Mature EBITDA Margin": mature_margin / 100,
                                                  "D&A / Revenue": da_ratio / 100, "Capex / Revenue": capex_ratio / 100, "NWC / Revenue": nwc_ratio / 100}
            result = run_private_dcf(history_model, adjustments_model, peers, config,
                                     {"Cash": cash * 1_000_000, "Debt": debt * 1_000_000, "Non-operating Assets": nonop * 1_000_000, "Debt-like Liabilities": debt_like * 1_000_000},
                                     overrides, {"enabled": apply_shareholder, "percent": shareholder_pct / 100, "reason": shareholder_reason})
            result["failed_peers"] = failed; result["config"] = config
            result["additional_risk_reason"] = additional_reason
            st.session_state.private_results = result
    except Exception as exc:
        st.error(f"Özel şirket değerlemesi tamamlanamadı: {exc}")

r = st.session_state.get("private_results")
if r:
    section("Özel Şirket Değerleme Çıktısı")
    st.warning(r["warning"])
    if r["status"] == "benchmarks_only":
        st.error("Mutlak işletme değeri üretilmedi: en az bir şirket ölçeği girdisi eksik.")
        st.dataframe(r["assumptions"], width="stretch"); st.dataframe(r["peers"], width="stretch")
    else:
        c1, c2, c3, c4 = st.columns(4)
        dcf = r["dcf"]
        with c1: kpi("DCF · Sürekli Büyüme EV", money(dcf.iloc[0]["Enterprise Value"], r["config"].currency, True), "FCFF bazlı", "info")
        with c2: kpi("DCF · Çıkış Çarpanı EV", money(dcf.iloc[1]["Enterprise Value"], r["config"].currency, True), f"{r['exit_multiple']:.1f}x", "info")
        with c3: kpi("WACC", percent(r["wacc"]), f"Ek risk hariç {percent(r['wacc_base'])}", "neutral")
        with c4: kpi("Model Güveni", r["overall_confidence"], str(r["confidence_factors"]), "neutral")
        tabs = st.tabs(["Normalizasyon", "Tahmin ve FCFF", "Beta ve WACC", "Terminal ve Köprü", "Senaryolar", "Kaynak ve Güven"])
        with tabs[0]:
            st.dataframe(r["normalized_history"], width="stretch"); st.dataframe(r["adjustment_log"], width="stretch")
        with tabs[1]:
            st.dataframe(r["assumptions"], width="stretch"); st.dataframe(r["forecast"], width="stretch")
            fig = go.Figure([go.Bar(x=r["forecast"].index, y=r["forecast"]["FCFF"], marker_color=COLORS["teal"])])
            st.plotly_chart(layout(fig, "Tahmini FCFF"), width="stretch")
        with tabs[2]:
            st.dataframe(r["beta_table"], width="stretch"); st.dataframe(r["beta_exclusions"], width="stretch")
            st.dataframe(r["wacc_table"], width="stretch")
        with tabs[3]:
            st.dataframe(r["dcf"].style.format({"Terminal Value": "{:,.0f}", "PV Terminal Value": "{:,.0f}", "Enterprise Value": "{:,.0f}", "Equity Value": "{:,.0f}", "Terminal Value % EV": "{:.1%}"}), width="stretch")
            st.dataframe(r["bridge"], width="stretch")
            adj = r["shareholder_adjustment"]
            st.info(f"Hissedar düzeltmesi öncesi: {money(adj['Value before adjustment'], r['config'].currency)} · sonrası: {money(adj['Value after adjustment'], r['config'].currency)} · gerekçe: {adj.get('reason') or 'Uygulanmadı'}")
        with tabs[4]:
            st.dataframe(r["scenarios"], width="stretch")
            st.plotly_chart(heatmap(r["sensitivity"], "Özel Şirket DCF · WACC / Terminal Büyüme", dcf.iloc[0]["Enterprise Value"]), width="stretch")
        with tabs[5]:
            comments([f"Genel model güveni: {r['overall_confidence']}", f"Güven etkenleri: {r['confidence_factors']}",
                      "Şirket girdileri, benzer şirket tahminleri, makro girdiler ve manuel düzeltmeler ayrı etiketlenmiştir."])
            st.dataframe(r["peers"] if "peers" in r else r["beta_table"], width="stretch")
            if not r["failed_peers"].empty: st.dataframe(r["failed_peers"], width="stretch")

footer()
