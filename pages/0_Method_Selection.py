"""Initial valuation-method selection screen."""

import streamlit as st

from src.ccv_state import method_card, new_project
from src.ui import footer, page_header


page_header("Değerleme Aracını Seçin", "Hızlı benzer şirket karşılaştırması veya ileri/ters DCF analiziyle başlayın.")
columns = st.columns(2)
with columns[0]:
    method_card("Benzer Şirket Analizi", "Halka açık benzer şirketlerin işlem çarpanlarından hedef değer aralığı üretir.",
                "Borsada işlem gören şirketler", "Hedef sembol; benzerler otomatik bulunabilir veya manuel girilebilir",
                "Comparable Companies")
with columns[1]:
    method_card("İndirgenmiş Nakit Akışı (DCF)", "Gelecekteki serbest nakit akışlarını bugünkü değere indirger.",
                "Tahmin edilebilir nakit akışı olan şirketler", "Finansal tahminler, WACC ve terminal değer varsayımları", "DCF")
st.divider()
if st.button("Yeni ve boş bir değerleme başlat", use_container_width=False):
    new_project()
    st.rerun()
footer()
