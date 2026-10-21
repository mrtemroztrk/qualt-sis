# Mehmet Ali Altınbaş görev planı

## Rol ve teslim sorumluluğu

Öğretim elemanı not çizelgesi, öğrenci not/LO/PO profili, bölüm analitiği, CSV ve rapor kullanıcı akışları, simülasyon ekranı ve frontend uçtan uca testlerinin birincil sahibisin. Onur Ege frontend reviewer ve yedeğindir. Poyraz hesaplama/not/analitik, Murat kayıt ve job altyapısı API'lerini sağlar.

Kod alanların: `features/gradebook`, `student-profile`, `analytics`, ilgili `mocks` ve `e2e` senaryoları. Figma'da not ve analitik sayfalarının sahibisin. Görevin backend yazmak veya bütün ekibin testlerini tek başına yapmak değildir; herkes kendi alanını test eder, sen E2E altyapısını ve bu kullanıcı akışlarını sahiplenirsin.

## İş kartları

| ID | MVP | İş | Puan | Birincil kabul ölçütü |
| --- | ---: | --- | ---: | --- |
| A-001 | 0 | Not/öğrenci Figma akışı ve mock senaryolar | 5 | Veri yok, hata, eksik not ve dolu ekranlar |
| A-002 | 0 | Test altyapısı ve temel tablo/grafik bileşenleri | 3 | Vitest/Playwright örneği; erişilebilir veri tablosu |
| A-003 | 1 | Öğretmen ders listesi ve gradebook iskeleti | 3 | Kayıt/değerlendirme kimliğiyle doğru satır/hücre |
| A-004 | 1 | Öğrenci kayıt listesi ve profil iskeleti | 2 | Öğrenci yalnız kendi derslerini görür |
| A-005 | 2 | Not girişi, bulk save, önizleme ve yayın | 8 | Klavye, doğrulama, 409 ve yayın ayrımı |
| A-006 | 2 | LO/PO profili ve hesap açıklaması | 5 | Null/sıfır/kapsam ayrımı, gerçek yayın sonucu |
| A-007 | 3 | CSV önizleme/commit ve rapor indirme | 5 | Hatalı satır ve yinelenen işlem yönetimi |
| A-008 | 3 | Ders/bölüm analitiği ve filtreler | 3 | Grafik, tablo, örneklem ve dönem tutarlılığı |
| A-009 | 4 | Ortak job/rapor durum bileşeni | 5 | Polling durur, hata/timeout/tekrar anlaşılır |
| A-010 | 4 | AI akışının frontend/E2E doğrulaması | 3 | Kabul sonrası gerçek şablon/not ekranı uyumlu |
| A-011 | 5 | Not senaryosu ve karşılaştırma ekranı | 5 | Kaydetmeden önce/sonra sonuç, gerçek veriden ayrım |
| A-012 | 5 | Kanıtlı performans özeti ve grafik erişilebilirliği | 5 | Kaynak bağlantısı ve sayısal tablo eşleşmesi |
| A-013 | 6 | Gerçek sistem E2E ve browser regresyonu | 5 | Rol, CSV, yayın, yenileme, doğrudan rota |
| A-014 | 6 | Demo, kullanıcı rehberi ve rapor kanıtları | 3 | Tekrarlanabilir kullanıcı senaryosu ve katkı kayıtları |
| **Toplam** | | | **60** | |

## MVP 0 için adımlar

Figma'da öğretmenin not girdiği, öğrencinin sonuç gördüğü ve yöneticinin PO dağılımını incelediği akışları çiz. Onur'un ortak tokenlarını kullan; ikinci bir görsel sistem kurma. Sayısal ekranda boş, missing, sıfır, muaf ve tam veri durumlarının tasarımları özellikle bulunmalı.

Poyraz'ın Result DTO'sundan MSW fixture'ları hazırla. UI testlerinin her defasında farklı sayılar üretmemesi için deterministik örnek veriler kullan. Vitest/Testing Library ve Playwright'ın bir başlangıç senaryosunu kur; gerçek backend senaryosu daha sonra ayrı etiketle çalışsın.

**Teslim:** not/PO prototipi, örnek JSON'lar, temel tablo/grafik bileşeni ve çalışan test komutu. **Reviewer:** Onur; Poyraz verinin anlamını inceler.

## MVP 1 için adımlar

Öğretmen ders listesini rol ve atama kapsamıyla bağla. Gradebook satırı enrollment, sütunu assessment kimliği taşır; öğrenci ismine göre eşleştirme yapılmaz. Loading, boş kayıt listesi ve henüz değerlendirme yok durumlarında sonraki eylem net olsun.

Öğrenci ders listesinde dönem, ders kodu ve yayın durumu göster. Sonuç yoksa boş grafiği sıfır başarı gibi çizme. Backend tamamlanmadan aynı şekilli mock verilerle route ve filtre akışını bitir.

## MVP 2 için adımlar

Not çizelgesinde hücre düzenleme, tab/enter ile gezinme, dirty state ve kaydedilmeyen değişiklik uyarısı kur. Puan maksimumunu görünür yap. Yerel sayı girişini API decimal string biçimine bilinçli çevir; `82,5` girdisi yanlışlıkla 825 olmasın. İlk sürümde tabloya gelişmiş Excel özellikleri eklemek yerine güvenilir klavye ve save akışını tamamla.

Toplu save yalnız değişen hücreleri göndersin. Hataları satır/hücrede göster; kaydetme sırasında kullanıcı girdisini kaybetme. Revision conflict'te güncel sunucu değeriyle kullanıcının değeri karşılaştırılabilsin. Toast tek başına hangi hücrenin yanlış olduğunu anlatmaya yetmez.

Kaydetme, önizleme ve yayımlama üç ayrı eylem olsun. Kullanıcı final yayın için eksik not kaldığını görsün. Yayın sonrası öğrenci görünümüne geçip gerçek sonuçları kontrol et. Formülü frontend'de ikinci kez otoriter olarak hesaplamak yerine backend açıklamasını kullan.

PO ekranında 11 çıktı için bar/radar görünümünün yanında okunabilir tablo sağla. Score, coverage, status, ders katkısı ve yayın zamanı ayrı alanlardır. Öğrenci bir PO'yu açınca ders → LO → değerlendirme zincirini takip edebilsin.

## MVP 3 için adımlar

CSV şablonunu indir → dosya seç → önizleme → hataları düzelt → değişiklik özetini onayla → commit akışını kur. Sunucu hatasının satır numarasını dosyayla aynı sayım kuralında göster. Hatalı dosyaya rağmen başarı bildirimi verme. İkinci commit isteğinin aynı sonucu dönmesi UI'de çift işlem gibi görünmesin.

Analitik ekranında dönem/PO seti/derse göre filtreyi URL query state'inde tut; yenileyince bağlam korunur. Bir filtre değiştiğinde tüm kartlar aynı yeni sorgu kapsamına geçsin; önceki veriyle yeni başlık karışmasın. Ortalama yanında örneklem ve eksik veri göster; öğrencilerin sayısal puanı tek başına kesin akademik değerlendirme gibi sunulmaz.

Rapor download yetki hatasını, boş veri ve hazırlanıyor durumunu ele al. İndirilen CSV ile ekrandaki filtre/yayın bilgisi aynı olmalı. Onur'un ortak empty/error bileşenlerini tekrar kullan.

## MVP 4 için adımlar

Onur'un AI upload ekranının kullanacağı ortak JobStatus bileşenini sahiplen. Job ID ile polling, backoff, sekme gizleme davranışı ve terminal durumda durmayı tek yerde çöz. Rapor hazırlama da aynı bileşeni kullanabilsin. Backend hatasını kullanıcıya anlamlı next action olarak göster.

Onur'un AI review ekranını frontend açısından incele: kaynak gösterimi, düzenleme, kabul özeti ve 409 akışı. E2E'de fixture/fake provider ile AI taslağı kabul edildikten sonra gerçek şablon ve not ekranının doğru alanları gördüğünü kanıtla. Provider çıktısı değişken olduğu için her PR testinde ücretli canlı model çağırma.

## MVP 5 için adımlar

Senaryo ekranında varsayımsal notları açıkça etiketle. Önce/sonra PO değişimini göster; öğrenci gerçek sonucu değiştirdiğini sanmasın. “Sıfırla” ile yayın değerlerine dönsün. Slider veya input sonucu simülasyon endpointine gönderirken debounce uygula, eski isteğin geç gelen yanıtı yeni sonucu ezmesin.

AI performans özetindeki her sayısal bulgu kaynak PO/yayın detayına gidebilsin. Metin üretilemezse normal sayısal profil çalışmaya devam etsin. Grafiklere metinsel özet, klavye erişimi ve veri tablosu ekle; yalnız renkle iyi/kötü sınıflandırma yapma.

## MVP 6 için adımlar

Gerçek backend/PostgreSQL üzerinde rol bazlı Playwright senaryolarını tamamla: öğretmen not girişi ve yayın, öğrenci yalnız kendi sonuçları, yönetici bölüm analitiği, CSV hatası, oturum sonlanması, doğrudan rota açma ve sayfa yenileme.

Onur'la browser ve dar ekran kontrolünü paylaş. Yalnız MSW testinin geçtiği akış varsa release adayında açık eksik olarak kaydet. Testlerde veri kurulumu deterministik olsun; başarısızlıkta screenshot/trace al ve ilgili issue'ya bağla.

Final demo için kısa kullanıcı rehberi, hesap açıklaması ve 2–3 dakikalık öğrenci/öğretmen akışını hazırla. Canlı sistem erişilemezse aynı senaryonun yerel Docker kurulumu ve kayıtlı görüntüleri yedek olur; kayıt canlıymış gibi sunulmaz.

## Senin süreç ve rapor kanıtın

- Not/analitik Figma tasarımları, erişilebilirlik ve gerçek kullanıcı akışı incelemeleri.
- Kendi issue/branch/PR'ların; Onur'un frontend PR'larına review ve gerekli düzeltmeler.
- Gerçek API E2E raporu, screenshot/trace ve hata düzeltme issue'su bağlantıları.
- CSE 311 raporunda sprint/velocity tablosunun derlenmesi, katkı grafikleri ve test süreç kanıtının ilk taslağı; her kişi kendi verisini doğrular.
- CSE 321 için ekranlarda veri kapsamı, örneklem ve yayın tutarlılığının örnekleri; takım görev tablosu.

## İlk çalışma oturumu

Poyraz ile Result ve Gradebook DTO'sunu, Onur ile ortak tema/API istemcisini sabitle. A-001 için Figma akışını ve success/missing/zero/no_data mock setini hazırla. Hesap servisi bitmeden profil, not çizelgesi ve hata durumlarını geliştirmeye başlayabilirsin.
