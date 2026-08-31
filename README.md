# Student Attendance and Leave API

FastAPI backend for tracking student attendance records and leave
requests. This initial milestone sets up the project skeleton, virtual
environment, and a health check endpoint. Attendance and leave
endpoints will be added under `app/routers/` in later milestones.

## Project structure

```
student-attendance-leave-api/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app entrypoint
│   ├── config.py         # Settings (app name, version, env)
│   └── routers/
│       ├── __init__.py
│       └── health.py     # GET /health
├── requirements.txt
├── .gitignore
└── README.md
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run locally

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.
Interactive docs (Swagger UI): `http://127.0.0.1:8000/docs`.

## Verify the health endpoint

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "Student Attendance and Leave API",
  "version": "0.1.0",
  "timestamp": "2026-08-31T14:37:02.234754+00:00"
}
```

## Next milestones

- Data models for students, attendance records, and leave requests
- Database integration (e.g. SQLite for dev, PostgreSQL for prod)
- CRUD endpoints under `app/routers/attendance.py` and
  `app/routers/leave.py`
- Auth (student vs. faculty/admin roles)
