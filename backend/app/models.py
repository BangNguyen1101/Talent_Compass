"""Mô hình dữ liệu. Khung năng lực (Competency) là dữ liệu trung tâm:
JD, chấm CV, phỏng vấn đều liên kết về đây."""

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

EMBEDDING_DIM = 1024


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Role(str, enum.Enum):
    student = "student"
    hr = "hr"
    admin = "admin"


class JobStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    closed = "closed"


class InterviewMode(str, enum.Enum):
    mock = "mock"  # sinh viên luyện tập (EDU-17)
    real = "real"  # HR phỏng vấn thật (BO-17)


class InterviewStatus(str, enum.Enum):
    in_progress = "in_progress"
    completed = "completed"


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), default=Role.student)
    org_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"))


class Competency(TimestampMixin, Base):
    """Một năng lực, ví dụ 'Giao tiếp' hay 'Python'. rubric: mô tả từng mức 1-5."""

    __tablename__ = "competencies"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50), default="technical")  # technical | soft | domain
    description: Mapped[str] = mapped_column(Text, default="")
    rubric: Mapped[dict] = mapped_column(JSONB, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)


class JobDescription(TimestampMixin, Base):
    __tablename__ = "job_descriptions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    level: Mapped[str] = mapped_column(String(50), default="junior")
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), default=JobStatus.draft
    )
    competencies: Mapped[list["JDCompetency"]] = relationship(
        back_populates="jd", cascade="all, delete-orphan", lazy="selectin"
    )


class JDCompetency(Base):
    __tablename__ = "jd_competencies"
    jd_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_descriptions.id", ondelete="CASCADE"), primary_key=True
    )
    competency_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("competencies.id", ondelete="CASCADE"), primary_key=True
    )
    required_level: Mapped[int] = mapped_column(Integer, default=3)  # 1-5
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    jd: Mapped[JobDescription] = relationship(back_populates="competencies")
    competency: Mapped[Competency] = relationship(lazy="joined")


class CV(TimestampMixin, Base):
    __tablename__ = "cvs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    raw_text: Mapped[str] = mapped_column(Text)
    redacted_text: Mapped[str] = mapped_column(Text)  # đã che PII, dùng để gửi cho AI
    parsed: Mapped[dict] = mapped_column(JSONB, default=dict)


class CVAssessment(TimestampMixin, Base):
    __tablename__ = "cv_assessments"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    cv_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cvs.id", ondelete="CASCADE"), index=True)
    jd_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_descriptions.id", ondelete="CASCADE"))
    overall_score: Mapped[float] = mapped_column(Float)  # 0-100
    result: Mapped[dict] = mapped_column(JSONB)  # điểm từng năng lực, điểm thiếu, gợi ý
    model_used: Mapped[str] = mapped_column(String(100))


class InterviewSession(TimestampMixin, Base):
    __tablename__ = "interview_sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    jd_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_descriptions.id", ondelete="CASCADE"))
    mode: Mapped[InterviewMode] = mapped_column(
        Enum(InterviewMode, name="interview_mode"), default=InterviewMode.mock
    )
    status: Mapped[InterviewStatus] = mapped_column(
        Enum(InterviewStatus, name="interview_status"), default=InterviewStatus.in_progress
    )
    # [{question, competency, answer, feedback, score}]
    turns: Mapped[list] = mapped_column(JSONB, default=list)
    summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class AuditLog(TimestampMixin, Base):
    """Truy vết mọi kết quả do AI tạo ra (AI đề xuất, con người quyết định)."""

    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100))
    target: Mapped[str] = mapped_column(String(200))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
