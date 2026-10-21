# Qualt proje ve ekip çalışma planı

21 Ekim 2026 tarihli plan. Hedef, Acıbadem CSE pilotu için öğrencinin değerlendirme notlarından öğrenme çıktısı (LO) ve program çıktısı (PO) başarısını hesaplayan, bu sonucun kaynağını açıklayan ve VPS üzerinde çalıştırılabilen bir sistem geliştirmektir. Ders, dönem, kredi, şablon ve not ekranları bu hedefi destekler.

Başarı iki parçadan oluşur: çalışan ürün ve ürünün dört kişilik bir mühendislik ekibi tarafından nasıl geliştirildiğinin kanıtı. Figma tasarımları, issue kayıtları, branch ve pull request geçmişi, kod incelemeleri, testler, GitHub Actions çalışmaları, Docker imajları ve veritabanı ölçümleri aynı teslim planının içindedir.

## Temel kararlar

- Backend ve AI: **Murat Emre Öztürk** ile **Poyraz Bingöl**.
- Frontend: **Onur Ege Filinde** ile **Mehmet Ali Altınbaş**. Backend geliştirme görevi bu iki kişiye verilmez.
- Mimari: ayrı geliştirilen ve test edilen Django uygulamalarından oluşan **modüler monolit**, özelliklere ayrılmış React frontend, ortak REST API sözleşmesi.
- Dağıtım: tek VPS üzerinde Docker Compose. Web, PostgreSQL ve gerektiğinde worker/Redis ayrı container olur. İş alanındaki her modülün ayrı container olması zorunlu değildir.
- Süreç: GitHub Issues ve Projects, kısa ömürlü feature branch'ler, pull request ile merge, korunan `main`, her sprint çalışan bütünleşik demo.
- Tasarım: Figma'da ortak tasarım sistemi ve tıklanabilir kullanıcı akışları; tasarım kararları ilgili issue ve PR'a bağlanır.
- İlk hedef: güvenilir not → LO → PO zinciri. AI, akademik puanın hesaplayıcısı olmaz; syllabus hazırlamayı ve raporlamayı destekler.

**Bu klasör bir planlama teslimidir.** Uygulama, CI, Docker veya Figma tasarımı henüz oluşturulmuş sayılmaz. Buradaki endpointler ve klasör ağaçları uygulanacak sözleşme taslaklarıdır. Belgeler ekip erişimi için `docs/ekip-ici-dokumanlar` branch’inde tutulur. Bu branch `main` ile birleştirilmez; ekip kendi görevlerini ve ortak sözleşmeleri bu branch üzerinden inceler. Uygulama geliştirme ve iş takibi kurulumu sonraki çalışma kapsamındadır.

## Hangi dosyayı kim okumalı

| Dosya | İçerik | Öncelikli okuyucu |
| --- | --- | --- |
| [01 Gereksinimler ve kapsam](01-GEREKSINIMLER-VE-KAPSAM.md) | Hocanın beklentileri, zorunlular, roller, açık kararlar | Herkes |
| [02 Modüler mimari](02-MODULER-MIMARI-VE-VERI-MODELI.md) | Stack, servis sınırları, bağımsız geliştirme, veri modeli | Herkes; özellikle backend |
| [03 Hesaplama kuralları](03-HESAPLAMA-VE-AKADEMIK-KURALLAR.md) | Not, LO, PO, ağırlık, eksik veri, sürümleme | Herkes |
| [04 API sözleşmeleri](04-API-SOZLESMELERI.md) | Endpointler, veri biçimleri, hata ve entegrasyon kuralları | Dört geliştirici |
| [05 MVP ve takvim](05-MVP-IS-PAKETLERI-VE-TAKVIM.md) | Sürümler, bağımlılıklar, demo ve kabul ölçütleri | Herkes |
| [06 Ekip geliştirme süreci](06-EKIP-GIT-FIGMA-VE-CI-SURECI.md) | Issue, branch, PR, review, conflict, Figma, CI kanıtları | Herkes |
| [07 Murat Emre görevleri](07-MURAT-EMRE-OZTURK.md) | Backend platformu, akademik yapı, AI altyapısı, dağıtım | Murat Emre |
| [08 Poyraz görevleri](08-POYRAZ-BINGOL.md) | Değerlendirme, hesaplama, analitik, AI iş akışları | Poyraz |
| [09 Onur Ege görevleri](09-ONUR-EGE-FILINDE.md) | Frontend temeli, akademik yönetim, şablon ve AI ekranları | Onur Ege |
| [10 Mehmet Ali görevleri](10-MEHMET-ALI-ALTINBAS.md) | Not çizelgesi, öğrenci profili, analitik, E2E | Mehmet Ali |
| [11 Kalite ve teslim](11-KALITE-VPS-VE-DERS-RAPORLARI.md) | Testler, VPS, yedek, rollback, iki dersin rapor kanıtları | Herkes |
| [12 Whiteboard backend haritası](12-WHITEBOARD-BACKEND-HARITASI.md) | Mevcut rol tahtasına eklenecek servisler ve kart örneği | Backend ekibi |

## İlk ortak oturumun sonucu

Yaklaşık 60–90 dakikalık ilk toplantıda herkes bu planın kapsamını kabul eder veya değişiklik önerir. Sonuç olarak MVP 0 ve MVP 1 backlog'u seçilir; API ve Figma sahipleri belirlenir; görev puanları ekipçe tekrar tahmin edilir; dersler arası PO ağırlıklandırmasıyla ilgili öğretim elemanına götürülecek soru kaydedilir.

İlk dikey akış şu olmalıdır: öğretim elemanı giriş yapar → kendisine atanmış ders açılışını görür → iki değerlendirme ve LO bağlantısını tanımlar → not girer → önizlemede PO hesabını açıklar → yayımlar → öğrenci kendi sonucunu görür. Bu akış tamamlanmadan geniş bir OBS özellik listesine dağılmayın.

## İş yükü dengesi

| Kişi | Ana alan | Planlanan göreli efor |
| --- | --- | ---: |
| Murat Emre Öztürk | Backend ve AI altyapısı | 60 puan |
| Poyraz Bingöl | Backend, hesaplama ve AI akışları | 60 puan |
| Onur Ege Filinde | Frontend ve tasarım sistemi | 60 puan |
| Mehmet Ali Altınbaş | Frontend ve analitik deneyimi | 60 puan |

Bu değerler ölçülmüş velocity veya saat taahhüdü değildir. Her kişide 14 başlangıç işi vardır; puanlar kod, kendi testleri, dokümantasyon ve entegrasyonu birlikte kapsayan ilk tahminlerdir. Öğrenme zorluğu ve review yükü ilk iki sprintte görünür olduğunda işler aynı uzmanlık alanındaki iki kişi arasında yeniden dağıtılır. Eşitliği commit veya satır sayısıyla ölçmeyin.

## Kaynakların kullanımı

Hocanın zorunlu gereksinimleri ile ekibin teknik tercihleri [gereksinim dosyasında](01-GEREKSINIMLER-VE-KAPSAM.md) ayrılmıştır. Figma, Docker, React ve seçilen test araçları gerekçeli ekip önerileridir; belgelerde bu araçların her biri için garanti bir ek puan yazmıyor. Değerlerini çalışan tasarım, tekrarlanabilir kurulum ve izlenebilir ekip süreciyle göstermelisiniz.
