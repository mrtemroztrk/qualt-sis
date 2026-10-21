# Poyraz Bingöl görev planı

## Rol ve teslim sorumluluğu

Değerlendirme ve not servisleri, deterministik LO/PO hesaplayıcısı, yayın snapshot'ları, CSV aktarımı, analitik/rapor ve AI syllabus iş akışının birincil sahibisin. Murat Emre backend reviewer ve yedeğindir. Mehmet Ali not ve analitik API'lerini, Onur Ege matris ve AI taslak API'lerini tüketir.

Kod alanların: `assessment`, `attainment`, `reporting`, `ai_assistance`. Hesaplayıcıyı Django modellerinden bağımsız tasarlaman ekibin erken paralel ilerlemesindeki en önemli adımdır.

## İş kartları

| ID | MVP | İş | Puan | Birincil kabul ölçütü |
| --- | ---: | --- | ---: | --- |
| P-001 | 0 | Hesaplayıcı DTO'ları ve hocanın örneği | 5 | Saf fonksiyonla 86.0, 82.9, 85.0, 82.9 |
| P-002 | 0 | Test fabrikaları ve sonuç API şeması | 3 | UI ve BE aynı fixture'ı kullanır |
| P-003 | 1 | Assessment ve mapping model/servis temeli | 3 | Alanlar ve scoped bağlantılar doğrulanır |
| P-004 | 1 | Not/sonuç fake servisleri ve erken API dilimi | 2 | Frontend veri ve hata biçimleriyle ilerler |
| P-005 | 2 | Tam hesaplama, kapsam ve snapshot üretimi | 8 | Eksik, sıfır, muaf, sıfır payda doğru |
| P-006 | 2 | Gradebook, atomik save ve yayın API'si | 5 | Revision, yetki ve yayın görünürlüğü |
| P-007 | 3 | CSV önizleme ve idempotent commit | 8 | Hatalı satır yazılmaz, tekrar çift kayıt yapmaz |
| P-008 | 3 | Analitik, tekrar ders, rapor ve indeksler | 5 | Filtreli ekran/rapor aynı sonucu verir |
| P-009 | 4 | Syllabus çıkarım şeması ve kaynaklı AI taslağı | 5 | Alanların kaynak sayfası ve doğrulaması |
| P-010 | 4 | AI kabul işlemi ve değerlendirme seti | 3 | İnsan onayı, revision ve kalite ölçümü |
| P-011 | 5 | Kanıta dayalı performans özeti | 3 | Sayılar yayın snapshot'ıyla eşleşir |
| P-012 | 5 | Kaydetmeyen not simülasyonu | 2 | Gerçek not ve yayın değişmez |
| P-013 | 6 | Veri tutarlılığı, yük ve restore doğrulaması | 5 | Yarış testi, ölçüm ve geri yükleme kontrolü |
| P-014 | 6 | Veri sistemi raporu ve demo fixture'ları | 3 | Tablo boyutları, formül kanıtı, tekrar üretilebilir demo |
| **Toplam** | | | **60** | |

## MVP 0 için adımlar

Önce [hesaplama kurallarını](03-HESAPLAMA-VE-AKADEMIK-KURALLAR.md) okuyup formülleri testle somutlaştır. Midterm/project örneğini yüksek hassasiyetle hesapla; ara yuvarlama yapma. ScoreInput, MappingInput, PolicyInput ve ScoreResult veri yapılarını yaz. LO/PO ağırlık toplamı için yanlış %100 kontrolü koyma.

Mehmet'e başarılı, eksik, hiç veri yok ve yasak erişim örneklerini; Onur'a geçersiz matris örneklerini ver. Murat'tan gerçek DB beklemeden saf fonksiyon testlerini çalıştır. PostgreSQL test fabrikaları geldiğinde aynı girdiyi API üzerinden de doğrula.

**Teslim:** hesap sözleşmesi, fixture, saf test ve Result şeması. **Reviewer:** Murat; Mehmet gösterim/null anlamını inceler.

## MVP 1 için adımlar

Assessment, AssessmentLOLink, LOPOMap ve CoursePOContribution modellerini sahiplen. Bağlantıların başka konfigürasyondaki LO/PO'ya gitmesini reddet. Değerlendirme maksimum puanı ve genel not ağırlığını ayrı alan tut. LO–PO kurallarını parametreleştir; akademik politika değişirse aynı veriyi yanlış anlamla yorumlama.

Mehmet'in gradebook'unu engellememek için sahte veriyle çalışan örnek servis ve şema hazırla. Onur'un validate isteği için hatanın hücre yolunu döndür: örneğin `assessment_lo_links.2.weight`. Formun hangi hücreyi işaretleyeceği anlaşılır olsun.

## MVP 2 için adımlar

Hesap motoruna normalizasyon, missing/excused ve coverage ekle. Score durumlarını tek enum yap; backend ve frontend farklı isimler üretmesin. Student result, course result ve program aggregate içindeki tüm değerlerin kaynakları izlenebilsin.

Gradebook listesi, bulk kaydetme ve publish iş akışını kur. Murat'ın açılış kilidi/revision protokolünü kullan. Grade yazma ve yayın oluşturma ayrı işlemdir: kaydetme öğrencinin gördüğünü otomatik değiştirmez. Snapshot girdilerini ve policy sürümünü sakla; result'ı aynı girdiden yeniden üretilebilir kıl.

**Mehmet ile kabul:** 50 satırlı çizelgede birkaç hücre düzenle → save → yayın önizle → publish → öğrenci görünümü. Başka öğretmen, başka öğrenci, geçersiz puan ve eşzamanlı save denemeleri reddedilmeli.

## MVP 3 için adımlar

CSV dosyasını önce salt doğrulama/önizleme olarak işle. Öğrenci numarası birden fazla veya sıfır eşleşiyorsa bunu açık hata yap; yanlış kişiye not yazma. Önizleme hash'i, offering revision ve batch sahibi commit'te tekrar kontrol edilir. Bir dosyadaki yinelenen hücreler sessizce son satır kazanacak şekilde işlenmez.

Analitik sorgusunu yayımlanmış sonuçlardan oluştur. Ortalama yanında öğrenci sayısı, eksik kapsam, dönem ve PO seti ver. Kimin dahil edildiğini açıklayan filtre metadatası ekle. Tekrar dersi seçimini ve tarih kesitini merkezi serviste uygula; CSV export ayrı formül yazmasın.

Sorgu sürelerini sentetik veriyle ölç; önce `select_related/prefetch_related`, uygun B-tree/unique indeks ve sorgu azaltma kullan. Materialized view, partition veya replica ancak kanıtlı ihtiyaç varsa eklenir. “Ölçeklenebilir” iddiası yerine veri büyüklüğü, donanım ve ölçülen sonucu raporla.

## MVP 4 için adımlar

Murat'ın provider portuna karşı AI çıkarım şemasını tasarla: ders adı/kodu, kredi/AKTS, LO listesi, değerlendirme adları/yüzdeleri, kaynak kanıtları. Dosyada olmayan bağlantıyı “çıkarıldı” diye sunma; çıkarım ile öneriyi ayrı alanlarda tut. Resmi PO kimliklerini yalnız sunulan katalogdan seçtir.

AIProposal düzenleme/kabul servislerini geliştir. Kullanıcı taslağı değiştirebilir; kabulden önce tüm akademik validator'lar ve revision denetimi yeniden çalışır. Varsayılan hiçbir öneri yayımlanmış not veya resmi sonucu değiştirmez.

Değerlendirme setinde alan doğruluğunu, kaynağın doğru sayfaya işaret etmesini, gereksiz/uydurulmuş alan sayısını ve insan düzeltme ihtiyacını ölç. Provider kapalı/bozuk JSON/zaman aşımı durumlarını fake adapter ile test et. Kanıtı olmayan alanı düşük güvenle işaretlemek veya boş bırakmak doğru davranıştır.

## MVP 5 için adımlar

Performans özeti sadece seçilen yayın snapshot'larını tüketir. Sayısal bulguları önce backend çıkarır; AI bu bulguları açıklayan sınırlı metin üretir. Akademik başarısızlık kararı veya kişilik çıkarımı yaptırılmaz. Her yorum ilgili PO ve yayına bağlanır.

Simülasyon aynı hesap motoruna farklı geçici not girdileri verir. Yazma servisini çağırmaz, Publication oluşturmaz. Öğrencinin yalnız kendi kayıtları üzerinde çalıştığı ve orijinal verinin değişmediği testle kanıtlanır.

## MVP 6 için adımlar

Transaction yarışını gerçek PostgreSQL bağlantılarıyla test et; sıradan tek-thread unit testiyle concurrency kanıtı sunduğunu iddia etme. Publication bütünlüğü, index planları ve rapor sorgularını yük altında dene. Murat'ın restore ettiği DB'de kayıt sayıları, FK bütünlüğü ve örnek PO hesabını karşılaştır.

Sentetik demo verisini yeniden üretilebilir seed komutuyla hazırla; gerçek öğrencilerin notlarını kullanma. CSE 321 raporu için tablo satır/sütun/raw boyutu, indeks/total boyutu ve normalize model gerekçesini gerçek ölçümden yaz.

## Senin süreç ve rapor kanıtın

- Hesaplama issue'su → formül testi → review → yayın demosu zinciri.
- Murat'ın auth, migration ve deployment PR'larına anlamlı inceleme.
- CSE 321 veri modeli ve tutarlılık bölümlerinin ilk taslağı; seçilen isolation level ve kilit nedenleri.
- CSE 311 için kendi görev, tahmin, test ve PR katkıları; gerçekte tamamlanan sprint puanları.
- AI kullanılabilirlik ölçümü; başarılı örnek kadar düzeltilmesi gereken örneklerin de kaydı.

## İlk çalışma oturumu

P-001 issue içeriğini hazırla; dört sayısal sonucu testle doğrula; Mehmet ile Result DTO'sunu, Onur ile matris hata yollarını sabitle. Murat ile katalog ORM modeline bağlanmadan kullanılacak DTO sınırında anlaş. Bu teslim, başka servislere ihtiyaç duymadan başlayabileceğin ilk bağımsız iş paketidir.
