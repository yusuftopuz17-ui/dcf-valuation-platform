"""Initial valuation-method selection screen."""

import streamlit as st

from src.ccv_state import method_card, new_project
from src.ui import footer, page_header


page_header("Değerleme Yöntemini Seçin", "Her yöntem bağımsız bir çalışma alanıdır; bir yöntemdeki veriler diğerine geçince silinmez.")
columns = st.columns(3)
with columns[0]:
    method_card("Comparable Company Valuation", "Halka açık benzer şirketlerin işlem çarpanlarından hedef değer aralığı üretir.",
                "Olgun veya büyüyen halka açık ve özel şirketler", "Şirket profili, finansal metrikler ve doğrulanmış aday şirketler",
                "Comparable Companies")
with columns[1]:
    method_card("Discounted Cash Flow", "Gelecekteki serbest nakit akışlarını bugünkü değere indirger.",
                "Tahmin edilebilir nakit akışı olan şirketler", "Finansal tahminler, WACC ve terminal değer varsayımları", "DCF")
with columns[2]:
    method_card("Precedent Transactions", "Benzer şirketlerin geçmiş satın alma işlemlerindeki çarpanları inceler.",
                "Birleşme, satın alma ve stratejik değer analizleri", "Doğrulanmış işlem evreni, işlem değeri ve finansal metrikler",
                "Precedent Transactions")
st.divider()
if st.button("Yeni ve boş bir değerleme başlat", use_container_width=False):
    new_project()
    st.rerun()
footer()
