"""Professional report and download center."""

import streamlit as st

from src.formatting import money, percent
from src.reporting import build_csv_bundle, build_excel, build_pdf, build_powerpoint
from src.ui import footer, kpi, page_header, require_results, section


page_header("Rapor Merkezi", "Ekrandaki değerleme ile aynı sonuçlardan üretilen Excel, CSV, PDF ve PowerPoint çıktıları.")
r = require_results()
if r is None: footer(); st.stop()
market = r["market"]
section("Rapor Kapsamı")
c1, c2, c3, c4 = st.columns(4)
with c1: kpi("Hedef Şirket", f"{market['Company']} ({market['Ticker']})", market["Sector"], "info")
with c2: kpi("Mevcut Fiyat", money(market["Current Price"], market["Currency"]), market["Price Date"], "info")
with c3: kpi("WACC", percent(r["wacc"]), f"Terminal büyüme {percent(r['terminal_assumptions'].terminal_growth_rate)}", "neutral")
with c4: kpi("Tahmin Dönemi", f"{r['config'].forecast_years} yıl", f"Oluşturma {r['generated_at'][:19]}", "info")
st.write("**Seçilen benzer şirketler:**", ", ".join(r["peer_multiples"].index))

section("İndirilebilir Raporlar")
try:
    excel_bytes = build_excel(r)
except Exception as exc:
    excel_bytes = None; st.error(f"Excel raporu üretilemedi: {exc}")
try:
    csv_bytes = build_csv_bundle(r)
except Exception as exc:
    csv_bytes = None; st.error(f"CSV paketi üretilemedi: {exc}")
try:
    pdf_bytes = build_pdf(r)
except Exception as exc:
    pdf_bytes = None; st.error(f"PDF raporu üretilemedi: {exc}")
try:
    pptx_bytes = build_powerpoint(r)
except Exception as exc:
    pptx_bytes = None; st.error(f"PowerPoint raporu üretilemedi: {exc}")

cards = st.columns(4)
with cards[0]:
    st.markdown("#### Excel Modeli"); st.caption("18 çalışma sayfası, varsayımlar, model, duyarlılıklar ve kaynaklar.")
    if excel_bytes: st.download_button("Excel'i İndir", excel_bytes, f"{market['Ticker']}_valuation_model.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
with cards[1]:
    st.markdown("#### CSV Paketi"); st.caption("Tüm finansal, tahmin, DCF, benzer şirket ve senaryo tabloları.")
    if csv_bytes: st.download_button("CSV ZIP'i İndir", csv_bytes, f"{market['Ticker']}_valuation_tables.zip", "application/zip", use_container_width=True)
with cards[2]:
    st.markdown("#### PDF Yönetici Raporu"); st.caption("Değerleme aralığı, performans, senaryolar, bulgular ve uyarı metni.")
    if pdf_bytes: st.download_button("PDF'i İndir", pdf_bytes, f"{market['Ticker']}_valuation_report.pdf", "application/pdf", use_container_width=True)
with cards[3]:
    st.markdown("#### PowerPoint Özeti"); st.caption("Düzenlenebilir metinler ve gömülü değerleme grafikleri içeren 8 slayt.")
    if pptx_bytes: st.download_button("PowerPoint'i İndir", pptx_bytes, f"{market['Ticker']}_valuation_summary.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation", use_container_width=True)

section("Model Kontrolleri ve Kaynaklar")
c1, c2 = st.columns(2)
with c1: st.dataframe(r["checks"], use_container_width=True)
with c2: st.dataframe(r["sources"], use_container_width=True)
with st.expander("Ayrıntılı Sınırlamalar ve Feragatname"):
    st.markdown("""
- Tarihsel performans gelecekteki sonuçları garanti etmez.
- Tahminler kullanıcı varsayımlarına ve model mimarisine bağlıdır.
- Benzer şirket seçimi özneldir; muhasebe politikaları ve GAAP dışı düzeltmeler farklı olabilir.
- Para birimi farklılıkları ve API gecikmeleri karşılaştırılabilirliği etkileyebilir.
- Terminal değer DCF'nin büyük bölümünü oluşturabilir ve uzun vadeli varsayımlara duyarlıdır.
- Eksik veya gecikmiş piyasa verileri model sonuçlarını etkileyebilir.
- Çıktılar yatırım tavsiyesi, fairness opinion veya resmî yatırım bankacılığı değerlemesi değildir.
""")
footer()
