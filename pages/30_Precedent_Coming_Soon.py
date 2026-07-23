"""Precedent-transactions workflow placeholder."""

import streamlit as st
from src.ui import banner, footer, page_header

page_header("Precedent Transactions", "Doğrulanmış birleşme ve satın alma işlemlerine dayalı değerleme")
banner("Sonraki geliştirme aşaması", "Bu değerleme modülü bir sonraki geliştirme aşamasında eklenecektir.")
st.write("İşlem evreni, ödeme türü, açıklanma/kapanış tarihi ve sinerji etkileri olmadan örnek sonuç üretilmez.")
st.button("İşlem Evreni Oluştur", disabled=True)
footer()
