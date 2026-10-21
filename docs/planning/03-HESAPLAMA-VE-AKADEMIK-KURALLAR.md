# Hesaplama ve akademik kurallar

Bu kurallar API, frontend ve testlerin aynı akademik anlamı taşımasını sağlar. Girdi hatalarını frontend erken gösterebilir; yetki, doğrulama ve kalıcı hesaplama her zaman backend'de yapılır. Hesaplayıcı AI kullanmaz.

## Birbirinden ayrı dört ağırlık

| Alan | Anlam | Kural |
| --- | --- | --- |
| `grade_weight` | Değerlendirmenin dersin genel notuna katkısı | Her biri 0–1; ders toplamı 1 olmalı |
| `assessment_lo_weight` | Değerlendirmenin belirli LO'ya etkisi | Her bağlantı 0–1; satır/sütun toplamının 1 olması gerekmez |
| `lo_po_weight` | LO'nun ders içindeki PO'ya etkisi | İlk politika 0–1; toplamın 1 olması gerekmez |
| `course_po_weight` | Bir dersin genel öğrenci PO profiline katkısı | 1–5 tamsayı; bağlantı yoksa katkı yok |

Matrislerde 0 bağlantı yok demektir; kalıcı bağlantı kaydı pozitif ağırlık taşır. Arayüz yüzde gösterirken API oran saklar: `%60` → `"0.6000"`. Dersler arası 1–5 ağırlık yüzdeye çevrilmez. Kredi ve AKTS ayrı alanlardır; bu ağırlıkların hiçbirinin yerine geçmez.

1–5 ölçeğinin hangi katmanda kullanılacağı hocayla netleştirilecek tasarım kararıdır. Yukarıdaki iki katmanlı LO–PO ve ders–PO yaklaşımı planın varsayımıdır. Tek katman istendiğinde `policy_version` ve adapter değişir; UI'de aynı alanın anlamı sessizce değiştirilmez.

## Puan normalizasyonu ve formüller

Öğrenci `s`, değerlendirme `a`, öğrenme çıktısı `l`, program çıktısı `p`, ders açılışı `c` olsun.

`max_score > 0`, `0 ≤ raw_score ≤ max_score` ve bütün ağırlıkların kendi izinli aralığında olması zorunludur. Bonus puan ve negatif puan ilk politika kapsamında değildir. Kredi/AKTS negatif olamaz; kurumun izinli değer listesi ayrı akademik ayardır.

```text
normalized_grade(s,a) = raw_score(s,a) / max_score(a) * 100

course_grade(s,c) = Σ(normalized_grade(s,a) * grade_weight(a))
                   yalnızca bütün gerekli değerlendirmeler çözümlenmişken finaldir

LO(s,l) = Σ(normalized_grade(s,a) * assessment_lo_weight(a,l))
          / Σ(assessment_lo_weight(a,l))

course_PO(s,c,p) = Σ(LO(s,l) * lo_po_weight(l,p))
                  / Σ(lo_po_weight(l,p))

program_PO(s,p) = Σ(course_PO(s,c,p) * course_po_weight(c,p))
                 / Σ(course_po_weight(c,p))
```

Paydalar yalnızca o çıktıya bağlanan ve ilgili politika kapsamında hesaplanabilir girdileri içerir. Eksik/muaf girdi kuralları aşağıdadır. Genel ders notunda tam veri yokken yalnızca gerçekleşen katkı ve kapsama bilgisi gösterilir; bilinmeyen not sıfırmış gibi final not üretilmez.

Kurum kararı olmadan program PO hesabı AKTS ile tekrar çarpılmaz. PO başarısı ile GPA ayrı kavramdır. PO grafiğindeki 85 değeri 4.0'lık not ortalaması değildir.

## Hocanın örneği

[Guidelines s.5–6](../references/README.md#project-guidelines) içindeki örnek:

| Girdi | Değer |
| --- | ---: |
| Midterm | 90 / 100 |
| Project | 80 / 100 |
| Midterm → LO1 | 0.6 |
| Project → LO1 | 0.4 |
| Midterm → LO2 | 0.4 |
| Project → LO2 | 1.0 |
| LO1 → PO1 | 1.0 |
| LO2 → PO1 | 0.5 |
| LO2 → PO2 | 1.0 |

```text
LO1 = (90*0.6 + 80*0.4) / 1.0 = 86
LO2 = (90*0.4 + 80*1.0) / 1.4 = 82.857142857...
PO1 = (86*1.0 + 82.857142857...*0.5) / 1.5 = 84.952380952...
PO2 = 82.857142857...
```

Tek ondalık gösterimde LO1=86.0, LO2=82.9, PO1=85.0, PO2=82.9 olur. Ara aşamada 82 veya 82.9'a yuvarlayarak sonraki hesabı yapmayın. Backend Decimal ile yüksek hassasiyet kullanır; saklanan/iletilen sonuç dört ondalık olabilir, kullanıcı gösterimi bir ondalık ve `ROUND_HALF_UP` politikasıyla yapılır. API `policy_version` döndürür.

**Önemli kabul testi:** LO2'ye gelen ağırlıkların toplamı 1.4'tür. Form bunu “%100'ü geçti” diye reddederse proje yönergesindeki örnek yapılamaz. Yalnızca genel ders notu ağırlık toplamı için %100 kuralı uygulanır.

## Eksik not ve kapsama

Grade durumu `graded`, `missing`, `excused` olabilir. `graded` için puan zorunludur ve 0 gerçek bir puandır. `missing` ve `excused` için puan null olur; muafiyet gerekçesi zorunludur.

- **Missing:** Geçici hesapta mevcut girdilerden puan üretilebilir; kayıp ağırlık kapsama oranını düşürür. Sonuç `partial` etiketi taşır. Final yayını engeller.
- **Excused:** Yetkili kullanıcı gerekçeyle belirler. İlgili öğrenci için pay ve paydadan çıkarılır; yeniden normalizasyon yapılır. Tümü muafsa sonuç `not_applicable`, puan null olur.
- **Hiç bağlantı yok:** Puan null ve `not_mapped` döner. Sıfır başarı anlamına gelmez.
- **Tüm gerekli notlar eksik:** Puan null ve `no_data` döner.

LO kapsamı, puanı bilinen bağlantıların ağırlığının tüm gerekli, muaf olmayan bağlantı ağırlığına oranıdır. PO kapsamı bağlı LO kapsamlarının LO–PO ağırlıklarıyla ortalamasıdır; hesaplanamayan gerekli LO'nun kapsamı 0 sayılır. `not_applicable` LO hem pay hem paydadan çıkarılır. Böylece eksik LO grafikten kaybolarak tamamlanmış görünmez.

Program profilinde ders kapsamı, seçilen dönem/tarih kesitindeki katkılı ve muaf olmayan derslerin 1–5 ağırlıkları üzerinden hesaplanır. Yayımlanmamış gerekli dersin kapsamı 0'dır; puana dahil edilmez. Ders sayıları da döner: `expected_courses`, `published_courses`, `complete_courses`. Bu sayıların anlamı arayüzde yazılıdır.

Örnek: yalnızca vize girilmişse LO1 puanı 90, kapsamı 0.6'dır. Bu sonuç “LO1 başarı 90, verinin %60'ı mevcut, geçici” olarak gösterilir. Öğrenciye yayımlanan geçici sonuç ile yayımlanmamış öğretmen taslağı ayrıdır.

## Yayımlama ve sürümleme

1. Öğretim elemanı taslak konfigürasyonu ve notları düzenler. Her yazma açılışın `source_revision` değerini artırır.
2. Önizleme bir revision üzerinden hesaplanır; bağlı kaynaklar ve hatalar gösterilir.
3. `publish` isteği `expected_revision`, `stage=provisional|final`, gerekçe ve idempotency anahtarı taşır.
4. Backend kilit altında yetkiyi, revision'ı, matrisleri, puan aralıklarını ve final için tamlığı denetler.
5. Girdi, çıktı, hesaplama politikası, PO seti ve kaynak revision değişmez Publication içine kaydedilir; aktif yayın işaretçisi atomik değiştirilir.
6. Öğrenci API'si yalnızca aktif yayımlanmış snapshot'ı okur. Taslaktaki yeni notlar eski yayını değiştirmez; öğretmende “yayımlanmamış değişiklik” görünür.
7. Düzeltme yeni yayın oluşturur. Önceki yayın denetim izi olarak kalır; öğrenci geçmişini görme kapsamı ayrı karardır.

İlk yayından sonra puanın anlamını değiştiren `max_score`, LO kimliği, bağlantı ve PO seti değişikliği kilitlenir. Düzeltme için bölüm yöneticisinin gerekçeli `reopen` işlemi gerekir. Eski yayın korunur, taslak yeniden düzenlenir ve etkisi önizlenir. Not düzeltmesi de gerekçeli ve yeni yayınlıdır.

Silinen geçmiş ders/PO yayını bozmamalıdır. Kullanılmış akademik veriler `PROTECT` ve arşivleme yaklaşımıyla korunur. Şablon güncellemesi önceki ders açılışlarına otomatik yansımaz; yeni versiyon yeni kopyada kullanılır.

## Tekrar ders ve tarih kesiti

İlk politika `latest_final_attempt`: aynı öğrenci ve ders için seçilen tarih kesitindeki en son final yayını olan ders denemesi program profiline alınır. Daha yeni fakat tamamlanmamış deneme önceki final sonucu otomatik silmez. Eşit dönem durumunda deneme numarası ve açılış kimliğiyle deterministik sıralama yapılır.

Program profilinin varsayılan puanı final yayınlardan oluşur. Provisional yayın öğrencinin ders detayında görünür; programın resmi toplamına sessizce dahil edilmez. Program yanıtındaki `published_courses` bu profil hesabına dahil edilmiş final yayınlı ders sayısıdır. Kapsam, henüz final yayını olmayan gerekli dersleri de hesaba kattığından dönem devam ederken düşük olabilir.

`term_id` filtresi yalnızca o dönemi, `through_term_id` seçilen döneme kadar olan program profilini belirtir. İkisi birlikte gönderilirse 400. Farklı PO seti sürümlerini otomatik birleştirmeyin; seçilen set için sonuç veya açık uyumsuzluk bilgisi döndürün. Müfredat sürümleri arasında çapraz eşleme sonraki özelliktir.

## Şablon deneyimi

Öğretim elemanı boş şablon, onaylı kütüphane kopyası veya AI taslağıyla başlayabilir. Sihirbaz sırası: ders ve kredi → LO metinleri → değerlendirmeler ve genel not yüzdeleri → değerlendirme/LO matrisi → LO/PO matrisi → ders/PO 1–5 katkısı → doğrulama.

Her matrisin satır/sütun başlığı sabit, hücre yardım metni açık olur. “Eşit dağıt” yalnızca kullanıcı eylemiyle çalışır. Öğretmenin girdiği ağırlıklar kaydederken sessizce değiştirilmez. Yayın öncesinde bağlantısız LO, hiçbir dersten beslenmeyen PO, eksik not ve geçersiz toplam ayrı uyarılardır.

## Asgari hesaplama testleri

| Test | Beklenen |
| --- | --- |
| Hocanın 90/80 örneği | Yukarıdaki dört sonuç |
| 45/50 puan | Normalize 90 |
| LO ağırlığı toplamı 1.4 | Geçerli, payda 1.4 |
| Genel not ağırlığı toplamı 0.9 | Final yayını reddedilir |
| Bağlantı yok / payda 0 | Null, açıklayıcı durum; hata veya NaN yok |
| Eksik not / gerçek sıfır | Farklı sonuç ve kapsam |
| Muafiyet | Gerekçe, uygun payda değişimi |
| İki ders PO=80 ve 100, ağırlık=1 ve 3 | Program PO=95 |
| Taslak düzeltme | Öğrenci aktif yayını değişmez |
| Eşzamanlı iki revision | Biri başarılı; diğeri 409 |
| Tekrar ders | Aynı ders iki defa sayılmaz |
| Başka PO seti | Sessiz birleştirme yapılmaz |

Bu testler hesaplama sözleşmesinin parçasıdır. Rastgele sayılarla aralık koruma ve tüm ağırlıkları aynı katsayıyla çarpınca ortalamanın değişmemesi gibi özellik testleri de eklenebilir.
