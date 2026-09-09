"""
Student endpoints. POST/PATCH/DELETE require a signed-in user
(Depends(get_current_user)) -- GET endpoints stay open.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import AttendanceRecord, LeaveRequest, Student, User
from app.schemas import PaginatedStudents, StudentCreate, StudentResponse, StudentUpdate

router = APIRouter(prefix="/students", tags=["students"])


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    payload: StudentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Student:
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
    total = (await db.execute(select(func.count()).select_from(Student))).scalar_one()

    result = await db.execute(
        select(Student).order_by(Student.id.asc()).limit(limit).offset(offset)
    )
    students = result.scalars().all()

    return PaginatedStudents(items=students, total=total, limit=limit, offset=offset)


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(student_id: int, db: AsyncSession = Depends(get_db)) -> Student:
    student = await db.get(Student, student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with id {student_id} not found.",
        )
    return student


@router.patch("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: int,
    payload: StudentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Student:
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
async def delete_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
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
