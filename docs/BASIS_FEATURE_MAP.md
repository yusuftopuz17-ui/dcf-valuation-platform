# Basis araçları: kamuya açık özellik incelemesi

Bu dosya, `basisreport.com/tools` üzerindeki **Comparable Company Analysis** ve
**DCF Calculator** sayfalarında kamuya açık olarak görülebilen işlevlerin bu
projede nasıl karşılandığını belgeler. Özel kaynak kodu, ağ anahtarları, sunucu
mantığı, marka öğeleri veya telifli görseller kopyalanmamıştır.

## Kamuya açık teknoloji sinyalleri

- Sayfa varlıkları Next.js (`/_next/static/...`) yapısını gösterir.
- Vercel Insights betiği görünür; dağıtım katmanında Vercel kullanıldığı anlaşılır.
- Araç metinleri piyasa verisi kaynağı olarak Yahoo Finance'ı belirtir.
- Özel backend mimarisi ve ticari veri anlaşmaları kamuya açık değildir; bunlar
  teknik olarak ve hukuken doğrulanamaz.

## Benzer Şirketler

| Kamuya açık işlev | Bu projedeki karşılığı |
|---|---|
| Sembol ile hızlı analiz | `Benzer Şirket Analizi` |
| Otomatik sektör benzerleri | Yahoo Finance sektör taraması |
| Manuel benzer girişi | Virgülle ayrılmış semboller |
| Son dönem / ileri metrik görünümü | Görünüm seçici |
| P/E, EV/EBITDA, P/S, P/B | Aynı dört temel çarpan |
| Büyüme ve marj karşılaştırması | Hasılat büyümesi, net marj, EPS büyümesi |
| Sektör/benzer medyanı | Medyan satırı |
| Göreli renk ölçeği | Çarpan hücrelerinde renk gradyanı |
| İma edilen fiyatlar | Dört bağımsız çarpan yöntemi |
| Harmanlanmış aralık | Medyan orta nokta ve min–maks aralığı |
| Açıklayıcı yorum | Kural bazlı analist yorumu |

## DCF

| Kamuya açık işlev | Bu projedeki karşılığı |
|---|---|
| İleri DCF | Makul değer sekmesi |
| Ters DCF | Fiyatın ima ettiği FCF büyümesi |
| 5 / 10 yıllık dönem | Tahmin dönemi seçici |
| Büyümeyi terminal orana yaklaştırma | Fade anahtarı |
| Yıl ortası iskonto | Mid-year anahtarı |
| Ayı / Baz / Boğa | ±6 puan büyüme, ∓2 puan WACC |
| Terminal değer uyarısı | Terminal payı %75 üzeri uyarı |
| WACC × terminal büyüme | 9 × 9 yeniden hesaplanan tablo |
| Yıllık bugünkü değer | FCF iskonto köprüsü |
| Analist hedefi karşılaştırması | Yahoo konsensüsü varsa grafik |
| Paylaşılabilir varsayımlar | URL sorgu parametreleri |
| İndirilebilir analiz | JSON dışa aktarımı |

Bu uygulamada işletme değerinden özsermaye değerine geçerken **net borç açıkça
çıkarılır**. Böylece EV tabanlı DCF sonucu doğrudan hisse sayısına bölünmez ve
sermaye yapısı köprüsü finansal olarak görünür kalır.
