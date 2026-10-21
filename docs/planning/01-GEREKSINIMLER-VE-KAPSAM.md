# Gereksinimler ve ürün kapsamı

## Kaynak belgeler

Bu dosyadaki G, B, R ve S işaretleri aşağıdaki yerel belgeleri ifade eder. Sayfalar PDF sayfa numarasıdır.

| Kod | Belge | Esas alınan bölümler |
| --- | --- | --- |
| G | [Team Project Guidelines](../references/README.md#project-guidelines) | s.2–10 ürün ve kurallar; s.11–18 takvim, sunum ve raporlar |
| B | [Team Project Brief](../references/README.md#project-brief) | s.5–20 hesaplama zinciri; s.21–22 tasarım soruları ve Django |
| R | [Report Format](../references/README.md#report-format) | s.1–2 CSE 311 raporunun altı bölümü |
| S | [CSE 311 Syllabus](../references/README.md#course-syllabus) | s.1–2 konu, sınav ve teslim takvimi |

G, daha ayrıntılı çalışma örneği ve iki dersin ayrı rapor formatını içerir. B'deki bazı görseller ara değerleri tam sayı gösterir; hesaplama için G s.6'daki formül ve hassas değerler kullanılır. Çelişen veya belirsiz akademik politika kesin kurum kuralı olarak sunulmaz.

## Zorunlu teslimlerin izlenebilirliği

| ID | Kaynaktaki beklenti | Uygulamadaki karşılık | Kanıt |
| --- | --- | --- | --- |
| RQ01 | Web tabanlı öğrenci PO puanı yönetimi; Acıbadem CSE pilotu, G s.2 | Öğrenciye özel PO profili ve ders detayları | Canlı öğretim elemanı → öğrenci demosu |
| RQ02 | Python ve Django, G s.3,9 | Django REST API ve ORM | Bağımlılık kilidi, backend kodu, çalışan container |
| RQ03 | Aynı dört kişilik ekip, aynı ürün, iki ders; G s.9,11 | Tek ürün backlog'u ve iki ayrı rapor | Üye listesi ve görev kayıtları |
| RQ04 | Kod GitHub deposunda, G s.9 | Issue, branch, PR, Actions ve release geçmişi | GitHub bağlantıları |
| RQ05 | Değerlendirme → LO → PO, G s.5–7 | Deterministik hesaplama servisi | Bilinen örneğin test sonucu ve açıklama ekranı |
| RQ06 | Bölümün 11 PO'su, G s.4 | Sürümlü PO seti; sayı kodda sabitlenmez | Pilot veri ve yönetim ekranı |
| RQ07 | Rol ve görevlerin tasarlanması, G s.8 | Öğrenci, öğretim elemanı, bölüm yöneticisi, sistem yöneticisi | Yetki matrisi ve olumsuz yetki testleri |
| RQ08 | CSE 311 süreç, backlog, efor, sprint ve velocity, G s.14,17 | GitHub Projects ve sprint kayıtları | Gerçek tamamlanan işlerden hız hesabı |
| RQ09 | CSE 321 mimari, sınıf ve veri diyagramları, G s.14,18 | Modül, deployment, sınıf ve ER diyagramları | Kodla güncel diyagramlar |
| RQ10 | İndeks, ölçeklenme, hata toleransı ve tutarlılık, G s.18 | Ölçülmüş sorgular, transaction örnekleri ve kurtarma planı | EXPLAIN, yarış testi, restore kaydı |
| RQ11 | CSE 311 GitHub Actions YAML ve gerçek run özeti, R s.2 | CI/CD pipeline | YAML dosyaları ve run bağlantıları |
| RQ12 | Getting Real bölüm referansları, R s.2 | Kapsam, arayüz ve iterasyon kararlarına bağlanan ilkeler | Karar → bölüm → PR/issue eşlemesi |
| RQ13 | Final demo ve basılı rapor, G s.15–18 | Her ders için altı bölümlü rapor | Demo akışı, baskı kontrolü |

AI kullanımına izin verilir; çalışan ve kullanıcıya yararlı özellik beklenir. Syllabus yükleyerek yapılandırma, toplu not aktarımı ve öğrenci performans raporu örnekleri G s.10'da verilmiştir. AI kullanmak tek başına teslim ölçütü değildir.

## Tarihler

| Tarih | Beklenti | Planlama sonucu |
| --- | --- | --- |
| 13 Ekim 2026 | Ekip ve GitHub kaydı | Plan tarihinden önce; kaydın yapılmış olduğunu ekip kontrol etmeli |
| 10 Kasım 2026 | CSE 311 ilk ara sınav | Önceki günlere yoğun entegrasyon bırakılmaz |
| 12 Kasım 2026 | CSE 321 sunum ve rapor | Veri modeli, mimari ve örnek hesaplama hazır |
| 17 Kasım 2026 | CSE 311 sunum ve rapor | Gerçek backlog, PR, sprint ve CI kayıtları hazır |
| 19 Kasım 2026 | CSE 321 ilk ara sınav | Kapasite azaltılır |
| 22 ve 24 Aralık 2026 | CSE 311 ve CSE 321 ikinci ara sınavları | Yeni özellik geliştirme bitmiş olur |
| 29–30 Aralık 2026 | Final demo ve basılı raporlar | Release adayı, yedek demo ve basılı iki rapor |

Tarihler G s.13 ve S s.1–2'den alınmıştır. Sonraki ders duyuruları değişiklik yaparsa takvim güncellenir.

## Ürün rolleri ve kapsamları

| İşlem | Öğrenci | Öğretim elemanı | Bölüm yöneticisi | Sistem yöneticisi |
| --- | --- | --- | --- | --- |
| Yayımlanan kendi not/LO/PO sonuçlarını okuma | Kendi | Atandığı ders öğrencileri | Kendi bölümündeki öğrenciler | Destek yetkisi açıkça verilmişse |
| Ders kataloğu, dönem, ders açılışı ve atama | Okuma | Atandığını okuma | Kendi bölümü için yazma | Kurulum ve hesap yönetimi |
| Syllabus, değerlendirme ve matris taslağı | Hayır | Atandığı ders | Bölümü içinde inceleme/onay | Akademik işlem yetkisi ayrıca gerekli |
| Not girişi ve yayımlama | Hayır | Atandığı ders | Gerekçeli yeniden açma/yetki devri | Varsayılan akademik yazma yok |
| PO seti ve başarı eşiği yönetimi | Hayır | Okuma | Bölümü içinde yazma | İlk kurulum |
| Bölüm analitiği | Hayır | Kendi dersinin analitiği | Kendi bölümü | Destek kapsamına göre |
| AI taslağı oluşturma ve kabul | Hayır | Atandığı ders için | Kendi bölümü için | Akademik yetkiye göre |

Bir kişi birden fazla rol taşıyabilir. Rol, bölüm ve ders ataması birlikte kontrol edilir. URL'deki öğrenci veya ders ID'si bir yetki sağlamaz. Taslak notları öğrenciye göndermemek backend sorumluluğudur. İlk pilot tek kurumdur; bölüm kapsamı veri modelinde açık tutulur, tam SaaS çok kiracılı altyapı bu teslimin parçası değildir.

## Kapsam öncelikleri

**Çekirdek:** giriş ve yetki, bölüm/PO/dönem/ders/açılış/kayıt, kredi ve AKTS, değerlendirmeler, iki ağırlık matrisi, not çizelgesi, hesaplama açıklaması, yayımlama, öğrencinin 11 PO profili, temel bölüm analitiği, audit kaydı, testler ve VPS hazırlığı.

**Öncelikli fark yaratan özellikler:** sürümlü ve kopyalanabilir syllabus şablonları; güvenli CSV not aktarımı; hangi notun hangi PO'yu nasıl etkilediğini gösteren ekran; eksik veri kapsamı; kaynak sayfasıyla AI syllabus taslağı; tekrar üretilebilir rapor.

**Zaman kalırsa:** not senaryosu simülasyonu, daha ayrıntılı karşılaştırmalar, AI ile kanıtlı performans özeti, erişilebilir dışa aktarma, gelişmiş toplu işlem.

**Sonraki dönem:** resmi OBS API entegrasyonu, SSO, mobil uygulama, ders kayıt/onay sistemi, ödeme, devamsızlık yönetimi, mesajlaşma, otomatik ders programı, kapsamlı transkript/GPA. Bunların hiçbiri PO çekirdeğini ve ekip süreci kanıtını geciktirmemeli.

Resmi OBS entegrasyonu için mevcut erişim veya API varsayılmaz. İlk veri giriş yolu yönetim ekranı ve doğrulanan CSV'dir. GPA ve harf notu eklemek için kurumun gerçek not dönüşümü ve tekrar dersi politikası gerekir.

## Öğretim elemanına götürülecek kararlar

1. G s.7'deki 1–5 ağırlık dersin PO'ya katkısı mı, doğrudan LO–PO bağlantısının ölçeği mi? Önerimiz: ders içi LO–PO bağı ayrı, dersler arası katkı 1–5. Hesaplayıcı bu iki katmanı ayırır.
2. Tekrar alınan ders için son yayımlanan deneme mi, tüm denemeler mi kullanılacak? Öneri: seçilen tarih kesitindeki en son final deneme; geçmiş korunur.
3. Kredi/AKTS program PO puanına ayrıca çarpılacak mı? Öneri: hayır; verilen 1–5 katkı ağırlığı yeterli. Kredi alanı saklanır.
4. Eksik not ve muafiyet politikası nedir? Öneri: eksik not sıfır yapılmaz, sonuç geçici ve kapsamıyla gösterilir; final yayımlama eksikte durur.
5. Resmi 11 PO'nun tam metni ve kullanılacak syllabus sürümü hangisi? Kısaltılmış slayt metinleri resmi tam metin yerine sunulmaz.

Bu sorular planın ilerlemesini engellemez. Yanıt gelene kadar kullanılan politika bir sürüm numarasıyla açıkça gösterilir; değişiklik hesaplama servisine ve test verisine yansıtılır.
