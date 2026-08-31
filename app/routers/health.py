"""
Health check endpoint.

Used for local dev checks, container orchestration liveness probes,
and CI smoke tests once this is deployed.
"""

from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    """Return service status, name, version, and current UTC timestamp."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
