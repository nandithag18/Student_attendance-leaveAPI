"""
Student endpoints. POST /students is today's primary create workflow:
validate the request body (via StudentCreate), write it inside a
single DB transaction, and roll back cleanly on failure instead of
leaving a half-written row.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Student
from app.schemas import PaginatedStudents, StudentCreate, StudentResponse

router = APIRouter(prefix="/students", tags=["students"])


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    payload: StudentCreate, db: AsyncSession = Depends(get_db)
) -> Student:
    """
    Create a student.

    Validation: handled automatically by FastAPI/Pydantic via the
    `StudentCreate` schema before this function body even runs — a
    malformed request (missing field, bad email, semester out of
    range) never reaches here; the client gets a 422 with details.

    Transactional write: `db.add()` only stages the object in memory.
    `db.commit()` is the actual transaction boundary — either the
    INSERT fully succeeds, or (on IntegrityError, e.g. a duplicate
    roll_number/email) we roll back so nothing partial is left in
    the database, and return a clear 409 instead of a raw DB error.
    """
    student = Student(**payload.model_dump())
    db.add(student)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A student with this roll_number or email already exists.",
        )
    await db.refresh(student)
    return student


@router.get("", response_model=PaginatedStudents)
async def list_students(
    limit: int = Query(20, ge=1, le=100, description="Max items to return (1-100)"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedStudents:
    """
    List students, paginated.

    Stable ordering: always ordered by `id ASC`. `id` is a unique,
    monotonically increasing primary key, so the same offset/limit
    always returns the same page even if new rows are inserted
    elsewhere in the table between requests — ordering by a
    non-unique column (e.g. `name`) would risk rows shifting between
    pages or appearing twice.
    """
    total = (await db.execute(select(func.count()).select_from(Student))).scalar_one()

    result = await db.execute(
        select(Student).order_by(Student.id.asc()).limit(limit).offset(offset)
    )
    students = result.scalars().all()

    return PaginatedStudents(items=students, total=total, limit=limit, offset=offset)


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(student_id: int, db: AsyncSession = Depends(get_db)) -> Student:
    """Fetch one student by id, or a clear 404 if it doesn't exist."""
    student = await db.get(Student, student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with id {student_id} not found.",
        )
    return student
