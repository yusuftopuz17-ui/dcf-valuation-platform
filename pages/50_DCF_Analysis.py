"""Interactive forward and reverse DCF workspace with live market context."""

from __future__ import annotations

import html
import json

import numpy as np
import pandas as pd
import streamlit as st

from src.ccv_provider import company_record
from src.ui import footer, page_header, section
from valuation_platform.market_tools import (
    dcf_sensitivity,
    forward_dcf,
    reverse_dcf,
    reverse_dcf_sensitivity,
    scenario_table,
)
from valuation_platform.model import historical_metrics


def _money(value: float, currency: str, decimals: int = 1) -> str:
    if not np.isfinite(value):
        return "N/M"
    for divisor, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(value) >= divisor:
            return f"{currency} {value/divisor:,.{decimals}f}{suffix}"
    return f"{currency} {value:,.2f}"


def _result_card(result: dict, company: str, currency: str) -> None:
    upside = result["Upside"]
    tone = "br-danger" if np.isfinite(upside) and upside < 0 else ""
    direction = "aşağı yönlü fark" if np.isfinite(upside) and upside < 0 else "yukarı potansiyel"
    delta = f"%{abs(upside)*100:.1f} {direction}" if np.isfinite(upside) else "Fiyat girilmedi"
    st.markdown(
        f"""<div class="br-result {tone}">
        <div class="br-kicker">{html.escape(company)}</div>
        <div class="br-note">DCF ile hesaplanan özsermaye değeri</div>
        <div class="br-big">{_money(result['Equity Value'], currency)}</div>
        <div class="br-grid">
          <div class="br-stat"><span>Hisse başına</span><strong>{currency} {result['Per Share']:,.2f}</strong></div>
          <div class="br-stat"><span>Güncel fiyat</span><strong>{currency} {(result['Current Price'] or 0):,.2f}</strong></div>
          <div class="br-stat"><span>Fiyat farkı</span><strong>{delta}</strong></div>
        </div>
        <p class="br-note" style="margin-top:18px">Terminal değer payı %{result['Terminal Share']*100:.1f}.
        İşletme değerinden net borç çıkarılarak özsermaye değerine ulaşılmıştır.</p>
        </div>""",
        unsafe_allow_html=True,
    )


def _assumption_inputs(include_growth: bool) -> None:
    st.markdown("<div class='br-kicker'>Temel veriler</div>", unsafe_allow_html=True)
    st.number_input("Güncel hisse fiyatı", min_value=0.0, step=1.0, format="%.2f", key="dcf_price")
    st.number_input("Serbest nakit akışı (son dönem)", min_value=1.0, step=1_000_000.0,
                    format="%.2f", key="dcf_base_fcf",
                    help="Otomatik yüklemede sağlayıcının serbest nakit akışı; yoksa finansal tablolardan hesaplanan UFCF.")
    st.number_input("Seyreltilmiş hisse sayısı", min_value=1.0, step=1_000_000.0,
                    format="%.2f", key="dcf_shares")
    st.number_input("Net borç", step=1_000_000.0, format="%.2f", key="dcf_net_debt",
                    help="Borç eksi nakit. Net nakit pozisyonu negatif girilir.")
    st.divider()
    st.markdown("<div class='br-kicker'>Model varsayımları</div>", unsafe_allow_html=True)
    if include_growth:
        st.slider("FCF büyümesi (1–5/10. yıllar) %", 0.0, 50.0, step=.5, key="dcf_growth")
    st.slider("Terminal büyüme %", 0.0, 5.0, step=.1, key="dcf_terminal")
    st.slider("İskonto oranı (WACC) %", 1.0, 25.0, step=.5, key="dcf_wacc")
    st.radio("Tahmin dönemi", [5, 10], horizontal=True, key="dcf_years")
    st.toggle("Büyümeyi terminal orana yaklaştır", key="dcf_fade",
              help="Büyüme tahmin dönemi boyunca terminal orana doğrusal olarak yaklaşır.")
    st.toggle("Yıl ortası iskonto", key="dcf_midyear")


defaults = {
    "dcf_quick_ticker": "MSFT", "dcf_quick_package": None,
    "dcf_base_fcf": 100_000_000_000.0, "dcf_shares": 7_500_000_000.0,
    "dcf_net_debt": 0.0, "dcf_price": 0.0, "dcf_growth": 10.0,
    "dcf_terminal": 2.5, "dcf_wacc": 9.0, "dcf_years": 5,
    "dcf_midyear": True, "dcf_fade": False, "dcf_mode": "İleri DCF — Makul Değer",
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

page_header("DCF Değerleme Laboratuvarı",
            "Bir şirketin makul değerini hesaplayın veya piyasa fiyatının gerektirdiği büyümeyi tersine çözün.")
st.radio("Analiz modu", ["İleri DCF — Makul Değer", "Ters DCF — İma Edilen Büyüme"],
         horizontal=True, key="dcf_mode", label_visibility="collapsed")

search_left, search_right = st.columns([4, 1])
search_left.text_input("Borsa sembolü", key="dcf_quick_ticker", placeholder="Örn. AAPL")
load = search_right.button("Verileri Yükle", type="primary", width="stretch")
presets = st.columns([.7, .7, .7, 4])
for column, ticker in zip(presets[:3], ["AAPL", "GOOGL", "MSFT"]):
    if column.button(ticker, key=f"dcf_preset_{ticker}", width="stretch"):
        st.session_state.dcf_quick_ticker = ticker
        st.rerun()

if load:
    try:
        with st.spinner("Piyasa ve finansal veriler alınıyor..."):
            package = company_record(st.session_state.dcf_quick_ticker.strip().upper())
            record = package["record"]
            provider_fcf = float(pd.to_numeric(record.get("Free Cash Flow"), errors="coerce"))
            if not np.isfinite(provider_fcf) or provider_fcf <= 0:
                fcf_series = historical_metrics(package["historical"])["Free Cash Flow"].replace(
                    [np.inf, -np.inf], np.nan).dropna()
                if fcf_series.empty or fcf_series.iloc[-1] <= 0:
                    raise ValueError("Pozitif serbest nakit akışı bulunamadı; manuel giriş kullanın.")
                provider_fcf = float(fcf_series.iloc[-1])
            st.session_state.dcf_quick_package = package
            st.session_state.dcf_base_fcf = provider_fcf
            st.session_state.dcf_shares = float(record["Diluted Shares"])
            st.session_state.dcf_net_debt = float(record["Net Debt"])
            st.session_state.dcf_price = float(record["Current Price"])
            eps_growth = float(pd.to_numeric(record.get("EPS Growth"), errors="coerce"))
            if np.isfinite(eps_growth) and eps_growth > 0:
                st.session_state.dcf_growth = float(np.clip(eps_growth * 75, 1, 50))
    except Exception as exc:
        st.error(f"Veriler yüklenemedi: {exc}")

package = st.session_state.dcf_quick_package
record = package["record"] if package else {}
company = str(record.get("Company") or st.session_state.dcf_quick_ticker.upper())
currency = str(record.get("Currency") or "USD")
if package:
    st.caption(f"{company} · Canlıya yakın sağlayıcı verisi · Fiyat tarihi {record['Price Date']} · "
               f"Finansal dönem {record['Financial Date']} · Kaynak Yahoo Finance")
else:
    st.info("Sembolü yükleyin veya aşağıdaki alanlara kendi verilerinizi girin. Sonuçlar varsayımlar değiştikçe anında güncellenir.")

growth = st.session_state.dcf_growth / 100
terminal = st.session_state.dcf_terminal / 100
rate = st.session_state.dcf_wacc / 100

if st.session_state.dcf_mode.startswith("İleri"):
    input_col, output_col = st.columns([.38, .62], gap="large")
    with input_col:
        with st.container(border=True):
            _assumption_inputs(include_growth=True)
    try:
        result = forward_dcf(
            st.session_state.dcf_base_fcf, growth, terminal, rate,
            st.session_state.dcf_years, st.session_state.dcf_shares,
            st.session_state.dcf_net_debt, st.session_state.dcf_price or None,
            st.session_state.dcf_midyear, st.session_state.dcf_fade,
        )
    except Exception as exc:
        output_col.error(f"DCF hesaplanamadı: {exc}")
        footer()
        st.stop()

    scenarios = scenario_table(
        st.session_state.dcf_base_fcf, growth, terminal, rate,
        st.session_state.dcf_years, st.session_state.dcf_shares,
        st.session_state.dcf_net_debt, st.session_state.dcf_price or result["Per Share"],
        st.session_state.dcf_midyear, st.session_state.dcf_fade,
    )
    scenario_spread = scenarios["Hisse Başı Değer"].max() - scenarios["Hisse Başı Değer"].min()
    spread_ratio = scenario_spread / max(st.session_state.dcf_price, result["Per Share"], 1)
    sensitivity_label = "Düşük" if spread_ratio < .30 else ("Orta" if spread_ratio < .75 else "Yüksek")

    with output_col:
        if result["Terminal Share"] > .75:
            st.warning(f"Terminal değer toplam işletme değerinin %{result['Terminal Share']*100:.1f}'ini oluşturuyor; "
                       "model uzun vadeli varsayımlara yüksek derecede duyarlı.")
        st.info(f"{sensitivity_label} duyarlılık · Ayı/boğa farkı güncel fiyatın %{spread_ratio*100:.0f}'i")
        _result_card(result, company, currency)
        if np.isfinite(result["Upside"]):
            if result["Upside"] >= 0:
                safety = 1 - st.session_state.dcf_price / result["Per Share"]
                st.success(f"Güvenlik marjı: %{safety*100:.1f}")
                st.progress(float(np.clip(safety, 0, 1)))
            else:
                premium = st.session_state.dcf_price / result["Per Share"] - 1
                st.error(f"Hisse, bu varsayımlardaki DCF değerinin %{premium*100:.1f} üzerinde işlem görüyor.")
                st.progress(float(np.clip(premium, 0, 1)))
        verdict = ("Model fiyatın üzerinde değer üretiyor; büyüme ve WACC varsayımlarının dayanıklılığını "
                   "duyarlılık tablosunda kontrol edin." if result["Upside"] >= 0 else
                   "Piyasa, modelinizden daha yüksek büyüme veya daha düşük risk fiyatlıyor. Bu primin "
                   "operasyonel verilerle savunulması gerekir.")
        st.markdown(f"<div class='br-verdict'><b>Bu ne anlama geliyor?</b><br>{verdict}</div>",
                    unsafe_allow_html=True)

    section("WACC × Terminal Büyüme Duyarlılığı")
    sensitivity = dcf_sensitivity(
        st.session_state.dcf_base_fcf, growth, terminal, rate,
        st.session_state.dcf_years, st.session_state.dcf_shares,
        st.session_state.dcf_net_debt, st.session_state.dcf_midyear,
        st.session_state.dcf_fade,
    ).T
    sensitivity.index = [f"Terminal %{item*100:.1f}" for item in sensitivity.index]
    sensitivity.columns = [f"WACC %{item*100:.1f}" for item in sensitivity.columns]
    st.dataframe(sensitivity.style.format(f"{currency} {{:,.2f}}").background_gradient(cmap="RdYlGn"),
                 width="stretch")
    st.caption("Yeşil hücreler daha yüksek, kırmızı hücreler daha düşük ima edilen değeri gösterir. "
               "Tek bir hücre yerine sonuçların geniş bir varsayım aralığında dayanıklı olup olmadığına bakın.")

    section("Senaryo Karşılaştırması")
    cards = st.columns(3)
    scenario_tones = {"Ayı": "br-danger", "Baz": "", "Boğa": ""}
    for column, (name, row) in zip(cards, scenarios.iterrows()):
        with column:
            st.markdown(
                f"""<div class="br-result {scenario_tones[name]}">
                <div class="br-kicker">{name} senaryosu</div>
                <div class="br-big" style="font-size:2.1rem">{currency} {row['Hisse Başı Değer']:,.2f}</div>
                <div class="br-note">Büyüme %{row['FCF Büyümesi']*100:.1f} · WACC %{row['WACC']*100:.1f}<br>
                Fiyat farkı {row['Fiyat Farkı']:+.1%}</div></div>""",
                unsafe_allow_html=True,
            )

    section("Bugünkü Değer Dağılımı")
    schedule = result["Schedule"].copy()
    pv_chart = schedule.set_index("Yıl")[["Bugünkü Değer"]]
    pv_chart.index = [f"Yıl {year}" for year in pv_chart.index]
    pv_chart.loc["Terminal"] = result["PV Terminal"]
    st.bar_chart(pv_chart)
    st.dataframe(schedule.style.format({
        "Büyüme": "{:.1%}", "Serbest Nakit Akışı": f"{currency} {{:,.0f}}",
        "İskonto Faktörü": "{:.4f}", "Bugünkü Değer": f"{currency} {{:,.0f}}",
    }), width="stretch")

    if package:
        analyst_target = float(pd.to_numeric(record.get("Analyst Target"), errors="coerce"))
        analyst_count = float(pd.to_numeric(record.get("Analyst Count"), errors="coerce"))
        if np.isfinite(analyst_target):
            section("Piyasa · Analist · DCF")
            comps = st.columns(3)
            comps[0].metric("Analist Ortalama Hedefi", f"{currency} {analyst_target:,.2f}",
                            f"{int(analyst_count)} analist" if np.isfinite(analyst_count) else None)
            comps[1].metric("Güncel Fiyat", f"{currency} {st.session_state.dcf_price:,.2f}")
            comps[2].metric("DCF Makul Değeri", f"{currency} {result['Per Share']:,.2f}",
                            f"{result['Upside']:+.1%}")
else:
    input_col, output_col = st.columns([.38, .62], gap="large")
    with input_col:
        with st.container(border=True):
            _assumption_inputs(include_growth=False)
    if st.session_state.dcf_price <= 0:
        output_col.info("Ters DCF için güncel hisse fiyatı gereklidir.")
        footer()
        st.stop()
    implied_growth = reverse_dcf(
        st.session_state.dcf_price, st.session_state.dcf_base_fcf, terminal, rate,
        st.session_state.dcf_years, st.session_state.dcf_shares,
        st.session_state.dcf_net_debt, st.session_state.dcf_midyear,
        st.session_state.dcf_fade,
    )
    consensus = float(pd.to_numeric(record.get("EPS Growth"), errors="coerce")) if package else np.nan
    risk = "Makul beklenti" if implied_growth <= .10 else (
        "Yüksek beklenti" if implied_growth <= .25 else "Agresif büyüme fiyatlanıyor")
    tone = "" if implied_growth <= .25 else "br-danger"
    with output_col:
        st.markdown(
            f"""<div class="br-result {tone}" style="text-align:center">
            <div class="br-kicker">{html.escape(company)}</div>
            <div class="br-note">{st.session_state.dcf_years} yıllık ima edilen FCF büyümesi</div>
            <div class="br-big">%{implied_growth*100:.1f}</div>
            <div class="br-kicker">{risk}</div>
            <div class="br-grid">
              <div class="br-stat"><span>Hisse fiyatı</span><strong>{currency} {st.session_state.dcf_price:,.2f}</strong></div>
              <div class="br-stat"><span>Piyasa değeri</span><strong>{_money(st.session_state.dcf_price*st.session_state.dcf_shares,currency)}</strong></div>
              <div class="br-stat"><span>Mevcut FCF</span><strong>{_money(st.session_state.dcf_base_fcf,currency)}</strong></div>
            </div></div>""",
            unsafe_allow_html=True,
        )
        if np.isfinite(consensus):
            difference = implied_growth - consensus
            st.metric("Analist büyüme konsensüsü", f"%{consensus*100:.1f}",
                      f"İma edilen büyüme farkı {difference*100:+.1f} puan")
        st.markdown(
            f"<div class='br-verdict'>Piyasa fiyatı, seçili WACC ve terminal büyüme altında "
            f"yaklaşık <b>%{implied_growth*100:.1f}</b> yıllık FCF büyümesi gerektiriyor. "
            "Bu oranı şirketin tarihsel büyümesi, sektör görünümü ve analist beklentileriyle karşılaştırın.</div>",
            unsafe_allow_html=True,
        )

    section("İma Edilen Büyüme Duyarlılığı")
    reverse_grid = reverse_dcf_sensitivity(
        st.session_state.dcf_price, st.session_state.dcf_base_fcf, terminal, rate,
        st.session_state.dcf_years, st.session_state.dcf_shares,
        st.session_state.dcf_net_debt, st.session_state.dcf_midyear,
        st.session_state.dcf_fade,
    )
    reverse_grid.index = [f"WACC %{item*100:.1f}" for item in reverse_grid.index]
    reverse_grid.columns = [f"Terminal %{item*100:.1f}" for item in reverse_grid.columns]
    st.dataframe(reverse_grid.style.format("{:.1%}").background_gradient(cmap="RdYlGn_r"),
                 width="stretch")
    st.caption("Daha yüksek ima edilen büyüme, mevcut fiyatın gerçekleşmesi için daha zor operasyonel beklenti demektir.")

section("DCF’yi Nasıl Okumalısınız?")
lesson_cols = st.columns(2)
lessons = [
    ("1 · Serbest nakit akışı", "Faaliyetlerden nakit akışından yatırım harcamalarını çıkarın. Dalgalı şirketlerde tek dönem yerine normalize edilmiş birkaç yıllık ortalama kullanın."),
    ("2 · Büyüme varsayımı", "Tarihsel büyümeyi başlangıç noktası alın; ölçek büyüdükçe yüksek büyümenin kalıcı olamayacağını hesaba katın."),
    ("3 · WACC", "WACC yatırımcının talep ettiği getiridir. Risk yükseldikçe WACC yükselir ve bugünkü değer düşer."),
    ("4 · Duyarlılık", "Tek bir makul değer yanlış kesinlik yaratabilir. Tezin farklı WACC ve terminal büyüme hücrelerinde ayakta kalması önemlidir."),
]
for index, (title, text) in enumerate(lessons):
    with lesson_cols[index % 2]:
        st.markdown(f"<div class='br-lesson'><h3>{title}</h3><p class='br-note'>{text}</p></div>",
                    unsafe_allow_html=True)

with st.expander("Formüller, sınırlamalar ve sık sorulan sorular"):
    st.markdown("""
#### Temel formül

`İşletme Değeri = Açık dönem FCF bugünkü değerleri + Terminal değerin bugünkü değeri`

`Terminal Değer = FCFₙ × (1 + g) / (WACC − g)`

`Özsermaye Değeri = İşletme Değeri − Net Borç`

#### DCF ne zaman zayıflar?

- Negatif veya öngörülemeyen nakit akışına sahip erken aşama şirketlerde,
- Döngünün tepe veya dip noktasındaki emtia ve ağır sanayi şirketlerinde,
- Banka ve sigorta gibi borcun faaliyet girdisi olduğu sektörlerde,
- Terminal değerin toplam değerin çok büyük bölümünü oluşturduğu modellerde.

#### İyi bir güvenlik marjı nedir?

Tek bir evrensel oran yoktur. İş modeli ve tahminler ne kadar belirsizse gereken güvenlik marjı o kadar yüksek olmalıdır.
""")

export_result = {
    "ticker": record.get("Ticker") if package else None,
    "mode": st.session_state.dcf_mode,
    "assumptions": {
        "base_fcf": st.session_state.dcf_base_fcf, "growth": growth,
        "terminal_growth": terminal, "wacc": rate, "years": st.session_state.dcf_years,
        "shares": st.session_state.dcf_shares, "net_debt": st.session_state.dcf_net_debt,
        "current_price": st.session_state.dcf_price, "mid_year": st.session_state.dcf_midyear,
        "fade_growth": st.session_state.dcf_fade,
    },
}
download_col, share_col = st.columns(2)
download_col.download_button(
    "Analizi JSON Olarak İndir", json.dumps(export_result, ensure_ascii=False, indent=2, default=float),
    "dcf_analysis.json", "application/json", width="stretch",
)
if share_col.button("Varsayımları Bağlantıya Yaz", width="stretch"):
    st.query_params.update({
        "g": str(st.session_state.dcf_growth), "tg": str(st.session_state.dcf_terminal),
        "w": str(st.session_state.dcf_wacc), "y": str(st.session_state.dcf_years),
        "fcf": str(st.session_state.dcf_base_fcf), "sh": str(st.session_state.dcf_shares),
        "nd": str(st.session_state.dcf_net_debt), "px": str(st.session_state.dcf_price),
        "mid": "1" if st.session_state.dcf_midyear else "0",
        "fade": "1" if st.session_state.dcf_fade else "0",
    })
    st.success("Varsayımlar adres çubuğuna eklendi; bağlantıyı kopyalayabilirsiniz.")
footer()
