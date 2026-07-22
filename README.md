# DCF Engine + Comparable Company Valuation Platform

Kurumsal görünümlü, çok sayfalı bir Streamlit değerleme uygulaması. Halka açık şirket verilerini analiz eder; ayrıca finansal verisi sınırlı özel şirketler için ayrı bir DCF iş akışı sunar. Beş ila on yıllık işletme tahmini, FCFF, WACC, iki terminal değer yöntemi, benzer şirketler, duyarlılık tabloları, ayı/baz/boğa senaryoları ve football-field değerlemesi üretir.

Uygulama yatırım bankacılığı, özel sermaye, equity research, kurumsal finans ve üniversite çalışmalarında kullanılmak üzere tasarlanmıştır. Sonuçlar yatırım tavsiyesi değildir.

## Başlıca özellikler

- Hedef şirket ve benzer şirket sembollerini değiştirme
- Yıl bazında hasılat büyümesi ve EBITDA marjı girişi
- Vergi, D&A, Capex ve işletme sermayesi sürücüleri
- CAPM özsermaye maliyeti ve vergi sonrası borç maliyeti
- Mevcut veya hedef sermaye yapısıyla WACC
- Sürekli büyüme ve çıkış EV/EBITDA DCF yöntemleri
- EV/Hasılat, EV/EBITDA, EV/EBIT, F/K, P/B ve Fiyat/Satışlar
- IQR, z-skoru, MAD ve manuel hariç tutma
- Üç profesyonel duyarlılık ısı haritası
- Ayı, baz ve boğa senaryoları
- Gerçek duyarlılık ve yüzdelik sonuçlarına dayanan football field
- Kural bazlı otomatik finansal yorumlar; haricî yapay zekâ API'si gerekmez
- Excel, CSV, PDF ve PowerPoint indirmeleri
- Koyu siyah/füme kurumsal tasarım
- Pahalı veri indirmelerinde `st.cache_data` ve açık çalıştırma düğmesi
- Özel şirketler için normalizasyon kayıtları, benzer şirketlerden kaldıraçsız/kaldıraçlı beta ve ayrı risk düzeltmesi
- Eksik veri durumunda uydurma parasal değer yerine yalnızca doğrulanabilir oran ve kıyas sonuçları

## Sayfalar

1. **Yönetici Özeti:** KPI kartları, değerleme aralığı, football field, senaryolar ve temel bulgular.
2. **Tarihsel Performans:** Finansal tablolar, büyüme, marj, FCF dönüşümü, Capex ve net borç.
3. **Tahmin Modeli:** Tarihsel/tahmin ayrımı, sürücüler, hasılat, kârlılık ve UFCF.
4. **DCF Değerleme:** WACC, iskonto tablosu, terminal değer, işletme-özsermaye köprüsü ve uyarılar.
5. **Benzer Şirketler:** Ticari çarpanlar, aykırı gözlemler, dağılımlar, prim/iskonto ve ima edilen değerler.
6. **Duyarlılık ve Senaryolar:** Üç ısı haritası ve ayı/baz/boğa sonuçları.
7. **Rapor Merkezi:** Excel, CSV ZIP, PDF ve PowerPoint raporları; kontroller ve kaynaklar.
8. **Özel Şirket DCF:** Raporlanan ve normalize edilmiş finansallar, özel şirket betası, iki WACC görünümü, iki terminal yöntem, özsermaye köprüsü, senaryolar ve güven seviyesi.

## Finansal metodoloji

### Unlevered serbest nakit akışı

```text
UFCF = EBIT x (1 - vergi oranı) + D&A - Capex - NWC değişimi
```

### WACC

```text
Özsermaye Maliyeti = Risksiz Faiz + Beta x Hisse Risk Primi + Ülke Risk Primi
Vergi Sonrası Borç Maliyeti = Vergi Öncesi Borç Maliyeti x (1 - Vergi Oranı)
WACC = Özsermaye Ağırlığı x Özsermaye Maliyeti + Borç Ağırlığı x Vergi Sonrası Borç Maliyeti
```

### Terminal değer

```text
Sürekli Büyüme TV = UFCF(N) x (1 + g) / (WACC - g)
Çıkış Çarpanı TV = Son Yıl EBITDA x Çıkış EV/EBITDA
```

İşletme değeri net borçla düzeltilerek özsermaye değerine, seyreltilmiş hisse sayısıyla bölünerek hisse başına değere ulaşılır.

### Özel şirket metodolojisi

Özel şirket sayfası halka açık şirket modelinden bağımsız çalışır. Kullanıcı üç ila beş yıllık finansalları ve tek seferlik düzeltmeleri girer; her düzeltme gerekçe ve onay kaydıyla raporlanır. Tahminler şirket geçmişi, benzer şirket medyanları ve olgunlaşma varsayımlarını birleştirir. FCFF şu şekilde hesaplanır:

```text
FCFF = EBIT x (1 - vergi oranı) + D&A - Capex - işletme sermayesi değişimi
```

Özel şirket betası, benzer şirketlerin betalarını sermaye yapısından arındırıp hedef borç/özsermaye yapısıyla yeniden kaldıraçlandırır. İlave özel şirket risk düzeltmesi ayrı gösterilir; WACC hem bu düzeltme hariç hem dâhil raporlanır. Sürekli büyüme ve çıkış çarpanı yöntemleri birlikte sunulur. Nakit, faaliyet dışı varlıklar, faizli borç ve borç benzeri yükümlülükler işletme değerinden özsermaye değerine açık bir köprüyle aktarılır.

Geçerli hasılat, EBITDA, EBIT, FCFF veya güvenilir bir ölçek girdisi bulunmadığında model parasal değer üretmez. Yalnızca oran, marj, benzer şirket ve veri boşluğu sonuçlarını gösterir. Kontrol primi, azınlık iskontosu veya pazarlanabilirlik iskontosu gibi hissedar düzeyi düzeltmeler isteğe bağlıdır ve faaliyet değerinden ayrı raporlanır.

## Veri kaynakları

Varsayılan veri kaynağı `yfinance` üzerinden Yahoo Finance'tır. Her şirket ayrı önbelleğe alınır. Kaynak URL'si ve veri alım zamanı raporlanır. Eksik veya negatif paydalı çarpanlar sessizce doldurulmaz; hariç tutma tablosunda gösterilir.

## Yerel kurulum

Python 3.10 veya üzeri gerekir.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Tarayıcıda `http://localhost:8501` açılır.

## Kullanım

1. Sol panelde hedef şirketi ve benzer şirketleri girin.
2. Tahmin dönemi, büyüme, marj, WACC ve terminal değer varsayımlarını kontrol edin.
3. **Değerlemeyi Çalıştır** düğmesine basın.
4. Sayfalar arasında gezinerek tarihsel analiz, tahmin, DCF, benzer şirketler ve duyarlılıkları inceleyin.
5. Rapor Merkezi'nden çıktıları indirin.

Görsel bir sekme değişikliği veya tablo sıralaması finansal verileri yeniden indirmez. Yeni bir şirket/varsayım seti uygulamak için çalıştırma düğmesine tekrar basılır.

## Streamlit Community Cloud'a dağıtım

1. Bu klasörü bir GitHub deposuna gönderin.
2. [Streamlit Community Cloud](https://share.streamlit.io/) üzerinde **Create app** seçeneğini kullanın.
3. Depo, dal ve `app.py` yolunu seçin.
4. **Deploy** düğmesine basın.

Uygulama anahtar gerektirmeyen Yahoo Finance yolunu kullanır. Kurumsal ağlar ve veri sağlayıcıları hız sınırı uygulayabilir.

## Klasör yapısı

```text
├── app.py
├── pages/                 # Sekiz uygulama sayfası
├── src/                   # UI, cache, grafikler ve raporlama
├── valuation_platform/    # Finansal hesap motoru
├── assets/styles.css      # Siyah/füme tasarım sistemi
├── tests/                 # Finansal, rapor ve başlangıç testleri
├── .streamlit/config.toml
├── requirements.txt
├── pyproject.toml
├── LICENSE
└── README.md
```

## Testler

```bash
pytest
python -m compileall valuation_platform src pages app.py
streamlit run app.py --server.headless true
```

Testler; konfigürasyon, tahmin boyutları, hasılat, EBITDA, FCFF, özel şirket normalizasyonları, özel şirket betası, eksik veri kontrolü, WACC, terminal değer, özsermaye köprüsü, çarpanlar, aykırı değerler, ima edilen değer, duyarlılıklar, senaryo sıralaması, biçimlendirme, rapor üretimi ve Streamlit sayfa başlangıçlarını kapsar.

## Sınırlamalar

- Tarihsel performans geleceği garanti etmez.
- Tahminler kullanıcı varsayımlarına bağlıdır.
- Benzer şirket seçimi özneldir.
- Şirketlerin muhasebe ve GAAP dışı düzeltmeleri farklı olabilir.
- Para birimi farklılıkları karşılaştırılabilirliği etkiler; otomatik FX çevirisi yapılmaz.
- Terminal değer DCF'nin büyük bölümünü oluşturabilir.
- API verileri gecikmiş, eksik veya revize edilmiş olabilir.
- Piyasa fiyatları hızlı değişebilir.

## Feragatname

Sonuçlar tarihsel veriler, piyasa bilgileri, seçilen benzer şirketler ve kullanıcı varsayımlarından türetilen model bazlı tahminlerdir. Tahmin, garanti, fairness opinion, resmî yatırım bankacılığı değerlemesi veya yatırım tavsiyesi değildir.

## Lisans

MIT License.
