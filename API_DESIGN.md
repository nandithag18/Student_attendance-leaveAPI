# API Design — Student Attendance and Leave API

Design reference for implementation. Written before building the
data models and endpoints so contracts are settled up front.

---

## 1. Entities

### Student
| Field | Type | Notes |
|---|---|---|
| id | int | primary key, auto |
| roll_number | string | unique, e.g. `24BCE5285` |
| name | string | |
| email | string | unique |
| department | string | |
| semester | int | |

### AttendanceRecord
| Field | Type | Notes |
|---|---|---|
| id | int | primary key, auto |
| student_id | int | FK -> Student.id |
| course_code | string | e.g. `BCSE302L` |
| date | date | |
| status | enum | `present` \| `absent` \| `late` |
| marked_by | string | who recorded it (faculty id/name) |

Design decision to confirm: does an **approved** leave request
auto-create/override attendance records for those dates? If yes,
add a `source` field: `manual` \| `auto_from_leave`.

### LeaveRequest
| Field | Type | Notes |
|---|---|---|
| id | int | primary key, auto |
| student_id | int | FK -> Student.id |
| start_date | date | |
| end_date | date | must be >= start_date |
| reason | string | |
| status | enum | `pending` \| `approved` \| `rejected` |
| applied_on | datetime | server-set, not client-supplied |
| reviewed_by | string \| null | set on approve/reject |
| reviewed_on | datetime \| null | set on approve/reject |

---

## 2. REST endpoint plan

```
Students
  POST   /students                            201 Created
  GET    /students                             200 OK  (filters: department, semester)
  GET    /students/{id}                        200 OK / 404 Not Found
  PATCH  /students/{id}                        200 OK / 404 Not Found
  DELETE /students/{id}                         204 No Content / 404 Not Found

Attendance
  POST   /attendance                            201 Created / 409 Conflict (duplicate for same student+course+date)
  GET    /attendance                            200 OK  (filters: student_id, course_code, date_from, date_to)
  GET    /attendance/{id}                        200 OK / 404 Not Found
  PATCH  /attendance/{id}                       200 OK / 404 Not Found
  GET    /students/{id}/attendance/summary       200 OK  (% present, optionally per course_code)

Leave Requests
  POST   /leave-requests                        201 Created
  GET    /leave-requests                         200 OK  (filters: student_id, status)
  GET    /leave-requests/{id}                    200 OK / 404 Not Found
  PATCH  /leave-requests/{id}/status              200 OK / 404 Not Found / 409 Conflict (already reviewed)
  DELETE /leave-requests/{id}                     204 No Content / 409 Conflict (not pending)

Health
  GET    /health                                200 OK  [already implemented]
```

---

## 3. Request / response contracts

### POST /students
**Request**
```json
{
  "roll_number": "24BCE5285",
  "name": "Nanditha G Nair",
  "email": "nandu@example.edu",
  "department": "CSE",
  "semester": 5
}
```
**Response — 201**
```json
{
  "id": 1,
  "roll_number": "24BCE5285",
  "name": "Nanditha G Nair",
  "email": "nandu@example.edu",
  "department": "CSE",
  "semester": 5
}
```
**Response — 422** (validation error, e.g. missing field) — FastAPI's
default Pydantic error shape, no custom handling needed initially.

---

### POST /attendance
**Request**
```json
{
  "student_id": 1,
  "course_code": "BCSE302L",
  "date": "2026-09-01",
  "status": "present",
  "marked_by": "faculty_042"
}
```
**Response — 201**
```json
{
  "id": 10,
  "student_id": 1,
  "course_code": "BCSE302L",
  "date": "2026-09-01",
  "status": "present",
  "marked_by": "faculty_042"
}
```
**Response — 409** (a record already exists for this
student+course+date — decide whether duplicate marking should
overwrite or reject; recommend reject, force explicit PATCH to correct)
```json
{ "detail": "Attendance already recorded for this student, course, and date." }
```

---

### GET /students/{id}/attendance/summary
**Response — 200**
```json
{
  "student_id": 1,
  "total_classes": 40,
  "present": 34,
  "absent": 5,
  "late": 1,
  "attendance_percent": 87.5,
  "by_course": [
    { "course_code": "BCSE302L", "total": 20, "present": 18, "percent": 90.0 },
    { "course_code": "BCSE204L", "total": 20, "present": 16, "percent": 80.0 }
  ]
}
```

---

### POST /leave-requests
**Request**
```json
{
  "student_id": 1,
  "start_date": "2026-09-10",
  "end_date": "2026-09-12",
  "reason": "Medical"
}
```
**Response — 201**
```json
{
  "id": 5,
  "student_id": 1,
  "start_date": "2026-09-10",
  "end_date": "2026-09-12",
  "reason": "Medical",
  "status": "pending",
  "applied_on": "2026-09-01T14:20:00Z",
  "reviewed_by": null,
  "reviewed_on": null
}
```

---

### PATCH /leave-requests/{id}/status
**Request**
```json
{
  "status": "approved",
  "reviewed_by": "faculty_042"
}
```
**Response — 200**
```json
{
  "id": 5,
  "student_id": 1,
  "start_date": "2026-09-10",
  "end_date": "2026-09-12",
  "reason": "Medical",
  "status": "approved",
  "applied_on": "2026-09-01T14:20:00Z",
  "reviewed_by": "faculty_042",
  "reviewed_on": "2026-09-01T15:00:00Z"
}
```
**Response — 409** (already approved/rejected — reviewing twice is
not allowed; would need a new request instead)
```json
{ "detail": "This leave request has already been reviewed." }
```

---

## 4. Open decisions to make before/during implementation

1. Does an approved leave auto-generate attendance records, or stay
   fully separate from attendance tracking?
2. Should duplicate `POST /attendance` for the same
   student+course+date reject (409) or overwrite? (Recommended: reject,
   require PATCH to correct — keeps an audit trail of who marked what.)
3. Auth: none for this milestone, or a simple role check
   (student vs faculty) before touching leave-request approval and
   attendance endpoints? Worth deciding before building those handlers
   rather than bolting it on after.
