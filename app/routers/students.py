"""
Student API endpoints.

Provides student CRUD operations with:

- JWT authentication
- Role-based authorization
- Student resource ownership
- Search and filtering
- Pagination
- Consistent error handling
- Structured logging
- Safe transaction rollback
- OpenAPI documentation metadata
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
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


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/students",
    tags=["Students"],
)


@router.post(
    "",
    response_model=StudentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create student",
    description=(
        "Create a new student record. "
        "Student users can only create a record for their own account. "
        "Faculty and admin users can create student records."
    ),
    responses={
        201: {
            "description": "Student created successfully",
        },
        403: {
            "description": "User is not allowed to create this record",
        },
        409: {
            "description": "Email or roll number already exists",
        },
        500: {
            "description": "Internal database error",
        },
    },
)
async def create_student(
    payload: StudentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Student:
    """
    Create a student record.
    """

    if (
        current_user.role == "student"
        and payload.email != current_user.email
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You can only create a student record "
                "for your own account."
            ),
        )

    try:
        student = await student_service.create_student(
            db=db,
            student_data=payload.model_dump(),
        )

        logger.info(
            "Student created successfully | student_id=%s",
            student.id,
        )

        return student

    except IntegrityError:
        await db.rollback()

        logger.warning(
            "Student creation conflict | email=%s",
            payload.email,
        )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A student with this roll_number "
                "or email already exists."
            ),
        )

    except SQLAlchemyError:
        await db.rollback()

        logger.exception(
            "Unexpected database error while creating student",
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal database error occurred.",
        )


@router.get(
    "",
    response_model=PaginatedStudents,
    summary="List students",
    description=(
        "Retrieve students using optional search, department, "
        "semester, limit, and offset filters. "
        "Student users can only see their own record."
    ),
    responses={
        200: {
            "description": "Students retrieved successfully",
        },
        401: {
            "description": "Authentication required",
        },
        500: {
            "description": "Internal database error",
        },
    },
)
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
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of students to return",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of records to skip",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedStudents:
    """
    List students with authorization and filtering.
    """

    email = (
        current_user.email
        if current_user.role == "student"
        else None
    )

    try:
        students, total = await student_service.list_students(
            db=db,
            search=search,
            department=department,
            semester=semester,
            email=email,
            limit=limit,
            offset=offset,
        )

        logger.info(
            "Students listed successfully | "
            "total=%s | limit=%s | offset=%s",
            total,
            limit,
            offset,
        )

        return PaginatedStudents(
            items=students,
            total=total,
            limit=limit,
            offset=offset,
        )

    except SQLAlchemyError:
        await db.rollback()

        logger.exception(
            "Unexpected database error while listing students",
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal database error occurred.",
        )


@router.get(
    "/{student_id}",
    response_model=StudentResponse,
    summary="Get student by ID",
    description=(
        "Retrieve a student by ID. "
        "Student users can only retrieve their own record, "
        "while faculty and admin users can retrieve any record."
    ),
    responses={
        200: {
            "description": "Student retrieved successfully",
        },
        404: {
            "description": "Student not found",
        },
        500: {
            "description": "Internal database error",
        },
    },
)
async def get_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Student:
    """
    Retrieve a student by ID.
    """

    email = (
        current_user.email
        if current_user.role == "student"
        else None
    )

    try:
        student = await student_service.get_student(
            db=db,
            student_id=student_id,
            email=email,
        )

    except SQLAlchemyError:
        await db.rollback()

        logger.exception(
            "Unexpected database error while retrieving student "
            "| student_id=%s",
            student_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal database error occurred.",
        )

    if student is None:
        logger.warning(
            "Student not found | student_id=%s",
            student_id,
        )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with id {student_id} not found.",
        )

    logger.info(
        "Student retrieved successfully | student_id=%s",
        student_id,
    )

    return student


@router.patch(
    "/{student_id}",
    response_model=StudentResponse,
    summary="Update student",
    description=(
        "Update an existing student record. "
        "Student users can only update their own record "
        "and cannot change record ownership."
    ),
    responses={
        200: {
            "description": "Student updated successfully",
        },
        403: {
            "description": "User cannot modify this record",
        },
        404: {
            "description": "Student not found",
        },
        409: {
            "description": "Email or roll number already exists",
        },
        500: {
            "description": "Internal database error",
        },
    },
)
async def update_student(
    student_id: int,
    payload: StudentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Student:
    """
    Update a student record.
    """

    email = (
        current_user.email
        if current_user.role == "student"
        else None
    )

    try:
        student = await student_service.get_student(
            db=db,
            student_id=student_id,
            email=email,
        )

        if student is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student with id {student_id} not found.",
            )

        updates = payload.model_dump(
            exclude_unset=True,
        )

        if current_user.role == "student":
            if (
                "email" in updates
                and updates["email"] != current_user.email
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "You cannot change the ownership "
                        "of your student record."
                    ),
                )

        updated_student = await student_service.update_student(
            db=db,
            student=student,
            updates=updates,
        )

        logger.info(
            "Student updated successfully | student_id=%s",
            student_id,
        )

        return updated_student

    except IntegrityError:
        await db.rollback()

        logger.warning(
            "Student update conflict | student_id=%s",
            student_id,
        )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or roll number already exists.",
        )

    except SQLAlchemyError:
        await db.rollback()

        logger.exception(
            "Unexpected database error while updating student "
            "| student_id=%s",
            student_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal database error occurred.",
        )


@router.delete(
    "/{student_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete student",
    description=(
        "Delete a student record. "
        "The operation may be blocked if the student has "
        "dependent attendance or leave records."
    ),
    responses={
        204: {
            "description": "Student deleted successfully",
        },
        404: {
            "description": "Student not found",
        },
        409: {
            "description": (
                "Student cannot be deleted because dependent "
                "records exist"
            ),
        },
        500: {
            "description": "Internal database error",
        },
    },
)
async def delete_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Delete a student record.
    """

    email = (
        current_user.email
        if current_user.role == "student"
        else None
    )

    try:
        student = await student_service.get_student(
            db=db,
            student_id=student_id,
            email=email,
        )

        if student is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student with id {student_id} not found.",
            )

        await student_service.delete_student(
            db=db,
            student=student,
        )

        logger.info(
            "Student deleted successfully | student_id=%s",
            student_id,
        )

    except ValueError as exc:
        await db.rollback()

        logger.warning(
            "Student deletion blocked | student_id=%s",
            student_id,
        )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    except SQLAlchemyError:
        await db.rollback()

        logger.exception(
            "Unexpected database error while deleting student "
            "| student_id=%s",
            student_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal database error occurred.",
        )