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
    title=settings.app_name,
    version=settings.app_version,
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(students.router)


@app.get("/")
def root() -> dict:
    return {"message": f"{settings.app_name} is running. See /docs for API docs."}
