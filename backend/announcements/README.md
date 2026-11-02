# Announcements backend

Official notices and student posts have separate channels and URLs. The frontend
team builds the screens; this module supplies their API and access rules.

All endpoints require the existing JWT login and completion of the first password
change. This module does not modify accounts, the login screen, grades or timetables.
It has no dependency on the program outcomes module or its pull request.

## Channel and ownership rules

| Role | Read official feed | Read student feed | Create official post | Create student post |
| --- | --- | --- | --- | --- |
| STUDENT | Yes | Yes | No | Yes |
| INSTRUCTOR | Yes | Yes | Yes | No |
| HEAD | Yes | Yes | Yes | No |
| ADMIN | Yes | Yes | Yes | No |

Only the author can edit, publish, withdraw or archive a post, and their current
role must still allow writing in its channel. HEAD and ADMIN do not have an
ownership bypass. `is_staff` and `is_superuser` do not grant extra API access.

All authenticated roles can read published posts in both channels. These are
campus-wide feeds, not department-specific or course-specific notices. Moderation,
comments, likes, attachments, scheduled publishing and email notifications are
outside this first version. There is no separate Django admin screen.

## Files and integration

| File | Responsibility |
| --- | --- |
| `models.py` | Announcement, channel, author and publication state. |
| `migrations/0001_initial.py` | Create the table and its relationship to the existing user model. |
| `serializers.py` | JSON fields, validation, author display name and publication time. |
| `permissions.py` | Who may write to each channel and change each record. |
| `pagination.py` | Page sizes for feeds and personal lists. |
| `views.py` | Shared feeds, personal lists, detail, create and edit requests. |
| `urls.py` | Separate official and student routes. |
| `tests.py` | Channel boundaries, privacy, ownership and publication rules. |
| `test_integration.py` | Existing login, password change, refresh and current-role checks. |

The same small views serve both channels. Each URL passes a fixed channel into
its view; the request body cannot choose a different one. `perform_create()` sets
the author from the authenticated account. No new authentication mechanism is used.

Django integration is one app entry in `config/settings.py` and one URL include
in `config/urls.py`. No new dependency or production service is required.

## Endpoints

Base path: `/api/announcements/`. Keep the trailing slash on every URL.
Send `Authorization: Bearer <access token>` and JSON for POST/PATCH.

| Method | Path after the base path | Purpose |
| --- | --- | --- |
| GET, POST | `official/` | Read published official notices or create an official post. |
| GET | `official/mine/` | Read all of the current user's official posts. |
| GET, PATCH | `official/{id}/` | Read or edit one official post. |
| GET, POST | `student/` | Read published student posts or create a student post. |
| GET | `student/mine/` | Read all of the current user's student posts. |
| GET, PATCH | `student/{id}/` | Read or edit one student post. |

`mine/` includes the author's drafts, published posts and archived posts. Other
users, including admins, cannot read an author's unpublished detail: they receive
404. Looking up a student post through an official URL also returns 404.

Shared feeds contain only PUBLISHED posts, including when the viewer is their
author. They are sorted by most recent publication, then ID. Personal lists are
sorted by most recent update, then ID. A user who changed roles may still read
their old personal posts but cannot edit in a channel their new role cannot write.

### Pagination

Feeds and personal lists return an object with `count`, `next`, `previous` and
`results`. The default is 20 records per page. Use `?page=2` or
`?page=1&page_size=10`; `page_size` is capped at 50. An empty list has `count: 0`,
`results: []` and null page links. An out-of-range page returns 404.

There are no status, author or channel query filters. These query parameters do
not change the endpoint's visibility rules. Use the correct channel URL and
`mine/` for personal management.

## Content and publication

POST requires a non-blank `title` (at most 200 characters) and `body` (at most
10000 characters). `status` is optional and defaults to DRAFT. Unicode content
is supported. The API treats content as plain text, not trusted HTML.

| Status | Visible in shared feed? | Visible to author in mine/detail? |
| --- | --- | --- |
| DRAFT | No | Yes |
| PUBLISHED | Yes | Yes |
| ARCHIVED | No | Yes |

The author may switch between these states with PATCH. Creating a PUBLISHED post
publishes immediately. There is no approval queue. Returning to DRAFT withdraws a
published post; archiving removes it from the shared feed while retaining it for
the author. PUT and DELETE are not supported; use PATCH to edit or archive.

The server sets `published_at` when publishing and updates it when republishing
a draft or archive. Editing an already published post does not reset that time.
Drafting/archiving a previously published post retains its last publication time.

`id`, `channel`, `author_id`, `author_name`, `can_edit` and all timestamps are
read-only. Supplied read-only fields are ignored. The URL and signed-in account
always determine the channel and author, including if a client sends forged fields.

### Create a student draft

`POST /api/announcements/student/`

```json
{
  "title": "Study group",
  "body": "We are meeting in the library on Friday.",
  "status": "DRAFT"
}
```

Example 201 response (IDs and times are examples):

```json
{
  "id": 12,
  "channel": "STUDENT",
  "title": "Study group",
  "body": "We are meeting in the library on Friday.",
  "status": "DRAFT",
  "author_id": 7,
  "author_name": "Alex Morgan",
  "published_at": null,
  "created_at": "2026-11-02T17:00:00Z",
  "updated_at": "2026-11-02T17:00:00Z",
  "can_edit": true
}
```

Publish with `PATCH /api/announcements/student/12/`:

```json
{"status": "PUBLISHED"}
```

Archive with the same URL:

```json
{"status": "ARCHIVED"}
```

Successful GET detail and PATCH return the same object shape as POST. For an
official post, use the `official/` URL with an INSTRUCTOR, HEAD or ADMIN token.

`author_name` uses the user's first/last name, or `Campus member` if unset. Email
addresses and student numbers are not exposed. `can_edit` is specific to the
current viewer; do not reuse one user's cached response for another user.

## Errors

| Status | Meaning |
| --- | --- |
| 400 | Invalid or missing title/body, or a status outside the three choices. |
| 401 | Missing, invalid or expired token, or an inactive account. |
| 403 | Password change required, channel write access denied, or another author's published post. |
| 404 | Missing post, wrong channel, another author's private post, or missing page. |
| 405 | Unsupported method, such as PUT or DELETE for an authorized writer. |

Field errors use arrays, for example `{"title": ["This field may not be blank."]}`.
Permission errors use `detail`, for example
`{"detail": "Only the author can change this announcement."}`.
Check HTTP status and the current account state; do not branch on English message
text. A successful write returns 201 for POST or 200 for PATCH.

## Frontend sections to build

| Section | API | Student controls |
| --- | --- | --- |
| Official announcements | GET `official/` | Read only; keep visibly separate and prominent. |
| Student announcements | GET `student/` | Read posts and open a new-student-post form. |
| My announcements | GET `student/mine/` | Manage own drafts, publish, edit and archive where `can_edit` is true. |

For instructors, heads and admins, use `official/mine/` for their management
section and POST `official/` for new notices. They can read the student feed but
cannot post as students. Keep official notices and community posts in separate
sections; do not merge them into an unlabeled feed.

Use the existing login result's `user.role` to show the correct create button.
Use each record's `can_edit` for edit/publish/archive controls. Both are UI aids;
the server checks permissions again for every request.

Implementation steps for the frontend team:

1. Reuse the existing `qualt:login` event and `session.access` token.
2. Fetch each channel separately and render `data.results`, not the outer object.
3. Render title, body and author name as text (for example, `textContent`), not `innerHTML`.
4. Provide title/body inputs and explicit Save draft / Publish actions.
5. Show 400 field errors without discarding the user's form text.
6. Reload the relevant feed and personal list after a successful write.
7. Clear announcement data on `qualt:logout`. Use the existing login/refresh flow on 401.

Minimal request example using the current frontend's session shape:

```javascript
const response = await fetch(`${BACKEND_ORIGIN}/api/announcements/student/`, {
  headers: { Authorization: `Bearer ${session.access}` },
});
const data = await response.json();
if (!response.ok) throw new Error(`Could not load announcements (${response.status}).`);
const posts = data.results;
```

## Run and test

Use the existing Docker setup from `backend/`. In a fresh checkout, copy
`.env.example` to `.env`, fill the local database values and leave EMAIL_HOST empty
for console email. Do not commit credentials.

```bash
docker compose up -d db
docker compose run --rm web python manage.py migrate
docker compose up -d --build web
docker compose exec web python manage.py test announcements --verbosity 2
docker compose exec web python manage.py makemigrations --check --dry-run
```

Wait for PostgreSQL to be ready before migration. If the existing Compose ports
or names are occupied, use a local override rather than stopping unrelated apps.
The automated tests create and remove a separate test database; the migration
does not insert demo posts or accounts into the normal application database.

For manual testing, use existing student and instructor accounts. For an empty
local test database only, create two accounts in `python manage.py shell` inside
the web container:

```python
from getpass import getpass
from accounts.models import User

for role, name in [(User.Role.STUDENT, "student"), (User.Role.INSTRUCTOR, "instructor")]:
    email = f"notice-{name}@example.test"
    User.objects.create_user(
        username=email, email=email, first_name="Demo", last_name=name.title(),
        password=getpass(f"Temporary password for {email}: "),
        role=role, must_change_password=True,
    )
```

These shell-created accounts do not send email. Log in and complete the existing
password-change flow, then use the returned access tokens. For API requests:

```bash
API_URL=http://localhost:8000
ACCESS_TOKEN='<your student access token>'

curl -i "$API_URL/api/announcements/official/" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

curl -i -X POST "$API_URL/api/announcements/student/" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Study group","body":"Meet in the library.","status":"DRAFT"}'

curl -i "$API_URL/api/announcements/student/mine/" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

# Replace with the ID returned by POST.
ANNOUNCEMENT_ID=12
curl -i -X PATCH "$API_URL/api/announcements/student/$ANNOUNCEMENT_ID/" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"status":"PUBLISHED"}'
```

Verify that the student token receives 403 for POST `official/`, that an instructor
can publish there, and that a different student cannot edit the first student's
post. Replace API_URL's port when using a local Compose override.
