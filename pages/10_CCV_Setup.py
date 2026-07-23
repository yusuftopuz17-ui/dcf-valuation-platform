"""Public/private CCV setup and execution workspace."""

from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

from src.ccv_provider import YahooFinanceProvider, load_candidate_records
from src.ccv_state import get_project, save_project
from src.ccv_ui import active_filter_chips, ccv_page_navigation, multi_other, render_boundaries, render_weights, select_other
from src.ui import banner, footer, page_header, section
from valuation_platform.ccv import SECTOR_TAXONOMY, ValuationProject, run_ccv, validate_boundaries, validate_weights


BUSINESS_MODELS = ["Product sales", "Service-based", "Subscription", "SaaS", "Marketplace", "Transaction-based",
                   "Licensing", "Franchise", "Manufacturing", "Distribution", "Project-based",
                   "Asset-heavy operations", "Asset-light operations", "Hybrid", "Other"]
CUSTOMERS = ["B2B", "B2C", "B2B2C", "B2G", "Government", "Enterprise customers",
             "Small and medium-sized businesses", "Individual consumers", "Mixed customer base", "Other"]
GROWTH = ["Declining", "Stable", "Low growth", "Moderate growth", "High growth", "Hypergrowth", "Cyclical", "Turnaround", "Other"]
PROFITABILITY = ["Loss-making", "Near break-even", "Low margin", "Moderate margin", "High margin", "Mature and stable", "Volatile", "Other"]
GEOGRAPHIES = ["Local", "National", "Regional", "Europe", "North America", "Latin America", "Middle East",
               "Africa", "Asia-Pacific", "Global", "Emerging markets", "Developed markets", "Other"]
SIZES = ["Micro", "Small", "Lower middle market", "Middle market", "Upper middle market", "Large", "Other"]
REVENUE_MODELS = ["One-time sales", "Recurring subscription", "Contracted recurring revenue", "Usage-based",
                  "Transaction fees", "Commission", "Licensing", "Advertising", "Project-based",
                  "Service fees", "Product sales", "Franchise fees", "Mixed", "Other"]


def optional_number(label: str, key: str, percent: bool = False) -> float | None:
    text = st.text_input(label + " · isteğe bağlı", key=key, placeholder="Boş bırakılabilir")
    if not text.strip():
        return None
    try:
        value = float(text.replace(",", "."))
        return value / 100 if percent else value
    except ValueError:
        st.error(f"{label} sayısal olmalıdır.")
        return None


project = get_project()
page_header("Comparable Company Valuation · Kurulum", "Hedef şirketi tanımlayın, doğrulanmış aday evrenini sağlayın ve tekrarlanabilir benzerlik motorunu çalıştırın.")
st.caption("Adım 1/4 · Şirket ve benzer şirket kurulumu")

if project.company_type is None:
    section("Ne tür bir şirketi değerliyorsunuz?")
    columns = st.columns(2)
    with columns[0], st.container(border=True):
        st.markdown("### Halka Açık Şirket")
        st.write("Şirketi adı veya sembolüyle arayın. Sistem finansal ve piyasa verilerini alır, doğrulanmış adayları puanlar ve işlem çarpanlarını hesaplar.")
        if st.button("Halka Açık Şirketi Seç", type="primary", use_container_width=True):
            project.company_type = "Public"; save_project(project); st.rerun()
    with columns[1], st.container(border=True):
        st.markdown("### Özel Şirket")
        st.write("Şirket profilini ve mevcut finansal ölçüleri girin. Sistem doğrulanmış halka açık adayları puanlar ve uygun değerleme aralığını hesaplar.")
        if st.button("Özel Şirketi Seç", type="primary", use_container_width=True):
            project.company_type = "Private"; save_project(project); st.rerun()
    footer()
    st.stop()

top1, top2, top3 = st.columns([2, 1, 1])
top1.info(f"Aktif şirket türü: **{'Halka Açık' if project.company_type == 'Public' else 'Özel'}**")
if top2.button("Şirket Türünü Değiştir", use_container_width=True):
    project.company_type = None; project.target_identity = {}; project.public_identifier = {}; project.private_profile = {}
    save_project(project); st.rerun()
if top3.button("Kurulumu Temizle", use_container_width=True):
    replacement = ValuationProject(selected_method="Comparable Companies", company_type=project.company_type)
    save_project(replacement); st.session_state.ccv_results = None; st.rerun()

target: dict = {}
private_profile: dict = {}

if project.company_type == "Public":
    section("A · Halka Açık Şirket Çözümleme")
    query_col, exchange_col, search_col = st.columns([2, 1, .7])
    query = query_col.text_input("Şirket adı veya sembol", key="public_query", placeholder="Microsoft veya MSFT")
    exchange_hint = exchange_col.text_input("Borsa · isteğe bağlı", key="exchange_hint", placeholder="NASDAQ")
    if search_col.button("Ara", type="primary", use_container_width=True):
        try:
            matches = YahooFinanceProvider().search(query)
            if exchange_hint:
                matches = [row for row in matches if exchange_hint.casefold() in str(row["Exchange"]).casefold()]
            st.session_state.public_search_results = matches
        except Exception as exc:
            st.error(str(exc))
    matches = st.session_state.get("public_search_results", [])
    if matches:
        match_frame = pd.DataFrame(matches)
        st.dataframe(match_frame, use_container_width=True, hide_index=True)
        labels = [f"{row['Company']} · {row['Ticker']} · {row['Exchange']} · {row['Country']} · {row['Currency']}" for row in matches]
        selected_label = st.selectbox("Doğru şirketi açıkça onaylayın", labels, key="public_match")
        if st.button("Seçilen Şirketi Onayla"):
            chosen = matches[labels.index(selected_label)]
            project.public_identifier = chosen; project.target_identity = chosen
            save_project(project); st.success(f"{chosen['Company']} ({chosen['Ticker']}) onaylandı.")
    if project.public_identifier:
        st.success(f"Onaylı hedef: **{project.public_identifier.get('Company')} ({project.public_identifier.get('Ticker')})** · {project.public_identifier.get('Exchange')}")
    c1, c2, c3 = st.columns(3)
    valuation_date = c1.date_input("Değerleme tarihi", date.today(), key="public_valuation_date")
    currency = c2.selectbox("Raporlama para birimi", ["USD", "EUR", "TRY", "GBP"], key="public_currency")
    geography_preference = c3.text_input("Benzer şirket coğrafya tercihi", key="public_geo", placeholder="North America, Europe")
    description = ""
else:
    section("A · Özel Şirket Profili")
    identity_tab, business_tab, finance_tab = st.tabs(["Kimlik ve Sektör", "İş Modeli ve Pazar", "Ölçek ve Finansallar"])
    with identity_tab:
        c1, c2 = st.columns(2)
        company_name = c1.text_input("Şirket adı", key="private_name")
        website = c2.text_input("Şirket internet sitesi · isteğe bağlı", key="private_website")
        description = st.text_area("Kısa şirket açıklaması", key="private_description")
        c1, c2, c3 = st.columns(3)
        hq_country = c1.text_input("Merkez ülke", key="private_hq")
        operating_countries = c2.text_input("Ana faaliyet ülkeleri", key="private_countries")
        founding_year = c3.number_input("Kuruluş yılı · isteğe bağlı", min_value=1800, max_value=date.today().year,
                                       value=None, step=1, key="private_founding")
        c1, c2 = st.columns(2)
        valuation_date = c1.date_input("Değerleme tarihi", date.today(), key="private_valuation_date")
        currency = c2.selectbox("Raporlama para birimi", ["USD", "EUR", "TRY", "GBP"], key="private_currency")
        sector = select_other("Sektör", list(SECTOR_TAXONOMY), "private_sector")
        subsector_options = SECTOR_TAXONOMY.get(st.session_state.get("private_sector", "Other"), ["Other"])
        subsector = select_other("Alt sektör", subsector_options, "private_subsector")
    with business_tab:
        business_model = multi_other("İş modeli", BUSINESS_MODELS, "private_business_model")
        customer_structure = multi_other("Müşteri yapısı", CUSTOMERS, "private_customers")
        c1, c2 = st.columns(2)
        concentration = c1.selectbox("Müşteri yoğunlaşması", ["Low", "Moderate", "High", "Other"], key="private_concentration")
        recurring_customers = c2.selectbox("Tekrarlayan / tekrarlamayan müşteriler", ["Mostly recurring", "Mixed", "Mostly non-recurring", "Other"], key="private_recurring_customers")
        largest_customer = optional_number("En büyük müşterinin hasılat payı %", "private_largest_customer", True)
        top_five = optional_number("En büyük beş müşterinin hasılat payı %", "private_top5", True)
        customer_description = st.text_area("Kısa müşteri profili", key="private_customer_description")
        growth_profile = select_other("Büyüme profili", GROWTH, "private_growth_profile")
        profitability_profile = select_other("Kârlılık profili", PROFITABILITY, "private_profit_profile")
        geography = multi_other("Coğrafi kapsam", GEOGRAPHIES, "private_geography")
        main_revenue_geo = st.text_input("Ana hasılat coğrafyası", key="private_revenue_geo")
        domestic_pct = optional_number("Yurtiçi hasılat %", "private_domestic", True)
        international_pct = optional_number("Uluslararası hasılat %", "private_international", True)
        revenue_model = multi_other("Hasılat modeli", REVENUE_MODELS, "private_revenue_model")
        recurring_revenue = optional_number("Tekrarlayan hasılat %", "private_recurring_revenue", True)
        retention = optional_number("Müşteri tutma oranı %", "private_retention", True)
        churn = optional_number("Müşteri kayıp oranı %", "private_churn", True)
        contract_duration = optional_number("Ortalama sözleşme süresi · ay", "private_contract")
        backlog = optional_number("Sipariş birikimi / sözleşmeli hasılat", "private_backlog")
    with finance_tab:
        company_size = select_other("Şirket büyüklüğü", SIZES, "private_size")
        c1, c2 = st.columns(2)
        unit = c1.selectbox("Finansal birim", ["actual", "thousands", "millions", "billions"], index=2, key="private_unit")
        employees = c2.number_input("Çalışan sayısı · isteğe bağlı", min_value=0, value=None, step=1, key="private_employees")
        revenue_input = optional_number("Son yıllık hasılat", "private_revenue")
        ebitda_input = optional_number("EBITDA", "private_ebitda")
        ebit_input = optional_number("EBIT", "private_ebit")
        net_income_input = optional_number("Net kâr", "private_net_income")
        total_assets = optional_number("Toplam varlıklar", "private_assets")
        prior_ev = optional_number("Önceden tahmin edilmiş işletme değeri", "private_prior_ev")
        revenue_growth = optional_number("Son hasılat büyümesi %", "private_growth", True)
        cagr = optional_number("Üç yıllık hasılat CAGR %", "private_cagr", True)
        ebitda_margin = optional_number("EBITDA marjı %", "private_ebitda_margin", True)
        ebit_margin = optional_number("EBIT marjı %", "private_ebit_margin", True)
        net_margin = optional_number("Net kâr marjı %", "private_net_margin", True)
        st.markdown("**İşletme değerinden özsermaye değerine köprü**")
        cash_input = optional_number("Nakit", "private_cash")
        debt_input = optional_number("Borç", "private_debt")
        preferred_input = optional_number("İmtiyazlı özsermaye", "private_preferred")
        nci_input = optional_number("Kontrol gücü olmayan paylar", "private_nci")
        nonop_input = optional_number("Diğer faaliyet dışı varlıklar", "private_nonop")
        debt_like_input = optional_number("Diğer borç benzeri yükümlülükler", "private_debt_like")
    factor = {"actual": 1, "thousands": 1e3, "millions": 1e6, "billions": 1e9}[unit]
    target = {
        "Company": company_name, "Ticker": "PRIVATE", "Country": hq_country, "Sector": sector, "Subsector": subsector,
        "Business Description": description, "Business Model": business_model, "Customer Structure": customer_structure,
        "Geography": geography, "Revenue Model": revenue_model, "Revenue": revenue_input * factor if revenue_input is not None else None,
        "EBITDA": ebitda_input * factor if ebitda_input is not None else None,
        "EBIT": ebit_input * factor if ebit_input is not None else None,
        "Net Income": net_income_input * factor if net_income_input is not None else None,
        "Revenue Growth": revenue_growth, "EBITDA Margin": ebitda_margin,
        "Employees": employees, "Currency": currency, "Valuation Date": valuation_date.isoformat(),
    }
    private_profile = {
        "website": website, "founding_year": founding_year, "operating_countries": operating_countries,
        "customer_concentration": concentration, "largest_customer_pct": largest_customer, "top_five_pct": top_five,
        "recurring_customers": recurring_customers, "customer_description": customer_description,
        "growth_profile": growth_profile, "profitability_profile": profitability_profile,
        "three_year_cagr": cagr, "ebit_margin": ebit_margin, "net_margin": net_margin,
        "main_revenue_geography": main_revenue_geo, "domestic_revenue_pct": domestic_pct,
        "international_revenue_pct": international_pct, "company_size": company_size,
        "total_assets": total_assets * factor if total_assets is not None else None, "prior_ev": prior_ev,
        "recurring_revenue_pct": recurring_revenue, "retention_rate": retention, "churn_rate": churn,
        "contract_duration_months": contract_duration, "backlog": backlog,
    }
    bridge = {
        "Cash": cash_input * factor if cash_input is not None else None,
        "Debt": debt_input * factor if debt_input is not None else None,
        "Preferred Equity": preferred_input * factor if preferred_input is not None else 0.0,
        "Non-Controlling Interest": nci_input * factor if nci_input is not None else 0.0,
        "Other Non-operating Assets": nonop_input * factor if nonop_input is not None else 0.0,
        "Debt-like Liabilities": debt_like_input * factor if debt_like_input is not None else 0.0,
    }

section("B · Doğrulanmış Aday Evreni ve Gelişmiş Arama")
banner("Doğrulanmış evren", "Sistem Yahoo Finance sektör taramasından gerçek şirketler bulur. Manuel semboller tarama evrenine eklenir; hiçbir şirket veya finansal veri uydurulmaz.")
auto_discover = st.toggle("Sektöre göre otomatik aday taraması", True)
candidate_text = st.text_area("Manuel aday halka açık şirket sembolleri · isteğe bağlı", key="candidate_tickers",
                              placeholder="Örn. AAPL, MSFT, GOOGL (virgülle ayırın)")
c1, c2, c3, c4 = st.columns(4)
target_peer_count = c1.number_input("Hedef benzer şirket sayısı", 2, 30, 8)
minimum_similarity = c2.slider("Minimum benzerlik puanı", 0.0, 1.0, .35, .05)
period = c3.selectbox("Finansal dönem", ["TTM", "Last Fiscal Year"])
outlier_method = c4.selectbox("Aykırı değer yöntemi", ["IQR", "Winsorization", "Z-score", "No automatic outlier removal"])
outlier_threshold = st.number_input("Aykırı değer eşiği", .5, 5.0, 1.5, .1)
c1, c2, c3 = st.columns(3)
include_companies = c1.text_input("Manuel dahil edilecekler", placeholder="Semboller, virgülle")
exclude_companies = c2.text_input("Manuel hariç tutulacaklar", placeholder="Semboller, virgülle")
locked_companies = c3.text_input("Kilitlenecek şirketler", placeholder="Semboller, virgülle")
c1, c2 = st.columns(2)
include_countries = c1.text_input("Dahil edilen ülkeler", placeholder="Boşsa tümü")
exclude_countries = c2.text_input("Hariç edilen ülkeler", placeholder="Virgülle")
c1, c2 = st.columns(2)
include_exchanges = c1.text_input("Dahil edilen borsalar", placeholder="Boşsa tümü")
exclude_exchanges = c2.text_input("Hariç edilen borsalar", placeholder="Virgülle")

with st.expander("Metrics & Boundaries", expanded=False):
    boundaries = render_boundaries(project.boundaries)
    b1, b2 = st.columns(2)
    apply_boundaries_clicked = b1.button("Filtreleri Uygula", type="primary", use_container_width=True)
    if b2.button("Sınırları Sıfırla", use_container_width=True):
        project.boundaries = {}; save_project(project)
        for key in list(st.session_state):
            if key.startswith("boundary_"):
                del st.session_state[key]
        st.rerun()
    if apply_boundaries_clicked:
        try:
            validate_boundaries(boundaries); project.boundaries = boundaries; save_project(project)
            st.success("Tüm sınırlar normalize edilerek kaydedildi.")
        except ValueError as exc:
            st.error(str(exc))
    active_filter_chips(project.boundaries)

with st.expander("Benzerlik Puanı Ağırlıkları"):
    weights = render_weights(project.similarity_weights)

run_disabled = project.company_type == "Public" and not project.public_identifier
if st.button("CCV Analizini Çalıştır", type="primary", use_container_width=True, disabled=run_disabled):
    try:
        validate_weights(weights)
        candidate_tickers = [item.strip().upper() for item in candidate_text.split(",") if item.strip()]
        with st.spinner("Gerçek finansal veriler indiriliyor, sınırlar uygulanıyor ve benzerlik puanları hesaplanıyor..."):
            if project.company_type == "Public":
                ticker = project.public_identifier["Ticker"]
                package, target_failures, target_histories = load_candidate_records([ticker], 5, period)
                if package.empty:
                    raise ValueError(f"Hedef şirket verisi alınamadı: {target_failures.to_dict('records')}")
                target = package.iloc[0].to_dict(); target["Ticker"] = ticker
                bridge = {"Cash": target.get("Cash"), "Debt": target.get("Debt"),
                          "Preferred Equity": target.get("Preferred Equity", 0),
                          "Non-Controlling Interest": target.get("Non-Controlling Interest", 0),
                          "Other Non-operating Assets": 0.0, "Debt-like Liabilities": 0.0}
            else:
                target_histories = {}
            if auto_discover:
                discovered = YahooFinanceProvider().discover(str(target.get("Sector", "")), max(target_peer_count * 2, 12))
                candidate_tickers = list(dict.fromkeys(discovered + candidate_tickers))
            if not candidate_tickers:
                raise ValueError("Otomatik taramayı etkinleştirin veya en az bir doğrulanabilir aday sembolü girin.")
            candidates, failures, histories = load_candidate_records(candidate_tickers, 5, period)
            if candidates.empty:
                raise ValueError("Sağlayıcıdan hiçbir geçerli aday şirket alınamadı.")
            if project.company_type == "Public":
                candidates = candidates.drop(index=ticker, errors="ignore")
                histories.update(target_histories)
            include_country_set = {x.strip().casefold() for x in include_countries.split(",") if x.strip()}
            exclude_country_set = {x.strip().casefold() for x in exclude_countries.split(",") if x.strip()}
            include_exchange_set = {x.strip().casefold() for x in include_exchanges.split(",") if x.strip()}
            exclude_exchange_set = {x.strip().casefold() for x in exclude_exchanges.split(",") if x.strip()}
            if include_country_set:
                candidates = candidates[candidates["Country"].astype(str).str.casefold().isin(include_country_set)]
            if exclude_country_set:
                candidates = candidates[~candidates["Country"].astype(str).str.casefold().isin(exclude_country_set)]
            if include_exchange_set:
                candidates = candidates[candidates["Exchange"].astype(str).str.casefold().isin(include_exchange_set)]
            if exclude_exchange_set:
                candidates = candidates[~candidates["Exchange"].astype(str).str.casefold().isin(exclude_exchange_set)]
            project.target_identity = target
            project.private_profile = private_profile
            project.financial_inputs = {key: target.get(key) for key in ["Revenue", "EBITDA", "EBIT", "Net Income"]}
            project.boundaries = boundaries
            project.similarity_weights = weights
            project.candidate_tickers = candidate_tickers
            project.included_peers = [x.strip().upper() for x in include_companies.split(",") if x.strip()]
            project.excluded_peers = [x.strip().upper() for x in exclude_companies.split(",") if x.strip()]
            project.locked_peers = [x.strip().upper() for x in locked_companies.split(",") if x.strip()]
            project.outlier_settings = {"method": outlier_method, "threshold": outlier_threshold}
            project.manual_overrides = {"target_peer_count": target_peer_count, "minimum_similarity": minimum_similarity,
                                        "period": period, "valuation_date": valuation_date.isoformat(), "currency": currency}
            result = run_ccv(target, candidates, project, bridge)
            result["provider_failures"] = failures
            result["historical"] = histories.get(target.get("Ticker"), pd.DataFrame())
            st.session_state.ccv_results = result
            st.session_state.ccv_histories = histories
            save_project(project)
        st.success("CCV analizi tamamlandı. Yönetici Özeti sayfasına geçebilirsiniz.")
        if len(result["selected_peers"]) < target_peer_count:
            st.warning("Hedef sayıya ulaşmak için sınırlar sessizce gevşetilmedi. Reddedilen adaylar ve gerekçeler Benzer Şirketler sayfasında gösterilir.")
    except Exception as exc:
        st.error(f"CCV analizi tamamlanamadı: {exc}")

ccv_page_navigation(None, "pages/11_CCV_Executive_Summary.py")
footer()
