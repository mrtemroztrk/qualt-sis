# Ekip geliştirme ve mühendislik kanıtı

Ürünün çalışması kadar, değişikliklerin ekipçe kontrollü üretilmesi de teslimdir. Geliştirme geçmişi son hafta yeniden yazılmaz; gerçek karar, hata, review ve entegrasyon kayıtları iş yapılırken birikir.

## Organizasyon

İki teknik eş bulunur: backend'de Murat Emre–Poyraz; frontend'de Onur Ege–Mehmet Ali. Ayrıca uçtan uca eşleşmeler vardır: Murat–Onur akademik yapı/şablon, Poyraz–Mehmet not/analitik. AI'da Murat altyapıyı, Poyraz çıkarım davranışını, Onur taslak ekranını, Mehmet sonuç bildirimini teslim eder.

Ürün ve kapsam kararı dört kişiyle verilir. Toplantı kolaylaştırıcısı ve demo sunucusu haftalık döner; bu görev kişiyi diğer uzmanlık alanında kod yazmaya zorlamaz. Her modülde tek birincil sahip ve aynı alandan yedek bulunur. Sahibin sorumluluğu her işi tek başına yapmak değil, sınırı ve teslim kalitesini korumaktır.

## GitHub Projects düzeni

Durumlar: `Backlog → Ready → In Progress → In Review → Integration → Done`. Bekleyen işte `Blocked` etiketi ve engel nedeni/bağlantısı bulunur. Her kişide en fazla bir aktif ana iş, ayrıca bir review bulunması hedeflenir; iki kişiyi birden bloke eden entegrasyon işi önce çözülür.

Alanlar: issue ID, MVP, servis/özellik, owner, reviewer, priority, story points, sprint, dependency, Figma URL, contract PR, evidence URL. Board'a yalnızca başlık yazmak yetmez; kabul ölçütü bulunmayan iş Ready sayılmaz.

### Issue örneği

```text
Başlık: [MVP2][assessment] Notları atomik toplu kaydetme
İş ID: P-006
Kullanıcı ihtiyacı: Öğretim elemanı düzenlediği notları veri kaybetmeden kaydeder.
Owner: Poyraz Bingöl
Reviewer: Murat Emre Öztürk
Frontend tüketicisi: Mehmet Ali Altınbaş
Sözleşme: PATCH /api/v1/offerings/{id}/grades/bulk/
Bağımlılık: M-003 açılış ve kayıt DTO'su; fixture ile başlanabilir.
Kabul:
- Yalnız atanmış öğretmen yazabilir.
- Hatalı tek hücre varsa hiçbir satır değişmez.
- Eski expected_revision 409 döner.
- Missing ile graded=0 ayrılır.
Test/kanıt: API, transaction yarışı, gerçek UI E2E bağlantıları.
Kapsam dışı: CSV aktarımı P-007 işidir.
Tahmin: 5 puan; sprint planlamasında ekipçe tekrar değerlendirilir.
```

Çok büyük bir iş alt issue'lara bölünebilir. Üst işin puanı ve alt işlerin puanı velocity'ye iki kez yazılmaz. Bug, araştırma ve operasyon işleri de backlog'dadır; gizli iş yaratılmaz.

## Branch modeli

Trunk tabanlı çalışma: `main` her zaman entegre ve çalışır; feature branch'ler kısa ömürlüdür. Ayrı uzun ömürlü `frontend`, `backend`, `murat`, `poyraz` branch'leri açılmaz. Böyle branch'ler erken entegrasyonu geciktirir.

Adlandırma: `feat/123-grade-bulk-save`, `fix/207-csrf-login`, `docs/240-transaction-evidence`. Her branch gerçek issue'ya bağlıdır. Bir geliştirme dilimi tercihen 1–2 günlük küçük PR'lardan oluşur; büyük modül için tek dev PR beklenmez.

Yerel çalışma örneği; bunlar ileride ekipçe çalıştırılacak komutlardır:

```bash
git switch main
git pull --ff-only origin main
git switch -c feat/123-grade-bulk-save
git status
git add backend/apps/assessment
git commit -m "feat(assessment): save grade changes atomically"
git push -u origin feat/123-grade-bulk-save
```

Commit anlamlı bir değişiklik taşır. Gerçek kullanıcının Git kimliği kullanılır; ortak hesap veya tek kişinin herkes adına commit atması katkı izini bozar. Pair çalışmada gerçek katkı varsa `Co-authored-by` kullanılabilir. Şifre, `.env`, özel öğrenci verisi, yüklenmiş dosya ve veritabanı dump'ı commit edilmez.

## Pull request ve merge kuralları

1. Başlangıçta draft PR açılır; ilgili issue, Figma ve sözleşme bağlantısı eklenir.
2. PR açıklaması problem, değişen davranış, kabul ölçütleri ve test sonucunu içerir. UI işinde önce/sonra görseli; migration işinde veri etkisi bulunur.
3. Backend PR'ını diğer backend geliştiricisi; frontend PR'ını diğer frontend geliştiricisi inceler. API değişirse tüketici frontend geliştiricisi de sözleşmeyi inceler.
4. Reviewer kodu yalnız okumaz: kritik akışı çalıştırır; yetki, null, hata, eşzamanlılık ve test doğruluğunu kontrol eder. “LGTM” tek başına yeterli kanıt sayılmaz.
5. Geri bildirimden sonra yazar düzeltir, reviewer ilgili değişikliği tekrar görür. Çözümlenen konuşmalar ve başarılı zorunlu kontrollerden sonra PR merge edilir.
6. Varsayılan squash merge ile her PR `main` üzerinde okunabilir bir commit olur. Yazar ve varsa gerçek ortak yazarlar korunur. Çalışma kanıtı için PR/branch/Actions geçmişi ayrıca tutulur.
7. Branch silinir, issue ancak gerçek entegrasyon ve kabul ölçütü tamamlanınca Done'a geçer. Backend alt işi tamamlanmış olabilir; uçtan uca feature üst işi UI entegrasyonunu bekler.

`main` için force push ve doğrudan push kapatılır; en az bir bağımsız review, zorunlu CI ve çözülmüş konuşma istenir. Sözleşme/migration/güvenlik değişikliklerinde alan reviewer'ına ek tüketici/ilgili uzman incelemesi gerekir. İmkan varsa CODEOWNERS ve ruleset kullanılır; kişilerin gerçek GitHub kullanıcı adlarıyla tanımlanır. Depo planı gerekli korumayı desteklemiyorsa bu sınırlama kaydedilir ve PR kontrol listesiyle süreç uygulanır. [GitHub korumalı branch belgeleri](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)

## Conflict çözümü

Branch sık güncellenir. Paylaşılan branch geçmişi yeniden yazılmaz; `main` branch'i feature branch'e merge etmek anlaşılır başlangıç yöntemidir.

```bash
git fetch origin
git switch feat/123-grade-bulk-save
git merge origin/main
# Çakışan dosyaları incele, iki değişikliğin niyetini koruyarak düzenle.
git diff --check
# İlgili testleri ve entegrasyon kontrolünü çalıştır.
git add backend/apps/assessment
git commit
git push
```

Çakışmada sırayla: iki PR'ın amacı okunur → gerekiyorsa diğer yazarla kısa görüşülür → doğru birleşik davranış belirlenir → conflict işaretleri giderilir → testler çalışır → çözüm PR'a açıklanır. `ours/theirs` seçeneği bilinçsizce bütün dosyaya uygulanmaz.

Migration conflict'inde tablo geçmişi silinmez. İki migration'ın gerçekten paralel değişiklik olup olmadığı kontrol edilir; gerekiyorsa Django merge migration oluşturulur. Sadece yeni temiz veritabanında değil, önceki release şemasının üstünde de migration çalıştırılır. Lock dosyası conflict'inde elle satır birleştirmek yerine manifest kararları sonrası paket yöneticisiyle yeniden üretilir.

Gerçek bir conflict çıkarsa issue/PR, sebep, çözüm ve geçen test raporda gösterilir. Gerçek geliştirmede çıkmadıysa sırf puan için conflict yaratmayın; ekip bir eğitim branch'inde küçük bir alıştırma yapabilir ve bunu açıkça “eğitim çalışması” diye etiketler.

## Figma iş akışı

Onur ortak tasarım sisteminin sahibidir; Mehmet not/analitik deneyiminin eş sahibidir. İkisi de tasarım üretir ve birbirini inceler. Backend geliştiricileri ekranların veri anlamını ve API uygulanabilirliğini yorumlar; frontend tasarım görevlerini üstlenmez.

Figma dosyası sayfaları: `Foundations`, `Components`, `User Flows`, `Academic Admin`, `Gradebook`, `Student Profile`, `Analytics`, `AI Review`, `Prototype`, `Archive`.

İlk komponentler: renk/spacing/typography tokenları, buton, input, tablo, durum etiketi, doğrulama mesajı, boş ekran, spinner/skeleton, dialog, breadcrumb. Ortak ekran iskeleti ve responsive kırılımları önce uzlaşılır. Her sayfada loading, empty, success, validation, forbidden ve mümkünse conflict durumu tasarlanır.

Her kullanıcı hikâyesi ilgili Figma frame/prototip bağlantısı taşır. Review sırasında metinler, tab sırası, klavye kullanımı, hata konumu, null/veri yok anlamı, dar ekran ve grafiklerin tablo karşılığı değerlendirilir. Onaylanan tasarım sürümünün tarihi ve görseli issue'ya bağlanır. Ücretli Dev Mode başlangıç şartı değildir; paylaşılabilir frame, yorum ve ölçüler yeterlidir.

Tasarım teslimi yalnız güzel ekran görüntüsü değildir: bir akışın tıklanabilir prototipi, alan kuralları, bileşen listesi ve durumları bulunur. Kod bittiğinde uygulama ekranı Figma ile karşılaştırılır; gerekli fark gerekçesi kaydedilir.

## CI ve CD aşamaları

| Aşama | Kontroller | Ana sahip |
| --- | --- | --- |
| Her backend PR | Ruff, pytest, PostgreSQL integration, `makemigrations --check --dry-run`, migration, API şema farkı | Murat; Poyraz alan testleri |
| Her frontend PR | ESLint, TypeScript, Vitest, production build | Onur; Mehmet etkileşim testleri |
| Uçtan uca feature | Compose veya CI servisleriyle gerçek backend, Playwright | Mehmet; Onur kendi akışları |
| `main` merge | Aynı kontroller, Docker image build ve commit SHA ile etiket | Murat; frontend image Onur |
| Release | Staging deploy, smoke, production onay kapısı, backup, migration, deploy, smoke | Murat; Poyraz veri kontrolleri |

İlk günden küçük bir pipeline çalışır, sonraki kontroller ilgili özellik geldikçe eklenir. Aynı kontrolleri tekrar tekrar elle çalıştırmak yerine PR'daki koşullar güncel commit için doğrulanır. Untrusted PR'a production secret verilmez. Deployment yetkileri CI testlerinden ayrılır; korunan environment kullanılır.

Test raporları, ekran görüntüleri ve Playwright trace'leri workflow artifact'i olarak saklanır; öğrenci verisi/secret içermez. Önemli run bağlantıları ve gerekli çıktı kopyaları rapor kanıt klasörüne alınır; geçici artifact saklama süresine güvenilmez. [GitHub artifact belgeleri](https://docs.github.com/en/actions/using-workflows/storing-workflow-data-as-artifacts)

## Haftalık ritim ve adalet

- Haftanın başında 30–45 dakika: bir önceki tamamlanmış işler, kalan kapasite, öncelik ve Ready işlerin seçimi.
- Her çalışma gününde kısa asenkron durum: tamamlanan, sıradaki, engel. Herkesin her gün aynı saat çalışması gerekmez.
- Haftada iki kısa entegrasyon kontrolü: sözleşmeler, gerçek backend bağlantısı, çakışan dosyalar.
- Hafta sonunda 20–30 dakika: çalışan ürün demosu ve geriye dönük değerlendirme. Toplantı notu bir sayfayı geçmek zorunda değildir.

Velocity, sprintte **Done** olan işlerin önceden tahmin edilmiş puan toplamıdır. Biten işin puanı geçmişi güzelleştirmek için değiştirilmez. Tahmin değiştiyse tarihi ve sebebi kayıtlıdır; gelecek sprint planı düzeltilir. Commit sayısı, satır sayısı veya tek kişinin puanı performans yarışına dönüştürülmez.

İnceleme ve destek yükü kişi başı haftalık kaydedilir. Bir kişide bekleyen PR kuyruğu artıyorsa yeni iş almak yerine review yapılır. Backend işleri yalnız Murat–Poyraz, frontend işleri yalnız Onur–Mehmet arasında dengelenir. Bir alandaki gecikme diğer alanın mock/test/tasarım çalışmasını durdurmaz.

## Ready ve Done tanımı

**Ready:** kullanıcı amacı açık; kapsam sınırı ve kabul ölçütü yazılı; sahibi ve reviewer belli; bağımlılık tanımlı; gerekli Figma ve API sözleşmesi incelenmiş; örnek veri mevcut; iş bir sprintte bitebilecek büyüklükte.

**Done:** alan kodu ve testleri tamam; gerektiğinde migration var; review çözülmüş; CI yeşil; gerçek sistem entegrasyonu geçmiş; izin/hata/boş durumları çalışıyor; doküman ve sözleşme güncel; demo ve kanıt bağlantısı issue'da. Sadece kişinin bilgisayarında çalışması yeterli değildir.

## Herkesin gösterebilmesi gerekenler

Her üye kendi rolünde bir issue'yu anlatabilmeli, branch açıp push yapabilmeli, PR oluşturup review yanıtlayabilmeli, başka birinin PR'ını anlamlı inceleyebilmeli, conflict çözümünü açıklayabilmeli, başarısız CI logunu okuyabilmeli ve kendi modülünü Docker ortamında gösterebilmelidir. Bunlar rapora konacak yapay sayısal kota değil, ekipte gerçekten edinilecek yeteneklerdir. [GitHub pull request çalışma modeli](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests)
