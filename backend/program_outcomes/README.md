# Program outcomes backend

Each outcome belongs to an existing `departments.Department`, the same model
used by accounts and Poyraz's course catalog. ADMIN creates departments through
`/api/departments/`; this module never creates a department or assumes a CSE code.
It stores outcome definitions, not grades or LO/PO score calculations.

## Access and ownership

| Role | Read | Write |
| --- | --- | --- |
| STUDENT, INSTRUCTOR | Own department | No |
| HEAD | Own department | Create and edit own department's outcomes |
| ADMIN | All departments and unassigned legacy outcomes | Create, edit and assign legacy outcomes |
| Account without a department | Empty list, 404 on detail | HEAD cannot create until assigned |

Authentication and the first-password-change rule use the existing accounts app.
Out-of-scope IDs return 404. A department query filter only narrows the caller's
existing access; it never grants another department's records.

`PO1` may exist once in each department. A PostgreSQL unique constraint enforces
`department + code`, including the unassigned legacy group. Assigned outcomes
cannot move to another department, so their IDs remain safe for future links.
Use PATCH `is_active: false` to retire an outcome. DELETE and PUT are unsupported.
Closing a department preserves its existing outcomes and their read/edit access;
new outcomes and legacy assignments require an active department.

## API

All URLs keep their trailing slash. Send the existing JWT bearer token.

| Method | Path | Result |
| --- | --- | --- |
| GET | `/api/program-outcomes/` | JSON array scoped to the caller |
| GET | `/api/program-outcomes/?department=2` | Narrow that array to a department |
| POST | `/api/program-outcomes/` | Created outcome, 201 |
| GET, PATCH | `/api/program-outcomes/<id>/` | Outcome, 200 |

A HEAD omits `department`; the server uses their account's department. Supplying
another department is rejected. ADMIN must supply an existing active department
on POST. Other fields keep their previous meanings and limits:

```json
{
  "department": 2,
  "code": "PO1",
  "title": "Engineering analysis",
  "description": "Analyse engineering problems using appropriate methods.",
  "display_order": 1,
  "is_active": true
}
```

Responses include those fields, `id`, `department_name`, `created_at`, `updated_at`.
`department` and `department_name` can be null only on preserved legacy records.
Codes follow `PO1`, `PO2`, etc.; title is at most 200 characters, description 4000,
and display order starts at 1. Unicode text is supported.

Errors: 400 for field validation or a duplicate code within a department, 401 for
missing/invalid authentication, 403 for a disallowed role or incomplete first
password change, 404 for missing/out-of-scope IDs, 405 for unsupported methods.
Use HTTP status and field names rather than branching on English error text.

## Existing records and frontend integration

Migration `0002_outcome_department` preserves every existing outcome and ID. It
does not guess which department owns old pilot data, even if CSE already exists.
Legacy records initially have `department: null` and are visible only to ADMIN.
An ADMIN assigns the correct department once:

```http
PATCH /api/program-outcomes/12/
Content-Type: application/json
Authorization: Bearer <access-token>

{"department": 2}
```

After assignment the department's members can read the same outcome ID. If that
department already has the same code, rename the legacy code in the same PATCH
or resolve the duplicate first. No records are automatically deleted or copied.

The root `index.html` has only a small compatibility update: ADMIN's PO form
uses `/api/departments/` to select a department for new or legacy outcomes, and
cards show the department name. HEAD forms continue to work without a selector.
The existing API paths, list shape and outcome fields remain available.

## Code map and tests

| File | Purpose |
| --- | --- |
| `models.py`, `migrations/` | Department link, stable IDs and per-department uniqueness |
| `access.py` | Department-scoped queries shared by list and detail |
| `permissions.py` | Existing login/password/role rules |
| `serializers.py` | Department assignment, code and field validation |
| `views.py`, `urls.py` | Existing API endpoints and optional department filter |
| `tests.py`, `test_integration.py` | Original model/API and real JWT scenarios |
| `test_departments.py`, `test_migrations.py` | Cross-department access and safe upgrade of existing data |

Run from `backend/` using the existing Docker setup and local `.env`:

```bash
docker compose run --rm web python manage.py migrate
docker compose exec web python manage.py test program_outcomes --noinput
docker compose exec web python manage.py makemigrations --check --dry-run
```

If the server was already running during a branch switch, restart it after
migration. Tests use a separate PostgreSQL test database. No new Python dependency
or container is required. The accounts, departments and course apps are reused.
