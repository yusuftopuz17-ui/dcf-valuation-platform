"""Fast, evidence-linked public-company comparable analysis."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from src.ccv_provider import company_record, discover_yahoo_candidates, load_candidate_records
from src.ui import banner, footer, kpi, page_header, section
from valuation_platform.ccv import calculate_multiples
from valuation_platform.market_tools import comparable_implied_prices


PEER_PRESETS = {
    "MSFT": ["AAPL", "GOOGL", "ORCL", "CRM", "ADBE", "NOW", "IBM"],
    "AAPL": ["MSFT", "GOOGL", "AMZN", "META", "DELL", "HPQ", "SONY"],
    "GOOGL": ["META", "MSFT", "AMZN", "SNAP", "PINS", "TTD", "BIDU"],
}

SECTOR_PRESETS = {
    "Technology": ["MSFT", "AAPL", "GOOGL", "ORCL", "CRM", "ADBE", "NOW", "IBM"],
    "Communication Services": ["GOOGL", "META", "NFLX", "DIS", "TMUS", "VZ", "T"],
    "Consumer Cyclical": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW"],
    "Consumer Defensive": ["WMT", "COST", "PG", "KO", "PEP", "PM", "CL"],
    "Healthcare": ["LLY", "JNJ", "ABBV", "MRK", "PFE", "TMO", "ABT"],
    "Financial Services": ["JPM", "BAC", "WFC", "C", "GS", "MS", "AXP"],
    "Industrials": ["GE", "CAT", "HON", "RTX", "UPS", "DE", "ETN"],
    "Energy": ["XOM", "CVX", "COP", "EOG", "SLB", "MPC", "PSX"],
}


def _candidate_universe(ticker: str, sector: str, manual: list[str]) -> list[str]:
    """Prefer stable primary listings; fall back to Yahoo sector discovery."""
    if manual:
        return manual
    candidates = PEER_PRESETS.get(ticker) or SECTOR_PRESETS.get(sector)
    if candidates:
        return [item for item in candidates if item != ticker]
    return [item for item in discover_yahoo_candidates(sector, 20) if item != ticker]


def _fmt_money(value: float, currency: str) -> str:
    if not np.isfinite(value):
        return "N/M"
    for divisor, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(value) >= divisor:
            return f"{currency} {value/divisor:,.1f}{suffix}"
    return f"{currency} {value:,.0f}"


def _display_table(target: pd.Series, peers: pd.DataFrame, view: str) -> pd.DataFrame:
    frame = pd.concat([target.to_frame().T, peers], axis=0)
    frame["P/E"] = np.where(frame["Net Income"] > 0, frame["Market Cap"] / frame["Net Income"], np.nan)
    frame["EV/EBITDA"] = np.where(frame["EBITDA"] > 0, frame["Enterprise Value"] / frame["EBITDA"], np.nan)
    columns = ["Company", "Market Cap", "P/E", "EV/EBITDA", "P/S", "P/B",
               "Revenue Growth", "Net Margin"]
    if view == "Son Dönem + İleri":
        columns += ["Forward P/E", "PEG", "EPS Growth"]
    return frame[columns]


st.session_state.setdefault("quick_comp_ticker", "MSFT")
st.session_state.setdefault("quick_comp_manual", "")
st.session_state.setdefault("quick_comp_package", None)

page_header("Benzer Şirket Analizi", "Hedef şirketi sektör benzerleriyle karşılaştırın; medyan çarpanlardan ima edilen fiyatı görün.")
left, right = st.columns([3, 1])
left.text_input("Borsa sembolü", key="quick_comp_ticker", placeholder="Örn. MSFT")
run = right.button("Analiz Et", type="primary", use_container_width=True)
presets = st.columns([.6, .6, .6, 4])
for column, ticker in zip(presets[:3], ["AAPL", "GOOGL", "MSFT"]):
    if column.button(ticker, use_container_width=True):
        st.session_state.quick_comp_ticker = ticker
        st.rerun()
st.text_input("İsteğe bağlı manuel benzerler", key="quick_comp_manual",
              placeholder="Örn. AAPL, GOOGL, ORCL — boşsa sektör taraması yapılır")

if run:
    ticker = st.session_state.quick_comp_ticker.strip().upper()
    try:
        with st.spinner("Şirket ve benzer şirket verileri Yahoo Finance üzerinden alınıyor..."):
            target_package = company_record(ticker)
            target_record = target_package["record"]
            manual = [item.strip().upper() for item in st.session_state.quick_comp_manual.split(",") if item.strip()]
            universe = _candidate_universe(ticker, target_record["Sector"], manual)[:8]
            peer_frame, failures, histories = load_candidate_records(universe)
            if not peer_frame.empty:
                same_currency = peer_frame["Currency"].eq(target_record["Currency"])
                same_country = peer_frame["Country"].eq(target_record["Country"])
                peer_frame = peer_frame.loc[same_currency & same_country]
            if len(peer_frame) < 3:
                raise ValueError(
                    "Aynı ülke ve para biriminde sağlıklı bir medyan için en az 3 benzer şirket verisi gerekli. "
                    "Manuel benzer şirket alanına birincil borsa sembollerini girin."
                )
            st.session_state.quick_comp_package = {
                "target": target_record, "peers": peer_frame, "failures": failures,
                "source": target_record["Data Source"], "retrieved": target_record["Retrieved At"],
            }
    except Exception as exc:
        st.session_state.quick_comp_package = None
        st.error(f"Analiz tamamlanamadı: {exc}")

package = st.session_state.quick_comp_package
if not package:
    banner("Nasıl çalışır?", "Sembolü girip Analiz Et'e basın. Araç, hedef şirketin sektöründen adayları bulur; işlem çarpanlarını, büyümeyi ve kârlılığı aynı tabloda karşılaştırır.")
    st.caption("Veri yalnızca düğmeye bastığınızda indirilir. Kaynak: Yahoo Finance. Sonuçlar yatırım tavsiyesi değildir.")
    footer()
    st.stop()

target = pd.Series(package["target"], name=package["target"]["Ticker"])
peers = calculate_multiples(package["peers"])
peers["P/S"] = peers.get("P/S")
peers["P/B"] = peers.get("P/B")
target_calc = calculate_multiples(target.to_frame().T).iloc[0]
target_calc.name = target.name
target_calc["P/S"], target_calc["P/B"] = target["P/S"], target["P/B"]
implied = comparable_implied_prices(target_calc, peers)
currency = str(target["Currency"])

section(f"{target['Company']} ({target.name})")
metric_cols = st.columns(4)
metric_cols[0].metric("Güncel Fiyat", f"{currency} {target['Current Price']:,.2f}", target["Price Date"])
metric_cols[1].metric("Piyasa Değeri", _fmt_money(float(target["Market Cap"]), currency))
metric_cols[2].metric("Hasılat Büyümesi", f"%{target['Revenue Growth']*100:,.1f}")
metric_cols[3].metric("Net Kâr Marjı", f"%{target['Net Margin']*100:,.1f}")

view = st.radio("Görünüm", ["Son Dönem", "Son Dönem + İleri"], horizontal=True)
comparison = _display_table(target_calc, peers, view)
numeric_columns = [column for column in comparison.columns if column != "Company"]
numeric_peers = comparison.iloc[1:][numeric_columns].apply(pd.to_numeric, errors="coerce")
median = numeric_peers.median()
median_row = pd.DataFrame([{**{"Company": "Benzer Şirket Medyanı"}, **median.to_dict()}], index=["MEDYAN"])
comparison = pd.concat([comparison, median_row])

percent_columns = [name for name in ["Revenue Growth", "Net Margin", "EPS Growth"] if name in comparison]
formats = {column: "{:.1f}x" for column in ["P/E", "EV/EBITDA", "P/S", "P/B", "Forward P/E", "PEG"] if column in comparison}
formats.update({column: "{:.1%}" for column in percent_columns})
formats["Market Cap"] = "{:,.0f}"
st.dataframe(comparison.style.format(formats, na_rep="N/M")
             .background_gradient(subset=[c for c in ["P/E", "EV/EBITDA", "P/S", "P/B"] if c in comparison],
                                  cmap="RdYlGn_r"),
             use_container_width=True, height=min(490, 75 + 36 * len(comparison)))
st.caption(f"Kaynak: {package['source']} · Hedef finansal dönem: {target['Financial Date']} · "
           f"Fiyat tarihi: {target['Price Date']} · Benzer şirket sayısı: {len(peers)}")

section("Benzer Şirket Medyanları")
median_items = [
    ("F/K", median.get("P/E"), "x"),
    ("FD/FAVÖK", median.get("EV/EBITDA"), "x"),
    ("F/Satışlar", median.get("P/S"), "x"),
    ("PD/DD", median.get("P/B"), "x"),
    ("Hasılat Büyümesi", median.get("Revenue Growth"), "%"),
    ("Net Kâr Marjı", median.get("Net Margin"), "%"),
]
median_cards = []
for label, value, unit in median_items:
    if pd.isna(value):
        rendered = "N/M"
    elif unit == "%":
        rendered = f"%{float(value)*100:.1f}"
    else:
        rendered = f"{float(value):.1f}x"
    median_cards.append(
        f"<div class='br-stat'><span>{label}</span><strong>{rendered}</strong></div>"
    )
st.markdown(
    "<div class='br-shell median-panel'><div class='br-grid'>"
    + "".join(median_cards)
    + "</div></div>",
    unsafe_allow_html=True,
)

section("Çarpanlardan İma Edilen Fiyat")
if implied.empty:
    st.warning("Geçerli çarpan ve pozitif temel finansal metrik kombinasyonu bulunamadı.")
else:
    st.dataframe(implied.style.format({
        "Benzer Medyanı": "{:.1f}x", "İma Edilen Fiyat": f"{currency} {{:,.2f}}",
        "Güncel Fiyat": f"{currency} {{:,.2f}}", "Prim / İskonto": "{:+.1%}",
    }), use_container_width=True)
    prices = implied["İma Edilen Fiyat"]
    blended = prices.median()
    cards = st.columns(3)
    cards[0].metric("Harmanlanmış Orta Nokta", f"{currency} {blended:,.2f}",
                    f"{blended/target['Current Price']-1:+.1%}")
    cards[1].metric("Değerleme Aralığı", f"{currency} {prices.min():,.2f} – {prices.max():,.2f}")
    cards[2].metric("Geçerli Yöntem", str(len(prices)), "EV ve özsermaye çarpanları")
    expensive = int((target_calc[implied.index] > implied["Benzer Medyanı"]).sum())
    verdict = "primli" if blended < target["Current Price"] else "iskontolu"
    banner("Analist Yorumu", f"Hedef şirket, harmanlanmış benzer şirket değerine göre yaklaşık "
           f"%{abs(blended/target['Current Price']-1)*100:.1f} {verdict} görünüyor. "
           f"{expensive}/{len(implied)} çarpanda hedef şirket benzer medyanından daha pahalı. "
           "Büyüme, marj, muhasebe dönemi ve iş modeli farkları yorumlanmadan sonuç tek başına kullanılmamalıdır.")

with st.expander("Metodoloji ve kullanım notları"):
    st.markdown("""
- **F/K (P/E):** Pozitif net kâr üreten şirketlerde özsermaye değerini karşılaştırır.
- **FD/FAVÖK (EV/EBITDA):** Sermaye yapısı ve amortisman farklarını azaltarak işletme değerini karşılaştırır.
- **F/Satışlar (P/S):** Kârlılığı henüz oturmamış büyüme şirketlerinde ek referans sağlar.
- **PD/DD (P/B):** Bankalar ve varlık yoğun şirketlerde daha anlamlıdır.
- İma edilen fiyat, benzer medyan çarpanın hedef şirketin ilgili finansal metriğine uygulanmasıyla hesaplanır.
- Kırmızı/yeşil hücreler yalnızca göreli pahalı/ucuz görünümü destekler; yatırım görüşü değildir.
""")
if not package["failures"].empty:
    with st.expander("Verisi alınamayan adaylar"):
        st.dataframe(package["failures"], use_container_width=True)
footer()
