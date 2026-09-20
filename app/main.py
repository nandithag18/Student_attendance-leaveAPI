"""
Student Attendance and Leave API -- application entrypoint.

Run locally with:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from app.logging_config import setup_logging

from app.config import settings
from app.routers import auth, health, students

setup_logging()
app = FastAPI(
    title="Student Attendance and Leave API",
    description="""
REST API for managing students, attendance, and leave requests.

### Features
- JWT authentication
- Role-based access control
- Student CRUD operations
- Resource ownership authorization
- Search, filtering, and pagination
- Attendance and leave management
- Structured logging
- Error handling and transaction rollback

### Authentication
Use a JWT token in the following format:

Authorization: Bearer <access_token>

### Roles
- Student: Can access their own student record.
- Faculty: Can access student records.
- Admin: Can perform administrative operations.
""",
    version="1.0.0",
    contact={
        "name": "Student Attendance and Leave API Team",
    },
    license_info={
        "name": "MIT",
    },
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "Student Attendance Leave API"
    }
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(students.router)


@app.get("/")
def root() -> dict:
    return {"message": f"{settings.app_name} is running. See /docs for API docs."}
