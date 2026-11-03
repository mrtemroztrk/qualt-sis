# Course catalog and registration

Students pick course sections each term, their advisor approves the form, and
department heads and the ADMIN (rectorate) maintain the catalog and term plans.

- **Frontend:** read [Concepts](#concepts), [Registration flow](#registration-flow),
  [API](#api) and [Errors](#errors).
- **Backend:** also read [Code map](#code-map), [Rules in detail](#rules-in-detail)
  and [Concurrency](#concurrency).

Three Django apps work together:

| App | Models |
|---|---|
| `departments` | `Department` |
| `courses` | `Term`, `Course`, `Section`, `MeetingTime`, `TermPlan` |
| `course_registration` | `Registration`, `RegistrationItem`, `CompletedCourse` |

---

## Concepts

| Concept | Model | What it is |
|---|---|---|
| Department | `Department` | e.g. `CSE - Bilgisayar Mühendisliği` |
| Term | `Term` | e.g. 2026 Fall. Holds the **registration** and **add-drop** windows and the credit/ECTS limits |
| Course | `Course` | e.g. CSE 301, 3 credits, 6 ECTS, 3+0 hours. `kind` is `MANDATORY` (belongs to a department) or `ELECTIVE` (university-wide, no department) |
| Section | `Section` | One offering of a course in a term: number, instructor, quota. **Students register for sections, not courses.** |
| Meeting time | `MeetingTime` | Weekly hours of a section: weekday 1-7 (Monday = 1), start, end, room |
| Term plan | `TermPlan` | What one department's students of one **class year** take in one term: mandatory courses, how many electives, which electives may be chosen |
| Registration | `Registration` | A student's form for one term (one per student and term) |
| Registration item | `RegistrationItem` | One section on the form. `is_retake` marks a retake |
| Completed course | `CompletedCourse` | Passed or failed courses. Used for prerequisites and retakes until a grades module exists |

New fields on `accounts.User`:

| Field | Who has it | Meaning |
|---|---|---|
| `department` | Everyone except ADMIN | Required by the API |
| `advisor` | Students | The INSTRUCTOR or HEAD of the same department who approves the form |
| `class_year` | Students | 1-6. Selects the student's term plan |

No new roles were added. "Advisor" is a relation (a student's `advisor` field), not a role.

## Who does what

| Action | STUDENT | INSTRUCTOR | HEAD | ADMIN |
|---|---|---|---|---|
| Create departments; set a user's department, advisor, class year | | | | ✔ |
| Open terms (windows, limits) | | | | ✔ |
| Mandatory courses and their sections | | | ✔ own department | |
| Elective courses and their sections | | | | ✔ |
| Term plan: mandatory courses, `elective_count` | | | ✔ own department | ✔ |
| Term plan: `elective_options` | | | | ✔ |
| Build and submit own registration form | ✔ | | | |
| Approve or return advisees' forms | | ✔ | ✔ | |
| See sections they teach | | ✔ | ✔ | |

Rows outside a user's scope (another department, another advisor's student,
another student's form) answer **404**, not 403.

---

## Registration flow

```
           student submits           advisor approves
 DRAFT  ───────────────────▶ SUBMITTED ─────────────────▶ APPROVED
   ▲                            │
   │      advisor returns       │
   │      (note required)       ▼
   │                         RETURNED ── student submits again ──▶ SUBMITTED
   │
   └── any add or remove by the student, even after APPROVED
```

1. The ADMIN opens a term. HEADs and the ADMIN set up courses, sections and term plans.
2. During the **registration window**, the student reads their plan
   (`GET /api/courses/my-plan/`) and retakes (`GET /api/registration/retakes/`),
   then adds sections. The first add creates the form.
3. The student submits. The form must match the plan exactly.
4. The advisor approves it, or returns it with a note.
5. During the **add-drop window**, the student may add or remove sections. Any
   change sets the form back to `DRAFT`, so it needs a new submission and approval.

A seat is taken **when the section is added**, whatever the form's status, and
freed when it is removed.

## Retakes (alttan ders)

Retakes are computed; nobody lists them by hand. A course is a retake for a student when all of these hold:

1. The student **failed** it (`CompletedCourse.passed = false`) and has not passed it since.
2. It is a mandatory course in **this term's plan** for a **lower class year** of the student's department.

Then:

- A retake with a section open this term is **required**: the form cannot be submitted without it.
- A retake **may clash** with other hours. Each item shows `conflicts_with`; the student settles the clash with the instructor.
- Retakes **do not count** toward `max_credit` / `max_ects`. The form shows `total_*` (all courses) and `counted_*` (what the limits apply to).

## Prerequisites over the plan

A mandatory course whose prerequisite the student has not passed **cannot be added
and is not required** this term. Example: Ali (year 3) failed CSE 101, and his
plan has CSE 303, which needs CSE 101. Ali retakes CSE 101 only, submits his form
without CSE 303, and takes CSE 303 in a later term.

`GET /api/courses/my-plan/` shows `missing_prerequisites` on each mandatory course,
so the client can show the course as locked (`[]` means it can be taken).

---

## API

Every endpoint needs `Authorization: Bearer <access token>` from
`POST /api/auth/login/`, and a user who has changed their first password.
List endpoints are paginated: `{"count", "next", "previous", "results"}`, with
`?page=` and `?page_size=` (max 200). `GET /api/departments/` is not paginated.

### Departments and users (ADMIN)

| Method | Path | Body / query | Notes |
|---|---|---|---|
| GET | `/api/departments/` | | Anyone signed in. Non-admins see active departments only |
| POST | `/api/departments/` | `{code, name, language}` | |
| PATCH | `/api/departments/<id>/` | any of the above, `is_active` | |
| POST | `/api/auth/users/` | `{email, first_name, last_name, role, student_no, department, advisor, class_year}` | `department` required except for ADMIN; students need `student_no` and `class_year` |
| GET, PATCH | `/api/auth/users/<id>/` | `{department, advisor, class_year}` | Role cannot change here |

### Terms

| Method | Path | Body / query | Who |
|---|---|---|---|
| GET | `/api/courses/terms/` | | Anyone signed in |
| POST | `/api/courses/terms/` | `{year, season: FALL\|SPRING\|SUMMER, registration_start, registration_end, add_drop_start, add_drop_end, max_credit?, max_ects?}` | ADMIN. Limits default to 24 credits and 30 ECTS |
| PATCH | `/api/courses/terms/<id>/` | any of the above | ADMIN |

### Catalog management (HEAD and ADMIN)

The same endpoints serve both roles. A **HEAD** sees and writes only their own
department's **mandatory** courses. The **ADMIN** sees and writes only **elective**
courses. `kind` and `department` are set from the role; clients do not send them.

| Method | Path | Body / query | Notes |
|---|---|---|---|
| GET, POST | `/api/courses/manage/courses/` | `{code, name, credit, ects, theory_hours, practice_hours, prerequisites: [course ids]}` | |
| GET, PATCH | `/api/courses/manage/courses/<id>/` | | No delete. Send `is_active: false` to close a course |
| GET, POST | `/api/courses/manage/sections/?term=` | `{course, term, number, instructor, quota, meeting_times: [{weekday, start_time, end_time, room}]}` | `instructor` must be an active INSTRUCTOR or HEAD |
| GET, PATCH, DELETE | `/api/courses/manage/sections/<id>/` | | `meeting_times` replaces the whole list. Quota cannot go below seats taken. Once a student holds a seat, the section cannot be deleted and its course and term cannot change |
| GET | `/api/courses/manage/sections/<id>/students/` | | Students holding a seat |
| GET, POST | `/api/courses/manage/plans/?term=&department=` | `{department, term, class_year, mandatory_courses: [ids], elective_count, elective_options: [ids]}` | A HEAD omits `department` (their own is used). Only the ADMIN may send `elective_options` (403 otherwise) |
| GET, PATCH, DELETE | `/api/courses/manage/plans/<id>/` | | Reads return course summaries instead of ids |

### Catalog (read)

| Method | Path | Query | Who |
|---|---|---|---|
| GET | `/api/courses/sections/` | `term, department, kind, search` (code or name) | Anyone signed in. The course cards |
| GET | `/api/courses/my-plan/` | `term` (required) | STUDENT. 404 if no plan exists for their department and class year. Each mandatory course has `missing_prerequisites` |
| GET | `/api/courses/my-sections/` | `term` | INSTRUCTOR, HEAD: sections they teach |

A section (course card) looks like this:

```json
{
  "id": 7,
  "term": 1,
  "number": 1,
  "quota": 40,
  "seats_taken": 12,
  "course": {
    "id": 3, "kind": "MANDATORY", "code": "CSE 301", "name": "Bilgisayar Mimarisi",
    "credit": 3, "ects": 6, "theory_hours": 3, "practice_hours": 0,
    "department": "CSE - Bilgisayar Mühendisliği"
  },
  "instructor": {"id": 4, "first_name": "Cengiz", "last_name": "Riva", "email": "cengiz.riva@obs.test"},
  "meeting_times": [{"id": 9, "weekday": 1, "start_time": "09:00:00", "end_time": "12:00:00", "room": ""}]
}
```

Electives have `"kind": "ELECTIVE"` and `"department": null`.

### Student registration

| Method | Path | Body / query | Returns |
|---|---|---|---|
| GET | `/api/registration/mine/` | `term` | The student's forms (paginated) |
| GET | `/api/registration/retakes/` | `term` (required) | `[{...course, "required": true}]` |
| POST | `/api/registration/items/` | `{section}` | The whole form, 201 |
| DELETE | `/api/registration/items/<item id>/` | | The whole form, 200 |
| POST | `/api/registration/<form id>/submit/` | | The whole form, 200 |

Every write returns the whole form, so the client does not need a second request:

```json
{
  "id": 1,
  "student": {"id": 5, "student_no": "DEMO-3001", "first_name": "Ali", "last_name": "Yılmaz", "email": "...", "class_year": 3},
  "term": 1,
  "status": "DRAFT",
  "submitted_at": null, "decided_at": null, "decided_by": null, "advisor_note": "",
  "items": [
    {"id": 11, "section": {"...": "course card as above"}, "is_retake": true,
     "added_at": "...", "conflicts_with": ["CSE 301"]}
  ],
  "total_credit": 12, "total_ects": 21,
  "counted_credit": 8, "counted_ects": 15
}
```

### Advisor

| Method | Path | Body / query | Notes |
|---|---|---|---|
| GET | `/api/registration/advisor/` | `term, status` (e.g. `SUBMITTED`) | Forms of the caller's advisees, oldest submission first |
| POST | `/api/registration/advisor/<form id>/approve/` | `{note?}` | |
| POST | `/api/registration/advisor/<form id>/return/` | `{note}` | Note required (400 without it) |

---

## Errors

| Status | Meaning | Body |
|---|---|---|
| 400 | A field is wrong | `{"<field>": ["message"]}` |
| 403 | Wrong role, or a HEAD sending `elective_options` | `{"detail": "..."}` |
| 404 | Not found, or outside the caller's scope | `{"detail": "..."}` |
| 409 | A registration rule blocked the action | `{"code": "...", "detail": "..."}` |

Branch on `code`, not on the `detail` text:

| `code` | When |
|---|---|
| `registration_closed` | Outside the registration and add-drop windows |
| `course_inactive` | The course is closed |
| `already_added` | This section is already on the form |
| `same_course` | Another section of the same course is on the form |
| `no_plan` | No plan for the student's department, class year and term |
| `not_in_plan` | A mandatory course that is neither in the plan nor a retake |
| `elective_not_offered` | The elective is not in the plan's `elective_options` |
| `elective_limit` | The plan's `elective_count` is already reached |
| `quota_full` | No seat left |
| `credit_limit`, `ects_limit` | The term's limit would be exceeded (retakes excluded) |
| `schedule_conflict` | Hours overlap another non-retake course on the form |
| `prerequisite_missing` | A prerequisite has not been passed |
| `already_approved` | Submitting a form the advisor already approved |
| `no_advisor` | The student has no advisor yet |
| `empty_registration` | Submitting an empty form |
| `plan_incomplete` | The form does not match the plan. Extra fields: `missing_courses`, `missing_retakes`, `electives_required`, `electives_chosen`. Courses blocked by a prerequisite are never listed as missing |
| `not_submitted` | The advisor decides on a form that is not `SUBMITTED` |
| `section_in_use` | Deleting a section that students hold seats in |

---

## Code map

| File | Role |
|---|---|
| `departments/models.py` | `Department`. Depends on nothing, so `accounts` and `courses` can both point to it without a cycle |
| `accounts/serializers.py` | `validate_academic_assignment`: department, advisor and class year rules per role |
| `courses/access.py` | `manageable_courses(user)`, `manageable_plans(user)`: the HEAD/ADMIN scope behind every management view |
| `courses/serializers.py` | Catalog input rules (section ownership, overlapping meeting times, quota floor, plan permissions) and the course card output |
| `courses/views.py` | Thin generic views. Querysets come from `access.py`, so out-of-scope rows answer 404 |
| `course_registration/services.py` | **All registration rules**: `add_section`, `remove_section`, `submit_registration`, `decide_registration`, `retake_courses` |
| `course_registration/views.py` | Thin views: check the role, validate input, call a service, return the whole form |
| `course_registration/serializers.py` | The form output, including `conflicts_with` and the `total_*` / `counted_*` sums |
| `course_registration/management/commands/seed_course_demo.py` | Demo data |

Simple create/edit endpoints go view → serializer → model. Anything with rules
across several tables goes view → **service** → model, following the
`library_reservations` pattern.

## Rules in detail

`add_section` checks, in order: student eligible → window open → course active →
not already on the form → not another section of the same course → allowed by
the plan (mandatory in plan, retake, or offered elective under `elective_count`) →
seat left → limits (skipped for retakes) → no clash with non-retake courses →
prerequisites passed. Then it creates the item and sets the form to `DRAFT`.

`submit_registration` checks: window open → not already approved → advisor set →
not empty → plan complete (every mandatory course and every required retake whose
prerequisites are passed, exactly `elective_count` electives) → limits. The plan and limits are checked
again here because they may have changed since the courses were added.

## Concurrency

Every registration service runs in one transaction and locks rows in the same
order: **student, then section** (`select_for_update`).

- The student lock serializes one student's writes, so two tabs cannot both pass the credit limit or the elective count.
- The section lock serializes seats, so two students cannot both take the last seat. The HEAD/ADMIN section PATCH and DELETE take the same lock, so a quota change cannot interleave with a registration.
- The advisor's decision locks the student too, so the form cannot change while it is being decided.

`course_registration/tests/test_concurrency.py` checks this with separate PostgreSQL connections.

---

## Run, test, demo

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py test departments courses course_registration --noinput
```

### Demo data (local databases only)

```bash
docker compose exec web python manage.py seed_course_demo
```

The command creates or refreshes the demo rows and clears the demo students'
forms, so the scenario can be run again. The 2026 Fall registration window is
placed around the current time, so it is always open. Every demo user's
password is `DemoPass123!`.

| Email | Role | Notes |
|---|---|---|
| `admin.demo@obs.test` | ADMIN | API only. Use a superuser for `/admin/` |
| `head.cse@obs.test` | HEAD | CSE |
| `head.ee@obs.test` | HEAD | EE |
| `cengiz.riva@obs.test` | INSTRUCTOR | Advisor of Ali and Zeynep |
| `elif.sahin@obs.test` | INSTRUCTOR | Advisor of Mehmet |
| `ali.yilmaz@obs.test` | STUDENT | CSE year 3. Failed CSE 101: a required retake, and CSE 303 (needs CSE 101) is locked for him |
| `zeynep.ak@obs.test` | STUDENT | CSE year 3. Passed CSE 101 |
| `mehmet.oz@obs.test` | STUDENT | CSE year 1 |

| Plan (2026 Fall) | Mandatory | Electives |
|---|---|---|
| CSE year 3 | CSE 301, CSE 303, CSE 305 | 1 of UNI 101, UNI 102 |
| CSE year 1 | CSE 101, CSE 103 | none |

CSE 101 meets on Monday 10-12 and clashes with CSE 301 (Monday 09-12), which
shows a retake conflict. CSE 305 has a quota of 2. UNI 103 exists but is not offered to any plan.

---

## Known gaps

- `CompletedCourse` stands in for a grades module and is filled by hand in `/admin/`.
- Courses the student never took (rather than failed) are not retakes, and failed electives are not retakes.
- No advisor decision deadline and no notifications.
- Removed items are deleted, not kept as history.
- The plan is checked when the student submits, not again when the advisor approves.
