"""CCV-specific executive summary."""

import numpy as np
import pandas as pd
import streamlit as st

from src.ccv_state import get_project
from src.ccv_ui import ccv_page_navigation
from src.formatting import money, percent
from src.ui import banner, comments, footer, kpi, page_header, section


project = get_project()
page_header("CCV · Yönetici Özeti", "Benzer şirket seçimi, ana çarpanlar, değer aralıkları ve veri sınırlamaları tek görünümde.")
st.caption("Adım 2/4 · Yönetici değerlendirmesi")
result = st.session_state.get("ccv_results")
if not result:
    st.info("Önce CCV Kurulumu sayfasında hedef ve aday şirketleri doğrulayıp analizi çalıştırın.")
    ccv_page_navigation("pages/10_CCV_Setup.py", None); footer(); st.stop()

target, confidence = result["target"], result["confidence"]
currency = target.get("Currency") or project.manual_overrides.get("currency", "USD")
section("Hedef Şirket ve Peer Seti")
cols = st.columns(4)
with cols[0]: kpi("Hedef Şirket", target.get("Company", "Mevcut değil"), "Halka açık" if project.company_type == "Public" else "Özel", "info")
with cols[1]: kpi("Sektör / Alt Sektör", str(target.get("Sector", "Mevcut değil")), str(target.get("Subsector", "Mevcut değil")), "neutral")
with cols[2]: kpi("Seçilen Benzerler", str(len(result["selected_peers"])), f"Ortalama benzerlik {percent(confidence['Average Similarity'])}", "info")
with cols[3]: kpi("Peer Seti Güveni", confidence["Level"], f"Puan {confidence['Score']:.2f}", "positive" if confidence["Level"] == "High" else "neutral")
st.write(target.get("Business Description") or project.private_profile.get("description") or "Şirket açıklaması sağlanmadı.")
if project.company_type == "Private":
    banner("Kullanıcı girdisine bağımlılık", "Özel şirket sonuçları kullanıcı tarafından girilen ve bağımsız olarak doğrulanmamış finansal ölçülere bağlıdır.")

section("Ana Finansal Ölçüler")
financial_cols = st.columns(4)
for column, metric in zip(financial_cols, ["Revenue", "EBITDA", "EBIT", "Net Income"]):
    value = target.get(metric)
    with column:
        kpi(metric, money(value, currency, True) if value is not None and np.isfinite(value) else "Mevcut değil",
            "TTM / son kullanılabilir dönem" if project.company_type == "Public" else "Kullanıcı girdisi", "info")

stats = result["summary_statistics"]
valid_stats = stats[stats["Valid Observations"] > 0]
if valid_stats.empty:
    st.error("Geçerli çarpan gözlemi yok; parasal değerleme sunulamaz.")
else:
    relevance = ["EV/EBITDA", "EV/Revenue", "EV/EBIT", "P/E"]
    most_relevant = next((item for item in relevance if item in valid_stats.index and np.isfinite(valid_stats.loc[item, "Median"])), valid_stats.index[0])
    section("Değerleme Özeti")
    implied = result["implied_valuations"]
    median_row = implied[(implied["Multiple"] == most_relevant) & (implied["Statistic"] == "Median")]
    cols = st.columns(4)
    with cols[0]: kpi("Ana Çarpan", most_relevant, "Kârlılık ve veri mevcudiyetine göre", "info")
    with cols[1]: kpi("Medyan Çarpan", f"{stats.loc[most_relevant, 'Median']:.1f}x", f"{int(stats.loc[most_relevant, 'Valid Observations'])} geçerli gözlem", "neutral")
    if not median_row.empty:
        row = median_row.iloc[0]
        with cols[2]:
            kpi("İma Edilen İşletme Değeri", money(row["Implied Enterprise Value"], currency, True) if np.isfinite(row["Implied Enterprise Value"]) else "Uygulanamaz", "Medyan", "info")
        with cols[3]:
            kpi("İma Edilen Özsermaye Değeri", money(row["Implied Equity Value"], currency, True) if np.isfinite(row["Implied Equity Value"]) else "Köprü verisi eksik", "Medyan", "info")
    range_table = implied[implied["Statistic"].isin(["25th Percentile", "Median", "75th Percentile"])]
    if range_table.empty:
        st.warning("Hedef şirkette kullanılabilir hasılat, EBITDA, EBIT veya net kâr ölçüsü olmadığı için parasal değer üretilmedi; yalnızca peer benchmarkları gösterilir.")
    else:
        st.dataframe(range_table, use_container_width=True, hide_index=True,
                     column_config={"Selected Multiple": st.column_config.NumberColumn(format="%.1fx"),
                                    "Implied Enterprise Value": st.column_config.NumberColumn(format="%.0f"),
                                    "Implied Equity Value": st.column_config.NumberColumn(format="%.0f"),
                                    "Implied Value Per Share": st.column_config.NumberColumn(format="%.2f")})

section("Ana Gözlemler ve Sınırlamalar")
observations = [
    confidence["Explanation"],
    "Medyan çarpan ana referanstır; minimum ve maksimum değerler tavsiye aralığı olarak kullanılmaz.",
    f"Veriler {result['generated_at'][:19]} UTC tarihinde üretilmiştir.",
]
if "Warning" in confidence:
    observations.append(confidence["Warning"])
if not result["provider_failures"].empty:
    observations.append(f"{len(result['provider_failures'])} şirket sağlayıcı hatası nedeniyle analize alınamadı.")
if result["bridge"].get("Cash") is None or result["bridge"].get("Debt") is None:
    observations.append("Nakit veya borç eksik olduğu için EV bazlı yöntemlerde özsermaye değeri hesaplanmamıştır.")
comments(observations)

ccv_page_navigation("pages/10_CCV_Setup.py", "pages/12_CCV_Historical_Performance.py")
footer()
