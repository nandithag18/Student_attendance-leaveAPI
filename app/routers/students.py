"""
Student endpoints.
All student operations require a signed-in user.
Student users can only access their own records.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Student, User
from app.schemas import (
    PaginatedStudents,
    StudentCreate,
    StudentResponse,
    StudentUpdate,
)
from app.services import student_service
router = APIRouter(prefix="/students", tags=["students"])


@router.post(
    "",
    response_model=StudentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_student(
    payload: StudentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Student:

    if current_user.role == "student" and payload.email != current_user.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create a student record for your own account.",
        )

    try:
        return await student_service.create_student(
            db,
            payload.model_dump(),
        )
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A student with this roll_number or email already exists.",
        )

    await db.refresh(student)
    return student


@router.get("", response_model=PaginatedStudents)
async def list_students(
    search: str | None = Query(
        default=None,
        description="Search by name, email, or roll number",
    ),
    department: str | None = Query(
        default=None,
        description="Filter by department",
    ),
    semester: int | None = Query(
        default=None,
        ge=1,
        le=12,
        description="Filter by semester",
    ),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedStudents:

    email = current_user.email if current_user.role == "student" else None

    students, total = await student_service.list_students(
        db=db,
        search=search,
        department=department,
        semester=semester,
        email=email,
        limit=limit,
        offset=offset,
    )

    return PaginatedStudents(
        items=students,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Student:

    email = current_user.email if current_user.role == "student" else None

    student = await student_service.get_student(
        db,
        student_id,
        email,
    )

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

    email = current_user.email if current_user.role == "student" else None

    student = await student_service.get_student(
        db,
        student_id,
        email,
    )

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with id {student_id} not found.",
        )

    updates = payload.model_dump(exclude_unset=True)

    if current_user.role == "student":
        if "email" in updates and updates["email"] != current_user.email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot change the ownership of your student record.",
            )

    try:
        return await student_service.update_student(
            db,
            student,
            updates,
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Update conflicts with an existing student's roll_number or email.",
        )


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:

    email = current_user.email if current_user.role == "student" else None

    student = await student_service.get_student(
        db,
        student_id,
        email,
    )

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with id {student_id} not found.",
        )

    try:
        await student_service.delete_student(
            db,
            student,
        )
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    await db.delete(student)
    await db.commit()