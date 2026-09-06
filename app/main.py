"""
Student Attendance and Leave API — application entrypoint.

Run locally with:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from app.config import settings
from app.routers import health, students

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.include_router(health.router)
app.include_router(students.router)


@app.get("/")
def root() -> dict:
    return {"message": f"{settings.app_name} is running. See /docs for API docs."}
