# Murat Emre Öztürk görev planı

## Rol ve teslim sorumluluğu

Backend platformu, kimlik/yetki, akademik yapı, müfredat ve şablon servisleri, dosya/job/AI sağlayıcı altyapısı ile VPS dağıtımının birincil sahibisin. Poyraz backend reviewer ve yedeğindir. Onur Ege akademik API'lerin, Mehmet Ali öğrenci kayıt ve job sözleşmesinin frontend tüketicisidir.

Sahip olduğun kod alanları: `backend/config`, `identity`, `academics`, `curriculum`, `integrations`, `audit`, entegrasyon amaçlı `workflows`, backend Docker ve deployment betikleri. Bu alanlar ileride oluşturulacak proje yapısını ifade eder.

## İş kartları

| ID | MVP | İş | Puan | Birincil kabul ölçütü |
| --- | ---: | --- | ---: | --- |
| M-001 | 0 | Django/PostgreSQL temel yapı ve yerel Compose | 5 | Temiz kurulum, migration, health ve backend CI |
| M-002 | 0 | Session, CSRF, roller ve güvenli demo hesapları | 3 | Login/logout/me ve kapsam testleri |
| M-003 | 1 | Akademik katalog, açılış, atama ve kayıt | 8 | Ayrı dönem/şube, filtreli sorgu, unique kayıt |
| M-004 | 1 | PO seti, LO, şablon temeli ve hesap yönetimi | 5 | 11 PO pilotu, şablon kopyası, yetkili hesap oluşturma |
| M-005 | 2 | Konfigürasyon birleştirme ve revision protokolü | 5 | Modül servisleri tek atomik iş akışında |
| M-006 | 2 | Audit ve uçtan uca yetki sağlamlaştırma | 3 | Öğrenci taslak ve başka öğrenci verisini alamaz |
| M-007 | 3 | Gerekçeli reopen, yayın geçmişi entegrasyonu | 5 | Geçmiş yayın değişmeden yeni taslak açılır |
| M-008 | 3 | Akademik sorgu/indeks ve yönetim destekleri | 3 | Ölçülmüş sorgu, pagination, audit kapsamı |
| M-009 | 4 | Güvenli PDF, kalıcı job ve worker altyapısı | 5 | Timeout/yeniden başlatma sonrasında iş izlenebilir |
| M-010 | 4 | AI sağlayıcı adapter ve maliyet sınırları | 3 | Fake/gerçek adapter aynı arayüzü sağlar |
| M-011 | 5 | Rapor/job erişimi ve AI veri minimizasyonu | 3 | Başka kullanıcının dosyası/raporu indirilemez |
| M-012 | 5 | AI operasyon metrikleri ve hata davranışı | 2 | Kota/timeout ölçümü ve kontrollü kapatma |
| M-013 | 6 | Production Compose, HTTPS ve release akışı | 5 | Aynı imaj staging ve VPS'te çalışır |
| M-014 | 6 | Backup/restore, rollback ve teslim kanıtı | 5 | Geri yüklenmiş veriyle smoke ve runbook |
| **Toplam** | | | **60** | |

## MVP 0 için adımlar

Özel User modelini ilk migration'dan önce belirle. Development/test/production ayarlarını ayır; secret değerlerini ortamdan al. PostgreSQL'i yerelde ve CI'da aynı ana sürümle kullan. Gunicorn üretim girişi ve health uçlarını hazırla; ilk CI lint ve tek bir gerçek API testi çalıştırabilsin.

Onur ile `csrf/login/logout/me` şemasını kesinleştir. Session/CSRF davranışını gerçek tarayıcı isteğiyle birlikte dene. Roller ile bölüm üyeliğini ayır; öğretmenin ders atamasını ayrıca kontrol et. Demoda kullanılacak sentetik hesapları bir komutla üret; komut gerçek üretim verisini silmesin.

**Teslim:** ilk kurulum rehberi, lock dosyası, Compose, auth şeması, success/forbidden örnekleri ve CI bağlantısı. **Reviewer:** Poyraz; Onur sözleşmeyi inceler.

## MVP 1 için adımlar

Önce Department, Term, Course, CourseOffering, TeachingAssignment ve Enrollment ilişkilerini kur. Aynı katalog dersinin iki dönemde farklı öğretmen, kredi kopyası ve notları olabileceğini test et. Öğrenciyi doğrudan Course'a değil Offering'e kaydet.

Sonra sürümlü OutcomeSet ve ProgramOutcome, konfigürasyona bağlı LO ve şablon kopyalama servislerini kur. Şablon uygularken alan ID'lerini yeni açılışa yeniden üret; eski kaynak ilişkilerini yanlışlıkla paylaşma. Kullanılmış PO seti yeni sürüm olmadan değiştirilmez. Hesap yaratma/etkinlik yönetimini yalnız izinli yöneticilere aç.

**Onur'a verilecekler:** katalog ve detay örnekleri, filtre parametreleri, boş liste, duplicate code ve izin hataları. **Poyraz'a verilecekler:** `get_offering_context` DTO'su ve LO/PO configuration okuyucusu. Fixture'lar gerçek API bitmeden teslim edilir.

## MVP 2 için adımlar

Poyraz'ın assessment servisleriyle aggregate configuration iş akışını birleştir. Tek konfigürasyon PUT işlemi LO, assessment ve mapping değişikliklerini ya tamamen yapsın ya hiç yapmasın. Revision kontrolünü ortak açılış satırında uygula; farklı yazma yolları kilidi atlamasın.

Audit servisini kimlik, işlem, kaynak, sebep ve request ID ile hazırla. Tüm notların log'a dökülmesi yerine gerekli değişiklik özetini sakla; loglar gizli kullanıcı verisini yaymasın. Öğrenci result API'lerinin sadece yayın okuduğunu Poyraz'ın testleri üzerinden de gözden geçir.

**Kabul demosu:** Onur'un şablon kaydı ve Mehmet'in not kaydı aynı revision'ı yarışmalı kullanınca birisi 409 alır; veri karışmaz. **Reviewer:** Poyraz; iki frontend sahibi kendi akışını doğrular.

## MVP 3 için adımlar

Bölüm yöneticisinin gerekçeyle reopen yapmasını, eski yayınlar korunurken taslağın düzenlenmesini ve audit geçmişini sağla. Katalog/şablon arşivleme geçmiş sonuçları kırmamalı. Büyük listelerde gereksiz tüm kullanıcı verisini döndürme; sayfalama ve kapsamlı arama uygula.

Akademik sorgular için ölçüm verisi üret; JOIN ve filtrelerin indeks kullanımını Poyraz ile incele. Audit endpointi sınırlı alanları dönsün, bölüm dışı kayıtları sızdırmasın. CSE 321 için kendi tablolarının ilişki ve constraint açıklamalarını yaz.

## MVP 4 ve MVP 5 için adımlar

Dosyayı boyut, tür ve sayfa sınırıyla al; rastgele storage key altında özel sakla. Parsing'i kontrollü kaynakla worker'da yap. Job durumunu DB'de tut; kuyruk gönderimi başarısız olsa da pending iş yeniden yakalanabilsin. Bir job tekrar çalışırsa ikinci kez kabul/kayıt yapılmasın.

`AIProvider` arayüzü oluştur: timeout, retryable hata, invalid response, kota ve kapalı sağlayıcı durumlarını fake adapter ile üret. Secret tarayıcıya çıkmaz. Model/provider/prompt sürümü ve token/maliyet metadatası kaydedilir; gereksiz öğrenci kimlik bilgisi gönderilmez. Poyraz'a şemalı çıktı adapter'ı, Onur ve Mehmet'e job sözleşmesi ver.

MVP 5'te performans özeti için yalnız gerekli sayısal/anonimleştirilmiş veriyi aktar. Rapor indirme yetkisi ve dosya erişimini ayrı test et. Harici sağlayıcıyı devre dışı bıraktığında normal not ve yayın ekranlarının çalışmasını göster.

## MVP 6 için adımlar

Backend ve worker aynı sürümlü imajı kullansın. Caddy yönlendirmesi, HTTPS, iç ağ, kalıcı volume ve healthcheck'leri kur. Frontend imajını Onur teslim eder; sen onun production URL/env beklentisini dağıtıma bağlarsın.

Release sırası backup → migration → imaj güncelleme → smoke → izleme olmalı. Eski imaja dönüşün veritabanı migration'ını otomatik geri almadığını runbook'ta açıkla. Poyraz ile restore'u ayrı boş ortamda doğrula. `check --deploy`, başarısız deployment ve geri dönüş kanıtını kaydet.

## Senin süreç ve rapor kanıtın

- Kendi issue ve feature PR'ların; en az bir anlamlı Poyraz PR incelemesi ve geri bildirim sonrası değişiklik.
- CI/CD YAML dosyaları ve gerçek başarılı/başarısız run açıklamaları.
- Mimari kararı: modüler monolit, auth, deployment; gerekçe ve alternatiflerin kısa kaydı.
- CSE 311 raporunda branching ve CI/CD bölümlerinin ilk taslağı.
- CSE 321 raporunda deployment mimarisi, yedek/restore ve hata toleransının ilgili kısmı.
- Kendi 14 işinin issue/PR/test/kanıt eşlemesi. Raporlarda diğer kişilerin katkılarını onların kayıtlarıyla birleştir.

## İlk çalışma oturumu

M-001 issue taslağını açılmaya hazır hale getir; Poyraz ile DTO ve veri sınırını, Onur ile auth response'unu kesinleştir; kurulum komutlarını ve secret listesini yaz; küçük backend temel PR'ı üzerinde ilerle. Poyraz'ın hesaplayıcıyı geliştirmesi için bütün katalog API'sinin bitmesini bekletme: aynı oturumda fixture sözleşmesini ver.
