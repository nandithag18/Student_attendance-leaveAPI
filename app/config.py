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

    # Auth settings. jwt_secret_key MUST be overridden via .env in any
    # real deployment -- this default is only safe for local dev.
    jwt_secret_key: str = "dev-only-change-me-in-env-file"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    class Config:
        env_file = ".env"


settings = Settings()
