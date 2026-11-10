# Grades backend

The instructor assigned to a section splits its course grade into components
(Midterm 30%, Project 20%, Final 50%, ...), enters scores and publishes them.
Students see published scores and their running course average. Learning and
program outcome links are not part of this module yet.

## Who may do what

| Role | Access |
| --- | --- |
| INSTRUCTOR, or a HEAD teaching the section | Components, grade sheet, grade entry, CSV import, publishing for sections they teach |
| STUDENT | `/api/grades/mine/`: their own published scores and averages |
| Anyone else | Teaching URLs answer 403 by role, or 404 for another instructor's section |

Graded students are those whose **approved** registration form for the term
contains the section (`Registration.approved_items`). A form the student is still
changing during add-drop does not move them until the advisor approves it.

## Rules

- A section's component weights never add up to more than 100%.
- Publishing a component needs exactly 100%; after anything is published the total
  must stay at 100% (rebalance weights in one step, or unpublish first).
- Scores are between 0 and the component's `max_score` (default 100), two decimals.
  `max_score` cannot drop below a score already entered.
- A component with grades, or a published one, cannot be deleted (409).
- A grade batch is all or nothing; a `null` score removes that student's grade.
- Every write locks the section row, so totals and limits hold under concurrent requests.

## Course average

Each graded component counts as `score / max_score * 100`, weighted by its share:

```
average = Σ(weight × percent) ÷ Σ weight    (graded components only)
earned  = Σ(weight × percent ÷ 100)         (points toward the course grade so far)
```

`graded_weight` tells how much of the course is graded. Students' averages use only
published components; the instructor's sheet uses every graded component.

## API

All URLs keep their trailing slash and need the JWT bearer token. The instructor's
section list is the catalog's `GET /api/courses/my-sections/`.

| Method | Path | Result |
| --- | --- | --- |
| GET, POST | `/api/grades/teaching/sections/<id>/components/` | Section's components / create one |
| GET, PATCH, DELETE | `/api/grades/teaching/components/<id>/` | One component |
| GET | `/api/grades/teaching/sections/<id>/sheet/` | Students × components with averages |
| GET, POST | `/api/grades/teaching/components/<id>/grades/` | Grades / save `{"grades": [{"student": 7, "score": "85.5"}]}` |
| POST | `/api/grades/teaching/components/<id>/grades/import/` | Multipart `file`: CSV with `student_no` and `score` |
| GET | `/api/grades/teaching/components/<id>/grades/template/` | CSV of the roster with current scores |
| POST | `/api/grades/teaching/components/<id>/publish/` and `.../unpublish/` | Show or hide scores to students |
| GET | `/api/grades/mine/?term=<id>` | Student's sections, published scores, averages |

Component body: `kind` (MIDTERM, FINAL, PROJECT, ASSIGNMENT, QUIZ, ATTENDANCE, OTHER),
`name`, `weight`, `max_score`, `display_order`. Responses add `id`, `section`,
`is_published`, `published_at`, `grade_count`, `created_at`, `updated_at`.

CSV import accepts `,` `;` or tab separators and a decimal comma, so a template
saved by Excel in Turkish imports as is. Rows with an empty score are skipped.
Errors are reported by file line number. Grade saves and publishing answer with
`missing_grades`: graded students without a score in that component.

Errors: 400 for invalid fields, weights over 100% or rejected rows; 409 with a
`code` (`weights_incomplete`, `published_weights`, `published`, `has_grades`).

## Testing

```bash
docker compose exec web python manage.py test grades
```

Demo data: after the demo forms are approved, `python manage.py seed_grades_demo`.
