"""Schema request/response của API."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import InterviewMode, InterviewStatus, JobStatus, Role


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth ---
class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.student
    organization_name: str | None = None  # bắt buộc với HR


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(ORM):
    id: uuid.UUID
    email: str
    full_name: str
    role: Role
    org_id: uuid.UUID | None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Jobs & competencies ---
class JDGenerateIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    level: str = "junior"
    context: str = Field(default="", max_length=5000)


class RubricLevelIO(BaseModel):
    level: int
    descriptor: str


class JDCompetencyIO(BaseModel):
    name: str
    category: str = "technical"
    description: str = ""
    required_level: int = Field(ge=1, le=5, default=3)
    weight: float = Field(ge=0.1, le=5, default=1.0)
    rubric: list[RubricLevelIO] = []


class JobIn(BaseModel):
    title: str
    level: str = "junior"
    content: str
    status: JobStatus = JobStatus.draft
    competencies: list[JDCompetencyIO]


class JobOut(BaseModel):
    id: uuid.UUID
    title: str
    level: str
    content: str
    status: JobStatus
    created_at: datetime
    competencies: list[JDCompetencyIO]


# --- CV ---
class CVOut(ORM):
    id: uuid.UUID
    filename: str
    parsed: dict
    created_at: datetime


class AssessIn(BaseModel):
    jd_id: uuid.UUID


class AssessmentOut(ORM):
    id: uuid.UUID
    cv_id: uuid.UUID
    jd_id: uuid.UUID
    overall_score: float
    result: dict
    model_used: str
    created_at: datetime


# --- Interview ---
class InterviewStartIn(BaseModel):
    jd_id: uuid.UUID
    question_count: int = Field(ge=1, le=10, default=5)
    mode: InterviewMode = InterviewMode.mock


class AnswerIn(BaseModel):
    answer: str = Field(min_length=1, max_length=5000)


class InterviewOut(ORM):
    id: uuid.UUID
    jd_id: uuid.UUID
    mode: InterviewMode
    status: InterviewStatus
    turns: list
    summary: dict | None
    created_at: datetime
