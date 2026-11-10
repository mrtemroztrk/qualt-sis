# Local demo and review

The current team interface is the repository-root `index.html`. Django serves it
at `/`, and it calls `/api/...` on the same origin. A separate static server or
frontend port is not needed. The older `frontend/index.html` is the original login
prototype and is not the demo entry point.

## Start

From `backend/`, prepare the ignored `.env` using `.env.example`. Fill the database
credentials and leave SMTP settings empty to use console email.

```bash
docker compose up -d db
docker compose run --rm web python manage.py migrate
docker compose up -d --build web
```

Open `http://localhost:8000/`. If that port is occupied, set `WEB_PORT=8010` in
`.env` before starting and open `http://localhost:8010/`. The API uses the same
port automatically. Compose mounts the current root interface read-only; local
Python development can find the file in the repository without the mount.

For intentional frontend development on a separate origin, define
`window.QUALT_API_ORIGIN` before the main script and use an origin allowed in the
backend's CORS settings. The normal demo needs no override.

## Demo data

On a fresh local database only, start with Poyraz's existing course demo:

```bash
docker compose exec web python manage.py seed_course_demo
docker compose exec -T web python manage.py shell < scripts/seed_demo_features.py
```

`seed_course_demo` resets its demo students' course forms and completion records;
do not rerun it while preserving a rehearsal. `seed_demo_features.py` only adds
missing sample outcomes, rooms, announcements and feedback scenarios. It does
not reset forms, modify existing content, change consent or replace votes, so it
can be rerun without erasing the demo. All sample outcomes are illustrative.

Every course-demo account uses `DemoPass123!`:

| Role | Email | Demo use |
| --- | --- | --- |
| ADMIN | `admin.demo@obs.test` | Departments, user assignments, all feedback audit, library management |
| CSE HEAD | `head.cse@obs.test` | CSE outcomes and feedback; also selected as a teaching recipient |
| EE HEAD | `head.ee@obs.test` | Separate EE outcomes; no unrelated CSE feedback |
| INSTRUCTOR | `cengiz.riva@obs.test` | Advisor review, private feedback, sharing, polls |
| INSTRUCTOR | `elif.sahin@obs.test` | Another instructor's scope and teaching roster |
| STUDENT | `ali.yilmaz@obs.test` | Year 3, retake and blocked prerequisite, sharing decisions |
| STUDENT | `zeynep.ak@obs.test` | Year 3, prerequisite already passed, discussion participation |
| STUDENT | `mehmet.oz@obs.test` | Year 1, independent term plan |

These are local demonstration credentials, not production accounts.

## Rehearsal order

1. ADMIN: show the two departments and their users. Show the two separate PO1
   definitions, feedback audit and library rooms. Do not create real users or
   send real email during the demo.
2. CSE HEAD then EE HEAD: show that each sees their own program outcomes. CSE
   department feedback must not appear for EE HEAD.
3. Ali: inspect the term plan, retake and missing-prerequisite messages. Select
   the required courses and one offered elective; submit to Cengiz. A draft
   section already holds a seat, as documented by the course module.
4. Cengiz: approve the form. Ali's weekly schedule now appears. If Ali changes
   the form in an open window, the last approved schedule stays visible until
   the next approval.
5. Student: compare official announcements with the separate student channel.
6. Ali: reserve and cancel an available full hour in the library. Show the daily
   two-hour and weekly five-hour limits and Monday 07:00 Istanbul reset boundary.
   ADMIN alone manages cancellation and reversible bans.
7. Feedback: show private instructor-only and HEAD-only records, a rejected
   sharing request with continuing private replies, and the published poll.
8. Ali: review the pending teaching-head proposal. Show the exact department,
   anonymity and visibility conditions; counter or approve. CSE HEAD can publish
   only after accepting Ali's conditions. A head who is not the selected teacher
   cannot publish another instructor's feedback.
9. Compare the published discussion as student, selected instructor, relevant
   HEAD and ADMIN. Hidden identities remain hidden outside ADMIN audit, and a
   withdrawn discussion disappears from ordinary feeds.

The grades module and LO/PO score calculations are not part of this demo.

## Before presenting

```bash
docker compose exec web python manage.py migrate --check
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose exec web python manage.py test --noinput
```

Use `docs/DEMO.md` for the scenario and each backend module's README for its API
contract. Take a PostgreSQL backup before applying migrations to an existing
database. Legacy outcomes need explicit ADMIN department assignment; feedback
migration copies known student departments and preserves unknown records for
ADMIN classification. The development server and demo credentials are for local
rehearsal; production deployment is a separate configuration task.
