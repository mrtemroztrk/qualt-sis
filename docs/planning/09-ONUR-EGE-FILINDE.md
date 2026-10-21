# Onur Ege Filinde görev planı

## Rol ve teslim sorumluluğu

Frontend temeli, ortak tasarım sistemi, giriş ve navigasyon, akademik yönetim, interaktif şablon/matris editörü ve AI syllabus inceleme ekranlarının birincil sahibisin. Mehmet Ali frontend reviewer ve yedeğindir. Murat Emre akademik/auth API'lerini; Poyraz matris doğrulama ve AI öneri davranışını sağlar.

Kod alanların: `frontend/src/app`, `shared/ui`, `shared/api-client`, `features/auth`, `academic-admin`, `template-builder`, `ai-review`; frontend build/container yapılandırması. Backend, migration veya sunucu iş kuralı geliştirme görevin yoktur. UI doğrulaması backend kuralının kullanıcıya erken açıklamasıdır.

## İş kartları

| ID | MVP | İş | Puan | Birincil kabul ölçütü |
| --- | ---: | --- | ---: | --- |
| O-001 | 0 | Figma temelleri ve React uygulama iskeleti | 5 | Ortak token/component ve responsive shell |
| O-002 | 0 | Auth UI, API istemcisi ve frontend CI | 3 | Session/CSRF ile gerçek login; typecheck/build |
| O-003 | 1 | Akademik yönetim ekranları | 8 | Dönem, ders, açılış, atama ve kayıt akışı |
| O-004 | 1 | PO/LO ve şablon kütüphanesi | 5 | Kopyalama, düzenleme, boş ve hata durumları |
| O-005 | 2 | Değerlendirme ve iki matris editörü | 5 | %100 kuralı doğru yerde uygulanır |
| O-006 | 2 | Save/validate/revision entegrasyonu | 3 | 409'da taslak korunur; gerçek API akışı |
| O-007 | 3 | Sürüm/reopen ve audit kullanıcı akışı | 3 | Gerekçe, geçmiş sürüm ve değişiklik görünümü |
| O-008 | 3 | Yönetim tabloları ve erişilebilirlik düzeltmeleri | 2 | Pagination, arama, klavye, dar ekran |
| O-009 | 4 | Syllabus yükleme ve job durumları | 8 | Yükleme/ilerleme/hata/manuel alternatif |
| O-010 | 4 | Kaynaklı AI taslağı inceleme ve kabul | 5 | Alan bazında düzeltme, kaynak, açık uygulama |
| O-011 | 5 | Figma kullanılabilirlik ve tasarım tutarlılığı | 3 | Test gözlemlerinden somut düzeltmeler |
| O-012 | 5 | Şablon kalite uyarıları ve son UX iyileştirmeleri | 2 | Boş PO/LO bağlantı uyarısı anlaşılır |
| O-013 | 6 | Frontend production build ve container | 5 | SPA rotaları, cache, API yolu, mock kapalı |
| O-014 | 6 | Arayüz doğrulama ve rapor/demo katkısı | 3 | Figma–uygulama karşılaştırması ve kanıt |
| **Toplam** | | | **60** | |

## MVP 0 için adımlar

Mehmet ile Figma'da renk, yazı, aralık, input, tablo, hata ve durum etiketi kararlarını al. İlk akışları tıklanabilir yap: login → öğretmen dersleri → şablon; yönetici → açılış oluşturma. Menüdeki roller ve ekran erişimi `/auth/me/` yetenekleriyle eşleşsin.

React/TypeScript uygulamasında router, Query provider, tema, error boundary ve API istemcisini kur. API istemcisi credential, CSRF ve standart error dönüşümünü tek yerde yönetsin. Ortak üretilmiş tipleri Mehmet ile paylaş. Frontend CI lint, typecheck, unit test ve production build çalıştırsın.

**Kabul:** gerçek login/logout çalışır; oturum bitmesi, CSRF hatası, loading ve yetkisiz durum kullanıcıyı kilitlemez. Üretim bundle'ına secret veya mock verisi konmaz. **Reviewer:** Mehmet; Murat auth sözleşmesini inceler.

## MVP 1 için adımlar

Akademik yönetimi aynı anda tek dev form olarak yapma. Liste/detay/form akışları sırayla: dönem → ders kataloğu → ders açılışı → öğretmen atama → öğrenci kaydı. Kredi ve AKTS alanları ayrı görünür; aynı dersin farklı dönemi ayrı kaynak olur.

Şablon kütüphanesinde arama, sürüm bilgisi, önizleme ve “bu derse kopyala” akışı hazırla. PO seti ile LO editörü aynı kavrammış gibi tasarlanmaz: PO bölüme, LO ders konfigürasyonuna aittir. Kullanıcı sonradan kopyanın hangi sürümden geldiğini görebilsin.

Murat'ın API'si hazır olmadan MSW ile success/empty/duplicate/forbidden senaryolarını uygula. API hazır olduğunda mock'u kapatıp aynı ekranı bağla. Kullanıcı yetkisi olmayan düğmeyi görmese de 403 yanıtını ayrıca ele al.

## MVP 2 için adımlar

Sihirbazı ders bilgisi → LO → değerlendirme → assessment/LO → LO/PO → ders/PO katkısı → doğrulama olarak kur. Genel not ağırlıklarının toplamını göster; matrislerde her satır/sütun toplamını zorunlu %100 yapma. 1–5 katkı için ayrı ölçek ve yardım metni kullan.

Matris hücrelerinde klavye gezinmesi, görünür odak, sayısal giriş ve hücreye bağlı hata mesajı olsun. Silinen LO/değerlendirmenin hangi bağlantıları etkilediğini önce göster. Kaydetmeden önce lokal hataları işaretle, sonra server validate sonuçlarını alan yollarıyla eşleştir.

Kaydetme sırasında ilerleme göster; çift tıklamayla birden çok istek oluşturma. 409'da kullanıcı değişikliklerini silme. Güncel sürümü ve eldeki taslağı karşılaştırarak tekrar düzenleme sun; sunucu verisini otomatik ezme. Gerçek revision akışını Murat, Poyraz ve Mehmet ile entegrasyon demosunda dene.

## MVP 3 için adımlar

Yayımlanmış konfigürasyonda hangi alanın kilitli olduğunu görünür kıl. Yönetici reopen yaparken gerekçeyi zorunlu al; geçmiş yayının korunacağını açık metinle anlat. Audit görünümünde aktör, zaman, işlem ve gerekçe göster; teknik diff kullanıcıya anlaşılır özetle sunulur.

Yönetim tablolarına sunucu pagination/arama ekle. Birden fazla sayfadaki seçimi sessizce kaybetme veya kullanıcıya tüm sayfalar seçilmiş hissi verme. Dar ekranda tabloların yatay kaydırması ve etiketleri kullanılabilir kalsın; yalnız masaüstünde güzel görünmesi yeterli değildir.

## MVP 4 için adımlar

Syllabus upload ekranında kabul edilen PDF sınırını açık göster. Dosya boyutu, desteklenmeyen dosya, parsing hatası, kuyruk bekleme, provider timeout ve iptal/yeniden deneme durumlarını tasarla. Aynı dosyanın yüklenmesi ile AI işleminin tamamlanması ayrı aşamalardır.

Taslak ekranında sol tarafta kaynak sayfa/metin, sağda çıkarılan alanlar veya uygun responsive karşılığı bulunur. `extracted` bilgi ile modelin `suggested` bağlantısını görsel/metinsel olarak ayır. Güven skoru varsa doğrulanmış olasılık gibi sunma; kaynak kanıtı daha önemlidir.

Kullanıcı alanları düzenler, doğrulama hatalarını görür, kabul edilecek değişikliklerin özetini inceler ve açık “Taslağa uygula” işlemi yapar. Bu düğme not yayımlamaz. Arka planda konfigürasyon değiştiyse 409 akışına dönülür. Başarısız AI'dan manuel şablona geçiş bir çıkmaz ekran olmamalıdır.

## MVP 5 için adımlar

Ekibin dışından mümkünse birkaç gönüllüyle sentetik veri üzerinde kısa görev testi yap: ders oluştur, şablon kopyala, yanlış ağırlığı düzelt, AI alanını onayla. Tamamlanma, takılma ve hata noktalarını kaydet; sonuçları “kullanıcılar sevdi” gibi ölçüsüz ifadelerle sunma.

Mehmet ile spacing, metin, tablo, hata ve durum bileşeni farklılıklarını gider. Renk tek anlam taşıyıcısı olmasın; ikon/metin desteği ver. PO/LO bağlantı boşluklarını kullanıcıya düzeltilebilir görev olarak göster.

## MVP 6 için adımlar

Frontend Docker build'ini çok aşamalı kur; üretimde geliştirme sunucusu çalıştırma. Caddy'nin servis edeceği statik build'i, SPA deep link fallback'ini, `/api` yönlendirmesini ve asset cache davranışını Murat ile doğrula. `index.html` güncellenirken eski asset referansları bozulmasın. MSW üretimde devre dışı olsun.

Başlıca ekranları temiz tarayıcıda, dar ekranda ve klavyeyle kontrol et. Figma prototipi ile gerçek ürünün temel akışlarını yan yana göster. Kullanılmayan deneysel ekranlar menüde kalmasın. Mehmet'in E2E akışlarına kendi özelliklerinin seçici ve test desteğini ver.

## Senin süreç ve rapor kanıtın

- Figma tasarım sistemi, prototip, review yorumları ve tasarımın kodla karşılığı.
- Kendi issue/branch/PR'ların; Mehmet'in UI PR'larına anlamlı review.
- CSE 311 raporunda backlog, Figma iş akışı ve arayüz kararlarının Getting Real bağlantıları için ilk taslak.
- Frontend CI/build ve production container kanıtı; gerçek API ile çalışan akademik akış demosu.
- CSE 321 mimari diyagramına frontend/API sınırı ve kullanılan response şekillerinin katkısı.

## İlk çalışma oturumu

Mehmet ile ortak tasarım tokenlarını ve özellik klasörü sınırlarını belirle. Murat ile auth sözleşmesini kesinleştir. O-001/O-002'yi küçük PR dilimlerine ayır; Figma prototipi ve API istemcisini diğer frontend ekranlarının beklemeyeceği şekilde erken teslim et.
