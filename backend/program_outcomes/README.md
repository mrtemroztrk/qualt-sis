# Program outcomes backend

This module stores the expected graduate skills of the pilot Computer Engineering
program. A department head or admin maintains the definitions. Students and
instructors can read them.

The module manages definitions, not student scores. It does not create courses,
enter grades, build timetables or calculate LO/PO weights. Future course modules
can reference a `ProgramOutcome` by its database `id`.

## Scope

There is one shared outcome catalogue for the pilot program. There is no program
or department field yet. Every `HEAD` and `ADMIN` account has the same write
access. Before supporting multiple programs, add program membership and scoped
permissions together; the current role check is not department isolation.

No official PO text or demo accounts are inserted by the migration. Example
descriptions below are illustrative, not the university's approved wording.

## Where the code lives

| File | Responsibility |
| --- | --- |
| `models.py` | Store outcome definitions and enforce unique codes. |
| `migrations/0001_initial.py` | Create the outcome table. |
| `serializers.py` | Define JSON fields and reuse model validation. |
| `permissions.py` | Apply the existing password rule and restrict changes to heads/admins. |
| `views.py` | Handle list, detail, create and partial update requests. |
| `urls.py` | Declare this module's routes. |
| `tests.py` | Test stored data, validation and role permissions. |
| `test_integration.py` | Test the module through the existing JWT login flow. |

Integration with Django is limited to adding `program_outcomes` to
`config/settings.py` and including its URLs in `config/urls.py`. The existing
`accounts` application, dependencies, frontend and Docker services are unchanged.
There is no separate Django admin screen for this module in this version.

## Access rules

All requests need `Authorization: Bearer <access token>`. Use the existing
`/api/auth/login/` endpoint to get tokens.

| Account | List / detail | Create / edit / activate / deactivate |
| --- | --- | --- |
| `STUDENT` | Yes | No |
| `INSTRUCTOR` | Yes | No |
| `HEAD` | Yes | Yes |
| `ADMIN` | Yes | Yes |
| Anonymous or invalid token | No: 401 | No: 401 |
| First password change still required | No: 403 | No: 403 |

The API checks the user's current database role, not a role value supplied by the
frontend. `is_staff` and `is_superuser` do not replace the `HEAD`/`ADMIN` role check.

## Endpoints

Keep the trailing slash on each URL.

| Method | URL | Success | Purpose |
| --- | --- | --- | --- |
| GET | `/api/program-outcomes/` | 200 | List all definitions. |
| GET | `/api/program-outcomes/{id}/` | 200 | Read one definition. |
| POST | `/api/program-outcomes/` | 201 | Create a definition. |
| PATCH | `/api/program-outcomes/{id}/` | 200 | Change supplied fields only. |

The list is a JSON array, not a paginated `results` object. An empty catalogue
returns `[]`. Both active and inactive definitions are included. There are no
query filters in this version. A current-outcomes screen can use
`outcomes.filter(outcome => outcome.is_active)`; a management screen can show both.
Records are ordered by `display_order`, then `code` to break ties.

`PUT` and `DELETE` are not supported (405 for a permitted manager). Deactivate
with `PATCH {"is_active": false}` and reactivate with `PATCH {"is_active": true}`.
Both operations keep the same ID, including for future references from courses.
Inactive codes remain reserved and cannot be reused for another record.

## Fields

| Field | Rules |
| --- | --- |
| `id` | Read-only integer; use it in detail URLs and future relationships. |
| `code` | Required, unique, uppercase `PO` followed by a positive integer without leading zeros; at most 16 characters. Examples: `PO1`, `PO12`. |
| `title` | Required, non-blank text, at most 200 characters. |
| `description` | Required, non-blank text, at most 4000 characters. |
| `display_order` | Integer from 1 to 32767; defaults to 1. |
| `is_active` | Boolean; defaults to `true`. |
| `created_at` | Read-only creation timestamp. |
| `updated_at` | Read-only timestamp of the latest saved change. |

Required fields must be supplied on POST. PATCH only validates supplied fields;
omitting a field keeps its current value. Text can contain Unicode characters.

POST example:

```json
{
  "code": "PO1",
  "title": "Problem solving",
  "description": "Identify and solve engineering problems.",
  "display_order": 1,
  "is_active": true
}
```

Example response (IDs and timestamps are assigned by the server):

```json
{
  "id": 1,
  "code": "PO1",
  "title": "Problem solving",
  "description": "Identify and solve engineering problems.",
  "display_order": 1,
  "is_active": true,
  "created_at": "2026-11-02T12:00:00Z",
  "updated_at": "2026-11-02T12:00:00Z"
}
```

GET detail and PATCH return the same field structure. GET list returns an array
of these objects.

## Errors the frontend should handle

| Status | Meaning | Suggested UI behavior |
| --- | --- | --- |
| 400 | Invalid field, missing required field or duplicate code. | Show the field's error messages next to its input. |
| 401 | Missing, invalid or expired access token. | Use the existing refresh/login flow. |
| 403 | Password change required or role cannot write. | Finish password change or show a permission message. |
| 404 | The requested outcome ID does not exist. | Return to the list and refresh it. |
| 405 | The HTTP method is not supported. | Use PATCH for changes and deactivation. |

Example field error:

```json
{"code": ["Use an outcome code such as PO1 or PO12."]}
```

Example role error:

```json
{"detail": "Only department heads and admins can change program outcomes."}
```

Do not decide access from an error's English text. Use the HTTP status and the
current user's `role` / `must_change_password` fields. The backend remains the
authority even if the frontend hides edit buttons.

## Run and test with the existing Docker setup

Run commands from `backend/`. For a fresh local checkout, copy `.env.example` to
`.env`, fill `DB_NAME`, `DB_USER` and a local `DB_PASSWORD`, and leave `EMAIL_HOST`
empty to use console email. Do not commit `.env`.

```bash
docker compose up -d db
docker compose run --rm web python manage.py migrate
docker compose up -d --build web
docker compose exec web python manage.py test program_outcomes --verbosity 2
docker compose exec web python manage.py makemigrations --check --dry-run
```

On the first build, `docker compose run` builds the web image if needed. PostgreSQL
must be ready before migration; if it is still starting, retry after it becomes
ready. These commands use the existing `backend/docker-compose.yml` ports and
container names. If they are already occupied by another project, use a local
Compose override with different names and ports rather than stopping that project.

The tests create a separate test database and remove it afterwards. They cover
unique codes, ordering, valid and invalid writes, all four roles, deactivation,
login, first password change, token refresh and revoked access. Tests do not
populate the application's normal database.

For manual API testing, use an existing HEAD/ADMIN account. In an empty local
database only, create a test account in the Django shell:

```bash
docker compose exec web python manage.py shell
```

```python
from getpass import getpass
from accounts.models import User

User.objects.create_user(
    username="po-head@example.test",
    email="po-head@example.test",
    password=getpass("Temporary test password: "),
    role=User.Role.HEAD,
    must_change_password=True,
)
```

This creates a local test user without sending email. Log in through the existing
login screen or API and complete the required password change before testing POs.
Use a separate STUDENT account to verify that create/update requests return 403.

## Manual API requests

Set `API_URL` to your running backend and copy an access token from your own
login response. The standard Compose port is 8000; a local override may differ.
Do not put a real password or token in a committed file.

```bash
API_URL=http://localhost:8000
ACCESS_TOKEN='<access token from /api/auth/login/>'

curl -i "$API_URL/api/program-outcomes/" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

curl -i -X POST "$API_URL/api/program-outcomes/" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"code":"PO1","title":"Problem solving","description":"Identify and solve engineering problems.","display_order":1}'

# Replace this value with the ID returned by POST.
OUTCOME_ID=1

curl -i "$API_URL/api/program-outcomes/$OUTCOME_ID/" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

curl -i -X PATCH "$API_URL/api/program-outcomes/$OUTCOME_ID/" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"is_active":false}'
```

## Frontend handoff

1. Reuse the existing login response and password-change flow.
2. Fetch the catalogue after login; render an empty state for `[]`.
3. Show the code, title, description and active status. Use `id` as the item key.
4. Offer create/edit/activate/deactivate controls only to HEAD and ADMIN users.
5. Display 400 field errors near their form fields; do not discard entered text.
6. After POST or PATCH succeeds, reload the list so server ordering is reflected.

For an authenticated request with the current frontend's session object:

```javascript
const response = await fetch(`${BACKEND_ORIGIN}/api/program-outcomes/`, {
  headers: { Authorization: `Bearer ${session.access}` },
});
const data = await response.json();
if (!response.ok) {
  // Pass the status and error data to the screen's error handler.
  throw new Error(`Could not load program outcomes (${response.status}).`);
}
const activeOutcomes = data.filter(outcome => outcome.is_active);
```

This is a request example, not a new frontend screen. The frontend team owns
the screen and its integration with the existing `qualt:login` event.
