# DCF Engine + Comparable Company Valuation Platform

Kurumsal görünümlü, iki araçlı bir Streamlit değerleme uygulaması. Açılışta kullanıcı **Benzer Şirket Analizi** veya **İleri/Ters DCF** aracını seçer. Her iki araç da gerçek piyasa verisiyle çalışır ve manuel varsayımlara izin verir.

Uygulama yatırım bankacılığı, özel sermaye, equity research, kurumsal finans ve üniversite çalışmalarında kullanılmak üzere tasarlanmıştır. Sonuçlar yatırım tavsiyesi değildir.

## Başlıca özellikler

- Yahoo Finance sektör taramasıyla otomatik benzer şirket keşfi ve manuel sembol girişi
- Son dönem / ileri görünüm; F/K, FD/FAVÖK, F/Satışlar ve PD/DD
- Benzer medyanları, renkli göreli karşılaştırma ve dört yöntemli ima edilen fiyat
- Harmanlanmış orta nokta, değerleme aralığı ve kural bazlı analist yorumu
- İleri DCF ile makul değer; ters DCF ile piyasanın ima ettiği FCF büyümesi
- 5/10 yıl, büyüme fade'i, yıl ortası iskonto ve açık net borç köprüsü
- Ayı, baz ve boğa senaryoları; 9×9 WACC / terminal büyüme duyarlılığı
- Yıllık nakit akışı bugünkü değer tablosu ve terminal değer yoğunlaşma uyarısı
- Varsa analist konsensüs hedefiyle piyasa/DCF karşılaştırması
- Paylaşılabilir URL varsayımları ve indirilebilir JSON analiz
- Koyu siyah/füme kurumsal tasarım
- Pahalı veri indirmelerinde `st.cache_data` ve açık çalıştırma düğmesi

## Aktif araçlar

1. **Benzer Şirket Analizi:** Hedef sembol, otomatik/manüel benzerler, karşılaştırma tablosu ve ima edilen fiyatlar.
2. **İleri ve Ters DCF:** Otomatik temel veriler veya manuel giriş, senaryolar, duyarlılık ve bugünkü değer köprüsü.

Gelişmiş eski model ve raporlama modülleri kod tabanında geriye dönük uyumluluk için korunur; kullanıcı navigasyonunda yalnızca bu iki hızlı araç görünür. Kamuya açık referans özelliklerinin eşleme belgesi: [`docs/BASIS_FEATURE_MAP.md`](docs/BASIS_FEATURE_MAP.md).

## CCV benzer şirket metodolojisi

```text
Benzerlik Puanı =
%15 Sektör + %20 Alt Sektör + %15 İş Modeli + %10 Müşteri Yapısı
+ %10 Coğrafya + %10 Ölçek + %7,5 Büyüme + %7,5 Kârlılık + %5 Hasılat Modeli
```

Kullanıcı ağırlıkları değiştirebilir; toplamın her zaman %100 olması gerekir. Adaylar önce açık kullanıcı sınırlarından geçirilir, ardından deterministik olarak puanlanır. Sistem hedef peer sayısına ulaşmak için sınırları sessizce gevşetmez.

Ana çarpanlar:

```text
İşletme Değeri = Piyasa Değeri + Borç + İmtiyazlı Özsermaye
                 + Kontrol Gücü Olmayan Paylar - Nakit
EV/Revenue = İşletme Değeri / Hasılat
EV/EBITDA = İşletme Değeri / EBITDA
EV/EBIT = İşletme Değeri / EBIT
P/E = Özsermaye Değeri / Net Kâr
```

Sıfır veya negatif EBITDA, EBIT ve net kâr için ilgili çarpan hesaplanmaz ve arayüzde **N/M** gösterilir. Ana değerleme referansı medyandır; 25. ve 75. yüzdelikler tavsiye aralığını oluşturur.

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

1. Açılışta **Benzer Şirket Analizi** veya **DCF** aracını seçin.
2. Şirket sembolünü girip **Analiz Et** ya da **Verileri Yükle** düğmesine basın.
3. Otomatik gelen şirket verilerini ve varsayımları kontrol edin.
4. Benzer şirket medyanlarını veya DCF senaryo/duyarlılık sonuçlarını inceleyin.
5. DCF varsayımlarını bağlantıya yazabilir veya analizi JSON olarak indirebilirsiniz.

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
├── pages/                 # Yöntem seçimi, aktif hızlı araçlar ve korunmuş eski sayfalar
├── docs/                  # Kamuya açık referans özellik eşlemesi
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

Testler; yöntem seçimi, şirket türü dallanması, taksonomi, birim ve sınır normalizasyonu, ağırlık toplamı, benzerlik puanı, manuel peer kontrolleri, negatif paydalarda N/M, aykırı değerler, medyan/çeyreklikler, ima edilen işletme ve özsermaye değeri, hisse başına değer, eksik finansal veri, rapor çıktıları, korunmuş DCF hesapları ve Streamlit başlangıcını kapsar.

## Sınırlamalar

- Tarihsel performans geleceği garanti etmez.
- Tahminler kullanıcı varsayımlarına bağlıdır.
- Benzer şirket seçimi özneldir.
- Şirketlerin muhasebe ve GAAP dışı düzeltmeleri farklı olabilir.
- Para birimi farklılıkları karşılaştırılabilirliği etkiler; otomatik FX çevirisi yapılmaz.
- Döneme özgü doğrulanmış FX sağlayıcısı yapılandırılmadığı için parasal sınırlar yalnızca aynı para birimindeki adaylara uygulanır; uyumsuz adaylar gerekçeyle reddedilir.
- Yahoo sektör taraması geniş bir başlangıç evrenidir; iş modeli ve müşteri yapısı sağlayıcıda bulunmadığında puan bileşeni nötr kabul edilir.
- Haricî bir yapay zekâ sağlayıcısı yapılandırılmamıştır. Nitel açıklamalar deterministik kurallarla üretilir; matematiksel CCV akışı bundan etkilenmez.
- Terminal değer DCF'nin büyük bölümünü oluşturabilir.
- API verileri gecikmiş, eksik veya revize edilmiş olabilir.
- Piyasa fiyatları hızlı değişebilir.

## Feragatname

Sonuçlar tarihsel veriler, piyasa bilgileri, seçilen benzer şirketler ve kullanıcı varsayımlarından türetilen model bazlı tahminlerdir. Tahmin, garanti, fairness opinion, resmî yatırım bankacılığı değerlemesi veya yatırım tavsiyesi değildir.

## Lisans

MIT License.
