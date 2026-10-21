# API sözleşmeleri ve bağımsız entegrasyon

Bu dosya uygulanacak API taslağıdır. MVP 0'da backend sahibi ve frontend tüketicisi seçilen dilimin OpenAPI şemasını birlikte kesinleştirir. Endpointin bu listede bulunması uygulanmış olduğu anlamına gelmez. Her iş paketi kendi OpenAPI, örnek JSON ve MSW senaryosunu kodundan önce teslim eder.

## Ortak kurallar

- Kök `/api/v1/`; Django ile uyumlu son `/` kullanılır. JSON alanları `snake_case`, kimlikler UUID, tarihler ISO 8601, zamanlar UTC gönderilir; UI Europe/Istanbul gösterir.
- Puan, oran, kredi ve AKTS ondalıkları JSON string olur: `"82.8571"`, `"0.6000"`, `"6.00"`. Eksik değer `null`; asla `0` veya boş string değildir.
- Tek kaynak yanıtı doğrudan nesne; liste yanıtı `{count, next, previous, results}`. Varsayılan sayfa 25, azami 100. İzinli `ordering` alanları endpoint şemasında listelenir.
- Hata `{error: {code, message, fields, request_id}}`. Frontend `message` metnini iş kuralı olarak parse etmez; `code` kullanır.
- Başarı: GET/PATCH/PUT 200, yaratma 201, job 202, logout 204. Doğrulama 400; erişim/CSRF 403; kapsam dışı kaynak 404; eski revision 409; büyük dosya 413; desteklenmeyen dosya 415; kota 429.
- SessionAuthentication varsayılanıyla oturumsuz korumalı istek de 403 dönebilir. Sözleşme `not_authenticated`, `permission_denied`, `csrf_failed` kodlarını ayırır. Login başarısızlığı 400 `invalid_credentials`, kullanıcı varlığını açıklamayan mesaj döner.
- Hatalı yöntem/format için 405/415, beklenmeyen sunucu hatasında izlenebilir `request_id` ile 500; traceback istemciye gönderilmez.
- Ders açılışına bağlı bütün yazmalar açılışın `expected_revision` değerini taşır. Katalog dersini PATCH etmek kendi kaynak revision'ını kullanır. Yeni kaynak yaratmada bu alan gerekmez. 409'da frontend güncel veriyi çeker, kullanıcının taslağını korur ve karşılaştırmalı çözüm sunar.
- Publish, import commit ve AI accept isteklerinde `Idempotency-Key` zorunludur. Aynı kullanıcı/endpoint/anahtar ve aynı payload önceki sonucu döndürür; aynı anahtar farklı payload ile 409. Kayıt en az 24 saat saklanır; işin kalıcı `committed/accepted` durumu daha sonra da tekrarlı uygulamayı engeller.
- Yetki kontrolleri liste, detay, nested ID, toplu işlem ve indirmelerde aynıdır. Listelerde filtre uygulanır; kapsam dışı detaya 404 döner. Rolü gizlemek yalnızca UI işidir, güvenlik sağlamaz.

```json
{
  "error": {
    "code": "revision_conflict",
    "message": "Ders verisi başka bir işlemle değişti.",
    "fields": {"expected_revision": ["Güncel revision: 18"]},
    "request_id": "572a854a-52a0-44df-ab56-6e676c8115aa"
  }
}
```

## Kimlik ve akademik yapı

Kısaltmalar: M=Murat Emre, P=Poyraz, O=Onur Ege, A=Mehmet Ali. Bütün listeler yetki kapsamıyla daraltılır.

| Endpoint | İstek / dönüş | Yetki | BE / FE | Aşama |
| --- | --- | --- | --- | --- |
| `GET /auth/csrf/` | `{csrf_token}` ve CSRF cookie | Herkes | M / O | 0 |
| `POST /auth/login/` | email, password → kullanıcı ve session cookie | Herkes, CSRF ve hız sınırı | M / O | 0 |
| `POST /auth/logout/` | Session kapatma, 204 | Oturum | M / O | 0 |
| `GET /auth/me/` | id, display_name, memberships, capabilities | Oturum | M / O | 0 |
| `GET /users/?role=&search=` | Kapsamlı hesap listesi | Bölüm yöneticisi | M / O | 1 |
| `POST /users/` | email, display_name, role, department_id | Yönetici; yetki yükseltme sınırı | M / O | 1 |
| `PATCH /users/{id}/` | is_active ve izinli profil alanları | Yönetici | M / O | 1 |
| `GET, POST /departments/` | code, name | Okuma oturum; yazma sistem yöneticisi | M / O | 1 |
| `GET, POST /terms/` | code, start_date, end_date | Okuma oturum; yazma bölüm yöneticisi | M / O | 1 |
| `GET, POST /courses/` | department_id, code, title, local_credit, ects | Kapsamlı okuma/yönetim | M / O | 1 |
| `GET, PATCH /courses/{id}/` | Ders detayı veya arşivleme | Kapsamlı yönetim | M / O | 1 |
| `GET, POST /offerings/` | course_id, term_id, section, instructor_ids | Kapsamlı okuma/yönetim | M / O | 1 |
| `GET, PATCH /offerings/{id}/` | Ders açılışı, atama, kredi kopyası, revision | Kapsamlı yönetim | M / O | 1 |
| `GET, POST /offerings/{id}/enrollments/` | student_ids → kayıtlar; toplu yaratma atomik | Atanmış öğretmen okur; yönetici yazar | M / O | 1 |
| `PATCH /offerings/{id}/enrollments/{enrollment_id}/` | status, expected_revision, reason | Bölüm yöneticisi | M / O | 1 |

İlk pilotta herkese açık kayıt yoktur. Kullanıcı yaratma bir davet/ilk şifre kurulum mekanizmasıyla tamamlanır; üretimde ortak veya sabit şifre dağıtılmaz. E-posta servisi kurulmamış demoda hesaplar güvenli yönetim komutuyla oluşturulur. Bu alternatif ve yönetici destekli şifre sıfırlama runbook'u M-004 kapsamındadır; herkese açık e-posta reset sistemi çekirdek teslimin parçası değildir.

## Müfredat ve şablonlar

| Endpoint | İstek / dönüş | Yetki | BE / FE | Aşama |
| --- | --- | --- | --- | --- |
| `GET, POST /outcome-sets/` | department_id, version, outcomes[] | Yönetici yazar; kapsamlı okuma | M / O | 1 |
| `GET /outcome-sets/{id}/` | Tam PO listesi, durum, sürüm | Kapsamlı okuma | M / O | 1 |
| `POST /outcome-sets/{id}/versions/` | Yeni sürüm kopyası; kullanılan set değişmez | Bölüm yöneticisi | M / O | 1 |
| `GET, POST /templates/` | title, course_id?, configuration | Öğretmen/yönetici | M / O | 1 |
| `GET /templates/{id}/` | Şablon ve mevcut sürümler | Kapsamlı okuma | M / O | 1 |
| `POST /templates/{id}/versions/` | Yeni değişmez template sürümü | Sahibi/yönetici | M / O | 1 |
| `POST /offerings/{id}/apply-template/` | template_version_id, expected_revision | Atanmış öğretmen/yönetici; boş taslak | M / O | 1 |
| `GET /offerings/{id}/configuration/` | Syllabus + değerlendirmeler + matrisler | Atanmış öğretmen/yönetici | M+P / O | 1–2 |
| `PUT /offerings/{id}/configuration/` | Bütün taslak, expected_revision | Atanmış öğretmen; atomik | M+P / O | 2 |
| `POST /offerings/{id}/configuration/validate/` | Kaydedilmemiş veya kayıtlı taslak → errors, warnings | Atanmış öğretmen | P / O | 2 |
| `POST /offerings/{id}/reopen/` | expected_revision, reason | Bölüm yöneticisi | M+P / O | 3 |

Konfigürasyon endpointi birleştirici iş akışıdır: curriculum kendi LO/şablon alanını, assessment kendi değerlendirme/matris alanını doğrular. HTTP endpointi ince bir `workflows` katmanında birleştirilir; bu katmanın veri tablosu olmaz. İki modülün birbirini çağıran yazma servisleriyle döngü oluşturulmaz. M entegrasyon sahibidir, P kendi public servisinden sorumludur.

```json
{
  "expected_revision": 7,
  "outcome_set_id": "10000000-0000-4000-8000-000000000001",
  "learning_outcomes": [
    {"id": "20000000-0000-4000-8000-000000000001", "code": "LO1", "description": "Apply software development practices."},
    {"id": "20000000-0000-4000-8000-000000000002", "code": "LO2", "description": "Work effectively in a software team."}
  ],
  "assessments": [
    {"id": "30000000-0000-4000-8000-000000000001", "code": "MIDTERM", "kind": "exam", "max_score": "100.00", "grade_weight": "0.4000"},
    {"id": "30000000-0000-4000-8000-000000000002", "code": "PROJECT", "kind": "project", "max_score": "100.00", "grade_weight": "0.6000"}
  ],
  "assessment_lo_links": [
    {"assessment_code": "MIDTERM", "lo_code": "LO1", "weight": "0.6000"},
    {"assessment_code": "PROJECT", "lo_code": "LO1", "weight": "0.4000"},
    {"assessment_code": "MIDTERM", "lo_code": "LO2", "weight": "0.4000"},
    {"assessment_code": "PROJECT", "lo_code": "LO2", "weight": "1.0000"}
  ],
  "lo_po_links": [
    {"lo_code": "LO1", "po_code": "PO1", "weight": "1.0000"},
    {"lo_code": "LO2", "po_code": "PO1", "weight": "0.5000"},
    {"lo_code": "LO2", "po_code": "PO2", "weight": "1.0000"}
  ],
  "course_po_contributions": [
    {"po_code": "PO1", "weight": 5},
    {"po_code": "PO2", "weight": 3}
  ]
}
```

Bu JSON örnek ders yapılandırmasıdır; genel not için 40/60 dağılımı ekip örneğidir, hocanın gerçek CSE 311 değerlendirme planı değildir. Gerçek syllabus'taki 25/25/10/40 ayrı şablon olarak girilir. Yeni LO/assessment için `id` atlanır; sunucu yaratır. Mevcut nesnede ID korunur. Linkler aynı konfigürasyon içinde benzersiz kodla çözülür, response tüm ID'leri döndürür. ID/kod çelişkisi 400; geçmiş notu olan nesneyi silme 409.

## Not, yayın ve sonuç endpointleri

| Endpoint | İstek / dönüş | Yetki | BE / FE | Aşama |
| --- | --- | --- | --- | --- |
| `GET /offerings/{id}/gradebook/?page=&search=` | assessments, öğrenci satırları, revision; sayfalı satırlar | Atanmış öğretmen | P / A | 2 |
| `PATCH /offerings/{id}/grades/bulk/` | expected_revision, changes[] → yeni revision, değişen hücreler | Atanmış öğretmen | P / A | 2 |
| `POST /offerings/{id}/preview/` | expected_revision, enrollment_id? → hesap ve doğrulama | Atanmış öğretmen | P / A | 2 |
| `POST /offerings/{id}/publish/` | expected_revision, stage, reason → Publication | Atanmış öğretmen | P / A | 2 |
| `GET /offerings/{id}/publications/` | Yayın sürümleri ve tarihleri | Atanmış öğretmen/yönetici | P / A | 3 |
| `GET /me/offerings/` | Öğrencinin kayıtları ve yayın durumu | Öğrenci | M / A | 2 |
| `GET /me/attainment/?through_term_id=&outcome_set_id=` | Yayımlanmış program PO profili | Öğrenci, kendi | P / A | 2–3 |
| `GET /me/offerings/{id}/results/` | Yayımlanmış notlar, LO, ders PO, açıklama | Kayıtlı öğrenci | P / A | 2 |
| `GET /students/{id}/attainment/` | Aynı result DTO; yetkili kapsam | Bölüm yöneticisi | P / A | 3 |
| `GET /offerings/{id}/analytics/` | LO/PO dağılımı, eksik veri, örneklem | Atanmış öğretmen/yönetici | P / A | 3 |
| `GET /departments/{id}/analytics/?term_id=&outcome_set_id=` | Bölüm PO dağılımı, kapsama | Bölüm yöneticisi | P / A | 3 |

`gradebook` yanıtı `{offering_id, revision, assessments, rows: {count,next,previous,results}}` biçimindedir. Her satır `enrollment_id`, `student:{id,display_name,student_number}`, `grades:[{assessment_id,state,raw_score}]` taşır. Hücre düzenleme öğrenci kimliğiyle değil kayıt ve değerlendirme kimliğiyle yapılır.

```json
{
  "expected_revision": 8,
  "changes": [
    {
      "enrollment_id": "40000000-0000-4000-8000-000000000001",
      "assessment_id": "30000000-0000-4000-8000-000000000001",
      "state": "graded",
      "raw_score": "90.00",
      "reason": "Initial entry"
    }
  ]
}
```

Bulk değişiklik üst sınırı başlangıçta 500 hücredir. Aynı hücrenin aynı payload'da tekrarı 400 döner. Başka derse ait enrollment/assessment 400 veya kapsam dışı 404; hiçbir hücre yazılmaz. Save sırasında yalnızca değişmiş hücreler gönderilir. Kullanıcı kaydetmediği veriyi sayfa değiştirirken kaybetmemelidir.

### Ortak sonuç nesnesi

```json
{
  "scope": "course",
  "publication_id": "50000000-0000-4000-8000-000000000001",
  "source_revision": 9,
  "policy_version": "attainment-v1",
  "outcome_set_id": "10000000-0000-4000-8000-000000000001",
  "stage": "final",
  "computed_at": "2026-11-06T12:00:00Z",
  "outcomes": [
    {
      "id": "60000000-0000-4000-8000-000000000001",
      "code": "PO1",
      "score": "84.9524",
      "coverage": "1.0000",
      "status": "complete",
      "contributions": [
        {"source_code": "LO1", "score": "86.0000", "weight": "1.0000"},
        {"source_code": "LO2", "score": "82.8571", "weight": "0.5000"}
      ]
    }
  ]
}
```

Örnekte tek PO gösterilmiştir. Gerçek profil seçilen setin bütün PO'larını döndürür; boş olanlarda `score:null` ve uygun status olur. Program scope'unda tek `publication_id` yerine `publication_ids`, `expected_courses`, `published_courses`, `complete_courses` bulunur. Hesap açıklaması raw input, normalize puan, ağırlık, pay ve paydaya kadar açılabilir. API kısaltılmış gösterim değerleriyle tekrar hesap yapmaz.

## İçe aktarma, AI ve dışa aktarma

| Endpoint | İşlev | Sahip BE / FE | Aşama |
| --- | --- | --- | --- |
| `GET /offerings/{id}/grade-import-template/` | İzinli değerlendirme kodlarıyla UTF-8 CSV şablonu | P / A | 3 |
| `POST /offerings/{id}/grade-imports/` | Multipart CSV → batch_id, satır hataları, önizleme | P / A | 3 |
| `POST /grade-imports/{id}/commit/` | expected_revision, preview_hash → atomik not yazma | P / A | 3 |
| `POST /files/` | Multipart syllabus PDF → file_id, güvenli metadata | M / O | 4 |
| `POST /ai/syllabus-proposals/` | file_id, offering_id → job_id; 202 | P+M / O | 4 |
| `GET /jobs/{id}/` | queued/running/succeeded/failed/cancelled, ilerleme, sonuç referansı | M / O+A | 4 |
| `POST /jobs/{id}/retry/` | Sahibi için yalnız failed ve retryable işi yeniden kuyruğa alma | M / O+A | 4 |
| `POST /jobs/{id}/cancel/` | Sahibi için best-effort iptal isteği; tamamlanmış kabulü geri almaz | M / O+A | 4 |
| `GET /ai/proposals/{id}/` | Alanlar, source_page, source_quote, doğrulama uyarıları | P / O | 4 |
| `PATCH /ai/proposals/{id}/` | Kullanıcının düzelttiği structured_draft | P / O | 4 |
| `POST /ai/proposals/{id}/accept/` | expected_revision, accepted_fields → yeni taslak revision | P+M / O | 4 |
| `POST /reports/` | scope, filters, format=csv → yetkili rapor kaydı | P / A | 3 |
| `GET /reports/{id}/download/` | Yetki kontrolüyle CSV indirme | P / A | 3 |
| `POST /ai/performance-summaries/` | publication_ids → job_id; yalnız yayımlanmış kanıt | P+M / A | 5 |
| `POST /offerings/{id}/simulate/` | Kendi kayıtlı puanları üzerinde overrides → kaydedilmeyen sonuç | P / A | 5 |
| `GET /audit-events/?offering_id=` | Scope'lu işlem geçmişi | M / O+A | 3 |
| `GET /health/live/`, `GET /health/ready/` | Canlılık ve DB hazır olma; hassas detay yok | M / — | 0,6 |

Rapor MVP 3'te senkron, boyutu sınırlandırılmış CSV olabilir; aynı `/reports/` kaynağı MVP 4'te job üzerinden 202 destekler. İlk sürüm formatı CSV'dir; görsel PDF ürün raporu sonraki genişlemedir. Ders için teslim edilecek basılı raporlar bu ürün endpointinden farklıdır.

Rapor nesnesi `id`, `state`, `scope`, `filters`, `publication_ids`, `job_id` (yoksa null), `download_url` (hazır değilse null) ve `expires_at` alanlarını taşır. Kaynak yayınlar rapor yaratılırken sabitlenir; indirme anında farklı notlarla yeniden hesap yapılmaz. Her download isteğinde yetki yeniden kontrol edilir.

CSV başlıkları: `student_number,assessment_code,raw_score,state,reason`. Önizleme öğrenci eşlemesini, geçersiz puanı, yinelenen satırı ve mevcut değerin değişimini gösterir. Önizleme yazma yapmaz; commit aynı batch/hash/revision'a bağlıdır. Başlangıç sınırı 5 MB ve 10.000 satırdır; aşılırsa 413. CSV dışa aktarımında formül başlatabilen hücreler güvenli biçimde escape edilir.

AI PDF sınırı başlangıçta 10 MB/30 sayfadır. Uzantı ve içerik tipi birlikte doğrulanır; kullanıcı dosyası public static altında sunulmaz. Metin içermeyen taranmış PDF için “manuel giriş gerekli” akışı vardır; OCR başlangıç kapsamına dahil değildir. Rapor indirmeleri kullanıcı ve scope kontrolünü her seferinde yapar.

Job sorgusunda frontend 2, 4, 8 saniyeye çıkan ve 10 saniyede sınırlanan polling kullanır; sekme gizliyken azaltır, terminal durumda durur. Job `result_ref`, `error_code`, `retryable` ve zaman damgalarını döndürür. Timeout'ta sonsuz spinner yerine yeniden deneme ve manuel yol sunulur.

Retry için idempotency anahtarı kullanılır ve aynı job aynı anda iki defa çalıştırılmaz. Cancel işlemi `cancel_requested` alanını işaretler; worker bir sonraki güvenli noktada durur. Harici sağlayıcı isteği başlamışsa maliyet doğmuş olabilir. UI iptal isteğini tamamlanmış iptal gibi sunmaz; terminal `cancelled` durumunu bekler.

## Frontend ve backend birlikte nasıl bağımsız ilerler

1. Feature issue seçilir; sahibi ve tüketicisi bu dosyadaki endpointi OpenAPI'de kesinleştirir.
2. İki taraf request, response, enum, null, hata ve pagination kurallarını bir küçük sözleşme PR'ında onaylar.
3. En az success, empty, validation, forbidden, conflict örnekleri `contracts/examples` altında oluşturulur. Async işte failed/timeout eklenir.
4. Frontend TypeScript tiplerini şemadan üretir ve MSW ile ekranı geliştirir. Backend aynı fixture'ları API/contract testinde kullanır.
5. Backend tamamlanınca MSW kapatılır; aynı ekran gerçek API ile çalışır. UI içinde alan isimleri çevrilerek uyuşmazlık saklanmaz.
6. Gerçek PostgreSQL ve backend'e karşı E2E geçince özellik entegre sayılır. Sadece mock ile çalışan ekran Done değildir.

[drf-spectacular](https://drf-spectacular.readthedocs.io/en/latest/) şema ve istemci üretimini destekler; [MSW](https://mswjs.io/docs/) ağ katmanında örnek API sağlar. Bunlar birbirinin yerine geçmez: biri sözleşmeyi, diğeri geliştirirken gözlenen davranışı destekler.

## Sözleşme değişikliği

Başlangıç taslağı bu Markdown dosyasıdır. Uygulama başlayınca `contracts/openapi.yaml` onaylı sözleşme olur. Backend'den üretilen şema geçici dosyaya çıkarılır ve onaylı şemayla karşılaştırılır; anlamlı değişiklik aynı PR'da şema, örnek, istemci ve test güncellemesi gerektirir. İki ayrı dosya sessizce farklılaşmaz.

Alan ekleme, enum ekleme ve null davranışı bile tüketiciyle kontrol edilir. Alan silme veya anlam değiştirme için önce tüketici uyarlanır; gerektiğinde yeni API sürümü açılır. `main` üzerinde sadece backend'in veya sadece frontend'in anladığı kırıcı sözleşme bırakılmaz. İlk sürümlerde flag ile kapalı yeni akış kullanılabilir.
