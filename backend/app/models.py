"""Mô hình dữ liệu.

- Khung năng lực (Competency) là dữ liệu trung tâm: JD, chấm CV, phỏng vấn đều bám theo nó.
- Tổ chức có 2 loại: company (HR, quản lý, người phỏng vấn, trưởng nhóm tuyển dụng, nhân viên)
  và school (cố vấn hướng nghiệp, sinh viên).
"""

import enum
import secrets
import string
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

EMBEDDING_DIM = 1024


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def new_join_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Role(str, enum.Enum):
    student = "student"            # EDU-17
    advisor = "advisor"            # EDU-17: cố vấn hướng nghiệp
    hr = "hr"                      # BO-15 soạn JD, BO-16 phân tích khảo sát
    manager = "manager"            # BO-15: quản lý phê duyệt JD
    interviewer = "interviewer"    # BO-17: người phỏng vấn
    hiring_lead = "hiring_lead"    # BO-17: trưởng nhóm tuyển dụng
    employee = "employee"          # BO-16: nhân viên trả lời khảo sát
    admin = "admin"


COMPANY_ROLES = {Role.hr, Role.manager, Role.interviewer, Role.hiring_lead, Role.employee}
SCHOOL_ROLES = {Role.advisor, Role.student}
ORG_CREATOR_ROLES = {Role.hr: "company", Role.advisor: "school"}


class JobStatus(str, enum.Enum):
    draft = "draft"
    pending_approval = "pending_approval"
    rejected = "rejected"
    published = "published"   # đã duyệt & ban hành
    closed = "closed"


class InterviewMode(str, enum.Enum):
    mock = "mock"
    real = "real"


class InterviewStatus(str, enum.Enum):
    in_progress = "in_progress"
    completed = "completed"


# ---------------------------------------------------------------- Tổ chức & người dùng

class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default="company")  # company | school
    join_code: Mapped[str] = mapped_column(String(12), unique=True, default=new_join_code)
    # BO-15: "memory phong cách thương hiệu" dùng mỗi khi AI soạn JD
    brand_voice: Mapped[str] = mapped_column(Text, default="")
    # BO-15: số cấp phê duyệt JD (HITL nhiều cấp)
    jd_approval_levels: Mapped[int] = mapped_column(Integer, default=1)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), default=Role.student)
    org_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"))
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # EDU-17: sinh viên đồng ý cho cố vấn xem báo cáo
    share_with_advisor: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ---------------------------------------------------------------- BO-15: JD & năng lực

class Competency(TimestampMixin, Base):
    """Từ điển năng lực của tổ chức. rubric: {"levels": [{level, descriptor}]}"""

    __tablename__ = "competencies"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50), default="technical")
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
    department: Mapped[str] = mapped_column(String(120), default="")
    job_family: Mapped[str] = mapped_column(String(120), default="")
    headcount: Mapped[int] = mapped_column(Integer, default=1)
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), default=JobStatus.draft
    )
    bias_issues: Mapped[list] = mapped_column(JSONB, default=list)
    # Ngân hàng câu hỏi phỏng vấn + tiêu chí chấm sinh từ JD (dùng cho BO-17)
    question_bank: Mapped[list] = mapped_column(JSONB, default=list)
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
    required_level: Mapped[int] = mapped_column(Integer, default=3)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    jd: Mapped[JobDescription] = relationship(back_populates="competencies")
    competency: Mapped[Competency] = relationship(lazy="joined")


class JDApproval(TimestampMixin, Base):
    """Mỗi lượt duyệt/từ chối của quản lý (HITL nhiều cấp)."""

    __tablename__ = "jd_approvals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jd_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_descriptions.id", ondelete="CASCADE"), index=True
    )
    level: Mapped[int] = mapped_column(Integer)
    approver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(20))  # approved | rejected | submitted
    comment: Mapped[str] = mapped_column(Text, default="")


class HeadcountPlan(TimestampMixin, Base):
    """Định biên được duyệt theo phòng ban/nhóm vị trí (thông tin mật của tổ chức)."""

    __tablename__ = "headcount_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    department: Mapped[str] = mapped_column(String(120))
    job_family: Mapped[str] = mapped_column(String(120))
    approved: Mapped[int] = mapped_column(Integer)
    filled: Mapped[int] = mapped_column(Integer, default=0)


# ---------------------------------------------------------------- EDU-17: CV & phỏng vấn thử

class CV(TimestampMixin, Base):
    __tablename__ = "cvs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    raw_text: Mapped[str] = mapped_column(Text)
    redacted_text: Mapped[str] = mapped_column(Text)
    parsed: Mapped[dict] = mapped_column(JSONB, default=dict)


class CVAssessment(TimestampMixin, Base):
    __tablename__ = "cv_assessments"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    cv_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cvs.id", ondelete="CASCADE"), index=True)
    jd_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_descriptions.id", ondelete="CASCADE"))
    overall_score: Mapped[float] = mapped_column(Float)
    ats_score: Mapped[float] = mapped_column(Float, default=0)
    ats: Mapped[dict] = mapped_column(JSONB, default=dict)
    result: Mapped[dict] = mapped_column(JSONB)
    model_used: Mapped[str] = mapped_column(String(100))


class InterviewSession(TimestampMixin, Base):
    __tablename__ = "interview_sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    jd_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_descriptions.id", ondelete="CASCADE"))
    mode: Mapped[InterviewMode] = mapped_column(
        Enum(InterviewMode, name="interview_mode"), default=InterviewMode.mock
    )
    round_type: Mapped[str] = mapped_column(String(30), default="behavioral")
    status: Mapped[InterviewStatus] = mapped_column(
        Enum(InterviewStatus, name="interview_status"), default=InterviewStatus.in_progress
    )
    turns: Mapped[list] = mapped_column(JSONB, default=list)
    summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    average_score: Mapped[float | None] = mapped_column(Float, nullable=True)


class AdvisorNote(TimestampMixin, Base):
    """EDU-17 HITL: cố vấn nhận xét báo cáo của sinh viên."""

    __tablename__ = "advisor_notes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    advisor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    target_type: Mapped[str] = mapped_column(String(30), default="general")
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content: Mapped[str] = mapped_column(Text)


# ---------------------------------------------------------------- Chất lượng & chi phí (dùng chung)

class Feedback(TimestampMixin, Base):
    """CSAT: người dùng chấm 1-5 cho một kết quả AI."""

    __tablename__ = "feedback"
    __table_args__ = (UniqueConstraint("user_id", "target_type", "target_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    org_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"))
    target_type: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[str] = mapped_column(String(64))
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, default="")


class QualityEval(TimestampMixin, Base):
    """LLM-as-Judge: đánh giá chất lượng phản hồi AI."""

    __tablename__ = "quality_evals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"))
    target_type: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[str] = mapped_column(String(64), index=True)
    scores: Mapped[dict] = mapped_column(JSONB)
    overall: Mapped[float] = mapped_column(Float)
    issues: Mapped[list] = mapped_column(JSONB, default=list)
    judge_model: Mapped[str] = mapped_column(String(100))


class LLMUsage(TimestampMixin, Base):
    __tablename__ = "llm_usage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    org_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    feature: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0)


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100))
    target: Mapped[str] = mapped_column(String(200))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)


# ---------------------------------------------------------------- BO-17: phỏng vấn ứng viên thật

class Candidate(TimestampMixin, Base):
    """Ứng viên của một JD: do HR/trưởng nhóm nhập (source=manual) hoặc tự ứng tuyển trên sàn (source=applied)."""

    __tablename__ = "candidates"
    __table_args__ = (UniqueConstraint("jd_id", "applicant_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    source: Mapped[str] = mapped_column(String(20), default="manual")
    applicant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    cv_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cvs.id", ondelete="SET NULL"), nullable=True)
    cover_note: Mapped[str] = mapped_column(Text, default="")
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    jd_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_descriptions.id"))
    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(255), default="")
    cv_text: Mapped[str] = mapped_column(Text, default="")  # đã che PII
    stage: Mapped[str] = mapped_column(String(30), default="interviewing")
    # Memory hồ sơ ứng viên qua các vòng: [{round_no, name, summary, gaps}]
    profile_memory: Mapped[list] = mapped_column(JSONB, default=list)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class InterviewRound(TimestampMixin, Base):
    __tablename__ = "interview_rounds"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    round_no: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    focus_competencies: Mapped[list] = mapped_column(JSONB, default=list)
    questions: Mapped[list] = mapped_column(JSONB, default=list)
    interviewer_ids: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | closed
    aggregate: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    recommendation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class Scorecard(TimestampMixin, Base):
    __tablename__ = "scorecards"
    __table_args__ = (UniqueConstraint("round_id", "interviewer_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    round_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interview_rounds.id", ondelete="CASCADE"), index=True
    )
    interviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    scores: Mapped[list] = mapped_column(JSONB, default=list)  # [{competency, score, evidence}]
    question_notes: Mapped[list] = mapped_column(JSONB, default=list)  # [{index, notes, asked}]
    raw_notes: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(String(20), default="")
    bias_flags: Mapped[list] = mapped_column(JSONB, default=list)
    submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class HiringDecision(TimestampMixin, Base):
    __tablename__ = "hiring_decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    decision: Mapped[str] = mapped_column(String(20))  # hire | reject | hold
    rationale: Mapped[str] = mapped_column(Text)
    committee: Mapped[list] = mapped_column(JSONB, default=list)
    followed_ai: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    decided_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


# ---------------------------------------------------------------- BO-16: khảo sát gắn kết

class Survey(TimestampMixin, Base):
    __tablename__ = "surveys"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    period_label: Mapped[str] = mapped_column(String(50), default="")
    # [{id, type: likert|text, text, dimension}]
    questions: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | open | closed
    analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class SurveyParticipation(Base):
    """Chỉ ghi nhận AI đã trả lời (chống trả lời 2 lần), KHÔNG liên kết với nội dung trả lời."""

    __tablename__ = "survey_participations"
    survey_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("surveys.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)


class SurveyResponse(Base):
    """Phản hồi ẩn danh: không có user_id, không có giờ phút."""

    __tablename__ = "survey_responses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    survey_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("surveys.id", ondelete="CASCADE"), index=True
    )
    department: Mapped[str] = mapped_column(String(120), default="Chưa rõ")
    answers: Mapped[dict] = mapped_column(JSONB)  # {question_id: số 1-5 | văn bản đã che PII}
    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    topics: Mapped[list] = mapped_column(JSONB, default=list)
    risk_signal: Mapped[bool] = mapped_column(Boolean, default=False)


class SurveyInsight(TimestampMixin, Base):
    __tablename__ = "survey_insights"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    survey_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("surveys.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))  # theme | risk | strength
    title: Mapped[str] = mapped_column(String(300))
    detail: Mapped[str] = mapped_column(Text)
    departments: Mapped[list] = mapped_column(JSONB, default=list)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    suggested_actions: Mapped[list] = mapped_column(JSONB, default=list)
    selected_actions: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected
    hr_note: Mapped[str] = mapped_column(Text, default="")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class TopicMemory(TimestampMixin, Base):
    """Memory chủ đề qua các kỳ khảo sát: chủ đề lặp lại ≥2 kỳ = tồn đọng."""

    __tablename__ = "topic_memory"
    __table_args__ = (UniqueConstraint("org_id", "topic"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    topic: Mapped[str] = mapped_column(String(200))
    occurrences: Mapped[int] = mapped_column(Integer, default=1)
    last_survey_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    history: Mapped[list] = mapped_column(JSONB, default=list)  # [{survey_id, period, count, negative}]
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | resolved
