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
from app.models import AttendanceRecord, LeaveRequest, Student
from app.schemas import PaginatedStudents, StudentCreate, StudentResponse, StudentUpdate

router = APIRouter(prefix="/students", tags=["students"])


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    payload: StudentCreate, db: AsyncSession = Depends(get_db)
) -> Student:
    """
    Create a student.

    Validation: handled automatically by FastAPI/Pydantic via the
    `StudentCreate` schema before this function body even runs -- a
    malformed request (missing field, bad email, semester out of
    range) never reaches here; the client gets a 422 with details.

    Transactional write: `db.add()` only stages the object in memory.
    `db.commit()` is the actual transaction boundary -- either the
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
    elsewhere in the table between requests -- ordering by a
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


@router.patch("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: int, payload: StudentUpdate, db: AsyncSession = Depends(get_db)
) -> Student:
    """
    Partially update a student. Only fields present in the request
    body are changed -- omitted fields keep their current value.

    Validation: each provided field is checked by StudentUpdate before
    this runs (e.g. a bad email or out-of-range semester never reaches
    here -- 422 instead).

    Transactional write: same pattern as create -- changes are staged
    in memory, then committed as one transaction. If the update would
    violate a unique constraint (e.g. changing roll_number to one
    that's already taken by someone else), the whole update is rolled
    back and rejected with 409, rather than silently corrupting data
    or leaving a half-applied change.
    """
    student = await db.get(Student, student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with id {student_id} not found.",
        )

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(student, field, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Update conflicts with an existing student's roll_number or email.",
        )
    await db.refresh(student)
    return student


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(student_id: int, db: AsyncSession = Depends(get_db)) -> None:
    """
    Delete a student -- but only if they have no attendance or leave
    history.

    Data-integrity decision: deleting a student who already has
    attendance_records or leave_requests is blocked (409) rather than
    silently cascade-deleting that history. A student profile getting
    removed shouldn't take their entire academic record with it --
    that data may still matter for audits, grading, or disputes.
    If those records genuinely need to go, that should be a separate,
    deliberate action -- not an automatic side effect of this endpoint.
    """
    student = await db.get(Student, student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with id {student_id} not found.",
        )

    attendance_count = (
        await db.execute(
            select(func.count())
            .select_from(AttendanceRecord)
            .where(AttendanceRecord.student_id == student_id)
        )
    ).scalar_one()
    leave_count = (
        await db.execute(
            select(func.count())
            .select_from(LeaveRequest)
            .where(LeaveRequest.student_id == student_id)
        )
    ).scalar_one()

    if attendance_count > 0 or leave_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete student {student_id}: "
                f"{attendance_count} attendance record(s) and "
                f"{leave_count} leave request(s) exist. Remove or "
                "reassign those first."
            ),
        )

    await db.delete(student)
    await db.commit()
