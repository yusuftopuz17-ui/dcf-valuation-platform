"""DCF workflow placeholder; existing DCF engine remains preserved."""

import streamlit as st
from src.ui import banner, footer, page_header

page_header("Discounted Cash Flow", "Bağımsız DCF çalışma alanı")
banner("Sonraki geliştirme aşaması", "Bu değerleme modülü bir sonraki geliştirme aşamasında eklenecektir.")
st.write("Mevcut DCF hesap motoru ve sayfaları kod tabanında korunmaktadır. Yeni çok-yöntemli proje modeliyle bağlantısı bu aşamada bilinçli olarak yapılmamıştır.")
st.button("DCF Kurulumuna Başla", disabled=True)
footer()
