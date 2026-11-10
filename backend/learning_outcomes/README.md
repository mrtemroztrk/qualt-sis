# Learning outcomes backend

Connects grades to the department's program outcomes (`program_outcomes` app):

```
grade -> grading component --(weight %)--> learning outcome (LO) --(weight %)--> program outcome (PO)
```

## Who does what

| Role | Access |
| --- | --- |
| HEAD | LOs of their department's mandatory courses and the LOs' PO links; reads and corrects component links of those courses' sections; lists their department's students and reads their PO profiles |
| ADMIN | The same for university-wide electives; lists every student and reads their PO profiles |
| INSTRUCTOR (or a HEAD teaching the section) | Sets which components measure which LOs in sections they teach; sees the section's LO scores |
| STUDENT | Their own PO profile |

Out-of-scope rows answer 404; other roles get 403.

## Rules

- An LO belongs to a course and is used by every term's sections. Codes are `LO1`,
  `LO2`, ... and unique per course. Retire an LO with `is_active: false`; it keeps
  its existing links, gains no new ones, and DELETE is unsupported.
- A mandatory course links only to its own department's POs. An elective may link
  to any department's POs; each student sees only their own department's.
- A component links only to LOs of its section's course. Attendance-like components
  may have no links.
- Link weights are 1-100 and relative: they need not add up to 100.
- Every PUT replaces the whole set of links it is given (an empty list removes all).

## Scores

Calculated on each request from grades and links; nothing calculated is stored, so
a changed weight or link applies at once.

```
component percent = score / max_score * 100
LO score          = Σ(weight × component percent) ÷ Σ weight
PO score          = Σ(weight × LO score) ÷ Σ weight
```

- Only graded components count. An outcome nothing has measured has no score
  (`null`), not zero.
- Students, HEAD and ADMIN see scores from published components; the instructor's
  section view includes unpublished grades.
- A course taken more than once counts from its latest attempt that has a score.

The guidelines' worked example (LO1 86.0, LO2 82.9, PO1 85.0, PO2 82.9) is a test
in `tests/test_scoring.py`.

## API

All URLs are under `/api/learning-outcomes/`, keep their trailing slash and need the JWT.

| Method | Path | Result |
| --- | --- | --- |
| GET, POST | `manage/courses/<course id>/` | Course's LOs / create one (`code`, `title`, `description`, `display_order`, `is_active`) |
| GET, PATCH | `manage/<id>/` | One LO |
| GET, PUT | `manage/<id>/program-links/` | PO links / replace `{"links": [{"program_outcome": 4, "weight": 100}]}` |
| GET | `manage/sections/<id>/matrix/` | Section's LOs and each component's LO weights |
| PUT | `manage/components/<id>/links/` | Replace `{"links": [{"learning_outcome": 3, "weight": 60}]}` |
| GET | `teaching/sections/<id>/matrix/` | Same matrix, for the section's instructor |
| PUT | `teaching/components/<id>/links/` | Same replace, for the section's instructor |
| GET | `teaching/sections/<id>/scores/` | Graded students × LO scores |
| GET | `mine/` | Student's PO profile |
| GET | `students/?search=&department=` | Students whose profiles the caller may read, 50 per page (HEAD, ADMIN) |
| GET | `students/<student id>/` | A student's PO profile (HEAD, ADMIN) |

`students/` is how HEAD and ADMIN pick a student: `search` matches student number,
first or last name, or email; `department` narrows ADMIN's list (a HEAD always sees
only their own department). Each row has `id`, `student_no`, `first_name`,
`last_name`, `email`, `class_year`, `department` and `department_name`.

Matrix `links` and score maps are keyed by LO id as a string. A PO profile lists
every active PO of the student's department with `score` (two decimals or `null`)
and the `courses` that contributed.

## Testing

```bash
docker compose exec web python manage.py test learning_outcomes
```
