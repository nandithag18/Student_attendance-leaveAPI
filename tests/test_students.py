from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.main import app
from app.auth import get_current_user
from app.database import get_db


class FakeDB:
    def __init__(self):
        self.rollback = AsyncMock()


def override_get_db():
    yield FakeDB()


def faculty_user():
    return SimpleNamespace(
        id=2,
        email="faculty@example.com",
        role="faculty",
    )


def student_user():
    return SimpleNamespace(
        id=1,
        email="student@example.com",
        role="student",
    )


student_record = SimpleNamespace(
    id=1,
    name="Nanditha",
    email="student@example.com",
    roll_number="24BCE001",
    department="CSE",
    semester=5,
)


@pytest.fixture(autouse=True)
def setup_dependencies():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db

    yield

    app.dependency_overrides.clear()


def test_create_student_success():
    app.dependency_overrides[get_current_user] = faculty_user

    payload = {
        "name": "Nanditha",
        "email": "student@example.com",
        "roll_number": "24BCE001",
        "department": "CSE",
        "semester": 5,
    }

    with patch(
        "app.routers.students.student_service.create_student",
        new_callable=AsyncMock,
        return_value=student_record,
    ) as mock_create:

        response = TestClient(app).post(
            "/students",
            json=payload,
        )

    assert response.status_code == 201
    assert response.json()["email"] == "student@example.com"
    mock_create.assert_awaited_once()


def test_create_student_validation_failure():
    app.dependency_overrides[get_current_user] = faculty_user

    invalid_payload = {
        "name": "",
        "email": "invalid-email",
        "roll_number": "",
        "department": "CSE",
        "semester": 0,
    }

    response = TestClient(app).post(
        "/students",
        json=invalid_payload,
    )

    assert response.status_code == 422


def test_student_cannot_create_record_for_another_user():
    app.dependency_overrides[get_current_user] = student_user

    payload = {
        "name": "Another Student",
        "email": "another@example.com",
        "roll_number": "24BCE002",
        "department": "CSE",
        "semester": 5,
    }

    response = TestClient(app).post(
        "/students",
        json=payload,
    )

    assert response.status_code == 403
    assert "own account" in response.json()["detail"]


def test_student_can_access_only_own_record():
    app.dependency_overrides[get_current_user] = student_user

    with patch(
        "app.routers.students.student_service.get_student",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock_get:

        response = TestClient(app).get("/students/99")

    assert response.status_code == 404

    mock_get.assert_awaited_once_with(
        db=mock_get.await_args.kwargs["db"],
        student_id=99,
        email="student@example.com",
    )


def test_faculty_can_access_any_student_record():
    app.dependency_overrides[get_current_user] = faculty_user

    with patch(
        "app.routers.students.student_service.get_student",
        new_callable=AsyncMock,
        return_value=student_record,
    ) as mock_get:

        response = TestClient(app).get("/students/1")

    assert response.status_code == 200
    assert response.json()["id"] == 1

    mock_get.assert_awaited_once_with(
        db=mock_get.await_args.kwargs["db"],
        student_id=1,
        email=None,
    )


def test_student_cannot_change_record_owner():
    app.dependency_overrides[get_current_user] = student_user

    payload = {
        "email": "another@example.com",
    }

    with patch(
        "app.routers.students.student_service.get_student",
        new_callable=AsyncMock,
        return_value=student_record,
    ):

        response = TestClient(app).patch(
            "/students/1",
            json=payload,
        )

    assert response.status_code == 403
    assert "ownership" in response.json()["detail"]


def test_service_failure_returns_500_and_rolls_back():
    app.dependency_overrides[get_current_user] = faculty_user

    fake_db = FakeDB()

    def override_failed_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_failed_db

    with patch(
        "app.routers.students.student_service.get_student",
        new_callable=AsyncMock,
        return_value=student_record,
    ), patch(
        "app.routers.students.student_service.delete_student",
        new_callable=AsyncMock,
        side_effect=SQLAlchemyError("Database failure"),
    ):

        response = TestClient(app).delete("/students/1")

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "An internal database error occurred."
    )

    fake_db.rollback.assert_awaited_once()