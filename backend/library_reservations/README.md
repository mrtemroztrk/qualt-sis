# Library room reservations

A separate Django app for reserving whole study rooms. The backend provides APIs;
the frontend team builds the booking, personal reservation and ADMIN screens.
There are no course, grade, timetable or learning outcome dependencies.

## Booking rules

- The library is open 24 hours a day, seven days a week. Each room has one
  reservation per full hour, such as 10:00–11:00. There is no seat sharing.
- Only STUDENT accounts can book. Each student can reserve at most **2 hours per
  calendar day** and **5 hours per booking week**, across all rooms.
- All calendar rules use `Europe/Istanbul`. The rest of Django keeps its existing
  time zone. Requests must include an explicit offset, such as `+03:00` or `Z`.
- The booking week starts Monday at 07:00 and ends the following Monday at 07:00.
  The end is exclusive: the final slot starts Monday at 06:00. A new week opens
  automatically at 07:00; no cron task, reset job or deletion is needed.
- A booking cannot start in the past or outside the current booking week. A slot
  is allowed exactly at its start if the request reaches the server then.
- On Monday, hours before and after 07:00 belong to different booking weeks but
  the **same calendar day**. The daily limit still applies across that boundary.
- Confirmed past hours count toward the allowance. A student cannot cancel a
  started reservation to recover quota. Future cancellation releases both the
  room and the allowance. Consecutive hours are allowed, but each is a separate
  one-hour request; the second request is not guaranteed to succeed.
- Students can read only their own reservation records. The availability grid
  reveals whether a slot can be booked, never another student's identity.

## Management rules

Only the application's **ADMIN** role can view everyone's reservations, cancel
them, manage rooms or issue/lift library bans. INSTRUCTOR and HEAD have no access
to this module. Django `is_staff` and `is_superuser` do not override these rules.
All endpoints require JWT authentication and the existing first password change.

ADMIN cancellation requires a reason and applies only before a reservation starts.
A library ban immediately cancels all of that student's future reservations in
the same transaction. A started reservation and past records are retained.
The ban only blocks new library bookings; it does not disable the campus account.
The student can still read the library panel and their own records.

Bans have no automatic expiry. ADMIN can lift a ban; cancelled reservations are
not restored. Re-banning after lifting creates a new history record. The actor,
reason and time are recorded. Repeating a cancellation or ban-lift is harmless;
creating a second active ban returns 409.

Deactivating a room stops new bookings but preserves existing reservations.
For a closure, ADMIN must also review and cancel affected future reservations
with a reason. Rooms and reservation history have no DELETE endpoint.

## Files and integration

| File | Responsibility |
| --- | --- |
| `models.py`, `migrations/` | Rooms, reservations, bans and database constraints. |
| `rules.py` | Istanbul calendar, Monday 07:00 window and quota constants. |
| `availability.py` | Private student allowance and hourly room availability. |
| `services.py` | Booking, cancellation, banning and lifting within transactions. |
| `serializers.py` | Request validation and separate student/ADMIN JSON fields. |
| `views.py` | Student read and write endpoints. |
| `admin_views.py` | ADMIN management endpoints. |
| `pagination.py`, `urls.py` | List sizes and explicit endpoint routing. |
| `tests/` | Calendar, database, API permissions, JWT and concurrency tests. |

Integration is one app entry in `config/settings.py` and one include in
`config/urls.py`. Existing `accounts.permissions.IsStudent` and `IsAdmin` are
reused. No new dependency, authentication system or production container is added.
Use the existing Django web and PostgreSQL services.

Writes lock the student's database row first, then the room when booking.
The student lock serializes quota checks even for requests to different rooms;
the room lock serializes competing students. Ban/cancellation operations share
the student lock. Partial unique constraints also protect active room/student
hours. Write reservations through these services, not direct ORM updates in new
endpoints: cross-record quotas need the transaction, not just field validation.
See [Django row locking](https://docs.djangoproject.com/en/6.0/ref/models/querysets/#select-for-update)
and [conditional constraints](https://docs.djangoproject.com/en/6.0/ref/models/constraints/#uniqueconstraint).

## API contract

Base: `/api/library/`. Keep trailing slashes. Send JSON and
`Authorization: Bearer <access token>`.

| Method | Path | Role | Purpose |
| --- | --- | --- | --- |
| GET | `rooms/` | STUDENT | List active rooms. |
| GET | `summary/` | STUDENT | Current window, weekly allowance and ban state. |
| GET | `availability/?room=1&date=2026-11-03` | STUDENT | 24 hourly slots for one day/room. |
| POST | `reservations/` | STUDENT | Book one hour. |
| GET | `reservations/mine/` | STUDENT | Only the signed-in student's reservations. |
| POST | `reservations/{id}/cancel/` | STUDENT | Cancel an owned future reservation. |
| GET, POST | `admin/rooms/` | ADMIN | List all rooms or create one. |
| GET, PATCH | `admin/rooms/{id}/` | ADMIN | View, rename, relocate or deactivate a room. |
| GET | `admin/reservations/` | ADMIN | List reservations with student identity. |
| POST | `admin/reservations/{id}/cancel/` | ADMIN | Cancel a future reservation with a reason. |
| GET, POST | `admin/bans/` | ADMIN | List ban history or issue a ban. |
| POST | `admin/bans/{id}/lift/` | ADMIN | Lift a ban without restoring bookings. |

List endpoints return `{count, next, previous, results}`. Default page size is 20;
`?page=2&page_size=50` is supported, capped at 100. Summary and availability are
single objects, not paginated lists.

Both reservation lists accept `period=upcoming|history|all` (default `upcoming`)
and optional `status=CONFIRMED|CANCELLED`. Upcoming includes an hour currently in
progress; history includes hours that have ended. Cancelled records are included
unless filtered out. Upcoming is ordered earliest first; history/all latest first.
The ADMIN list additionally accepts `student`, `room` and `date` (Istanbul date).
For past dates, also send `period=history` or `all`.

### Availability and summary

Both return `time_zone`, `server_time`, `window_start`, `window_end`, `slot_minutes`,
`daily_limit`, `weekly_limit`, `weekly_used`, `weekly_remaining`, `is_banned` and
`ban_reason`. Availability additionally returns `room_id`, `date`, `daily_used`,
`daily_remaining` and `slots`.

Each slot has `starts_at`, `ends_at`, `available` and `unavailable_reason`.
Reasons are `outside_window`, `past`, `room_inactive`, `reserved`, `banned`,
`overlap`, `daily_limit` or `weekly_limit`; an available slot has null reason.
Only one blocking reason is shown, in that order. Dates outside the current
booking window return 400. The two boundary Mondays include disabled hours.

Availability is a snapshot, not a guarantee. Another student may book before the
POST arrives. On 409, show the reason and refresh availability and allowance.

### Create a booking

`POST /api/library/reservations/`:

```json
{"room": 1, "starts_at": "2026-11-03T10:00:00+03:00"}
```

The date is illustrative: choose a future slot returned by availability.
The server chooses student, status and one-hour length. Supplied extra fields
cannot impersonate a student or bypass these rules. Success is 201:

```json
{
  "id": 12,
  "room": 1,
  "room_name": "Study Room A",
  "starts_at": "2026-11-03T07:00:00Z",
  "ends_at": "2026-11-03T08:00:00Z",
  "status": "CONFIRMED",
  "created_at": "2026-11-02T12:30:00Z",
  "cancelled_at": null,
  "cancellation_reason": "",
  "can_cancel": true
}
```

Personal list entries and cancellation responses use that shape. ADMIN entries
also include `student` (ID), `student_name`, `student_no`, and `cancelled_by` (ID).
All response dates include an offset; display them using `Europe/Istanbul`.

Student cancellation accepts `{}` or `{"reason":"Plans changed"}`. ADMIN
cancellation requires a non-blank reason (maximum 500 characters).

### Rooms and bans

Create a room as ADMIN with `{"name":"Study Room A","location":"First floor"}`.
`name` is unique, at most 80 characters; `location` is required, at most 160.
`is_active` defaults to true. PATCH accepts these same fields.

Create a ban with `{"student":7,"reason":"Repeated library rule violations"}`.
The student must exist and have STUDENT role. Success is 201 with
`{"ban": {...}, "cancelled_reservations": 2}`. The ban object contains
`id`, `student`, `student_name`, `student_no`, `reason`, `is_active`, `created_by`,
`created_at`, `lifted_by` and `lifted_at`. Lifting with POST `{}` returns that
object with `is_active: false`. ADMIN can identify a student from the reservation
list; no new campus-wide account-search endpoint is introduced.

### Errors

| Status | Meaning |
| --- | --- |
| 400 | Invalid fields, missing offset, non-hour start, past time or unopened week. |
| 401 | Missing/invalid token or inactive campus account. |
| 403 | Wrong role, required password change or active library ban when booking. |
| 404 | Unknown room/student/record, or another student's cancellation target. |
| 405 | Unsupported method. |
| 409 | Room/quota conflict, started reservation or duplicate active ban. |

409 responses contain `code` and `detail`. Codes: `room_inactive`, `room_taken`,
`overlap`, `daily_limit`, `weekly_limit`, `already_started`, `already_banned`.
The active-ban booking response is 403 with `code: library_ban` and `detail`.
Other permission errors use `detail`; field errors use `{field: [message]}`.
Use status/code for UI logic rather than matching English text.

## Frontend handoff

1. Reuse the existing `qualt:login` event and `session.access` JWT. Clear cached
   library data on `qualt:logout`; never reuse one student's response for another.
2. **Book a room:** fetch rooms and summary; let the student pick a room/date
   within the returned window, then fetch availability. Show remaining quota,
   ban state and disabled hours. Submit the exact returned `starts_at` value.
3. **My reservations:** use the separate `reservations/mine/` endpoint, with
   upcoming/history tabs. Use `can_cancel` to show the cancellation button.
   Refresh both this list and availability/summary after a successful write.
4. **ADMIN panel:** list/filter reservations; show identity only here. Provide
   cancellation and ban reason dialogs, ban history/lift controls and room setup.
5. Render user-provided room names/reasons as text, never raw HTML. Format all
   times with `Intl.DateTimeFormat('tr-TR', {timeZone: 'Europe/Istanbul', ...})`.
6. At `window_end`, refetch the summary/grid. The backend enforces the boundary
   even if a browser has stale data. Localize messages in the frontend.

No screens are added by this backend branch. Endpoint permissions remain the
authority even when the UI hides controls.

## Run and verify

From `backend/`, use the existing `.env.example` and local `.env` values. Do not
commit credentials. Once PostgreSQL is ready:

```bash
docker compose up -d db
docker compose run --rm web python manage.py migrate
docker compose up -d --build web
docker compose exec web python manage.py test library_reservations --verbosity 2
docker compose exec web python manage.py test --noinput
docker compose exec web python manage.py makemigrations --check --dry-run
```

Concurrency tests require PostgreSQL and independent connections; SQLite does
not provide the row-lock behavior this module relies on. No rooms or users are
seeded by migrations. Use an existing ADMIN account to create rooms, then a
STUDENT account that completed its first password change to reserve them.

For this local development worktree, isolated containers are named
`qualt-sis-library-web` and `qualt-sis-library-db`; the API is bound to
`127.0.0.1:8012`. The local Compose override is outside Git. Run:

```bash
docker exec qualt-sis-library-web python manage.py test library_reservations
```

Manual acceptance: create two rooms; use two student accounts to compete for one
slot; try a third daily and sixth weekly hour; cancel and rebook; ban a student,
confirm future cancellation, lift the ban and confirm other campus APIs still
work. Check HEAD/INSTRUCTOR receive 403 on all management endpoints.
