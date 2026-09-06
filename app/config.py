"""
Application configuration.

Centralizes settings so they can later be overridden via environment
variables (e.g. when adding a database for attendance/leave records).
"""

from pydantic_settings import BaseSettings  # type: ignore[import-not-found]


class Settings(BaseSettings):
    app_name: str = "Student Attendance and Leave API"
    app_version: str = "0.1.0"
    environment: str = "development"
    database_url: str = (
        "postgresql+asyncpg://attendance_user:attendance_pass"
        "@localhost:5432/attendance_leave_db"
    )

    class Config:
        env_file = ".env"


settings = Settings()
