"""
Pydantic schemas -- request/response contracts, matching API_DESIGN.md.

Separate from app/models.py (the DB/ORM layer) on purpose: schemas are
what the API exposes to clients, models are what's stored. Keeping
them apart means we control exactly what a request can set (e.g. a
client can't set `id`) and exactly what a response reveals.
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StudentCreate(BaseModel):
    """What a client sends to create a student. No `id` -- the DB assigns it."""

    roll_number: str = Field(min_length=1, max_length=20, examples=["24BCE5285"])
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    department: str = Field(min_length=1, max_length=80)
    semester: int = Field(ge=1, le=12)


class StudentUpdate(BaseModel):
    """
    Partial update -- every field optional, so a client only sends what's
    actually changing. `id` is never editable; it isn't listed here.
    """

    roll_number: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr | None = None
    department: str | None = Field(default=None, min_length=1, max_length=80)
    semester: int | None = Field(default=None, ge=1, le=12)


class StudentResponse(BaseModel):
    """What the API returns after creating (or fetching) a student."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    roll_number: str
    name: str
    email: EmailStr
    department: str
    semester: int


class PaginatedStudents(BaseModel):
    """Envelope for GET /students -- items plus enough info to page through the rest."""

    items: list[StudentResponse]
    total: int
    limit: int
    offset: int


class UserCreate(BaseModel):
    """What a client sends to register. No `role` here -- see note in auth router."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: str
    is_active: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
