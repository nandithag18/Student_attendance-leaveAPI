from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AttendanceRecord, LeaveRequest, Student


async def create_student(
    db: AsyncSession,
    student_data: dict,
) -> Student:
    student = Student(**student_data)
    db.add(student)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise

    await db.refresh(student)
    return student


async def list_students(
    db: AsyncSession,
    search: str | None = None,
    department: str | None = None,
    semester: int | None = None,
    email: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Student], int]:

    query = select(Student)

    if email:
        query = query.where(Student.email == email)

    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            Student.name.ilike(search_pattern)
            | Student.email.ilike(search_pattern)
            | Student.roll_number.ilike(search_pattern)
        )

    if department:
        query = query.where(Student.department == department)

    if semester is not None:
        query = query.where(Student.semester == semester)

    total = (
        await db.execute(
            select(func.count()).select_from(query.subquery())
        )
    ).scalar_one()

    result = await db.execute(
        query.order_by(Student.id.asc())
        .limit(limit)
        .offset(offset)
    )

    students = result.scalars().all()

    return students, total


async def get_student(
    db: AsyncSession,
    student_id: int,
    email: str | None = None,
) -> Student | None:

    query = select(Student).where(Student.id == student_id)

    if email:
        query = query.where(Student.email == email)

    result = await db.execute(query)

    return result.scalar_one_or_none()


async def update_student(
    db: AsyncSession,
    student: Student,
    updates: dict,
) -> Student:

    for field, value in updates.items():
        setattr(student, field, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise

    await db.refresh(student)

    return student


async def delete_student(
    db: AsyncSession,
    student: Student,
) -> None:

    attendance_count = (
        await db.execute(
            select(func.count())
            .select_from(AttendanceRecord)
            .where(AttendanceRecord.student_id == student.id)
        )
    ).scalar_one()

    leave_count = (
        await db.execute(
            select(func.count())
            .select_from(LeaveRequest)
            .where(LeaveRequest.student_id == student.id)
        )
    ).scalar_one()

    if attendance_count > 0 or leave_count > 0:
        raise ValueError(
            f"Cannot delete student {student.id}: "
            f"{attendance_count} attendance record(s) and "
            f"{leave_count} leave request(s) exist. Remove or "
            "reassign those first."
        )

    await db.delete(student)
    await db.commit()