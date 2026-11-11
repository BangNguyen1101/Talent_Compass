"""Schema request/response của API."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import InterviewMode, InterviewStatus, JobStatus, Role


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- Auth & tổ chức
class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.student
    organization_name: str | None = None  # tạo tổ chức mới (HR -> công ty, cố vấn -> trường)
    join_code: str | None = None          # tham gia tổ chức có sẵn
    department: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(ORM):
    id: uuid.UUID
    email: str
    full_name: str
    role: Role
    org_id: uuid.UUID | None
    department: str | None
    share_with_advisor: bool


class MeUpdate(BaseModel):
    full_name: str | None = None
    department: str | None = None
    share_with_advisor: bool | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class OrgOut(ORM):
    id: uuid.UUID
    name: str
    kind: str
    join_code: str | None = None
    brand_voice: str
    jd_approval_levels: int


class OrgUpdate(BaseModel):
    name: str | None = None
    brand_voice: str | None = Field(default=None, max_length=4000)
    jd_approval_levels: int | None = Field(default=None, ge=0, le=3)


class MemberUpdate(BaseModel):
    role: Role | None = None
    department: str | None = None
    is_active: bool | None = None


class MemberOut(UserOut):
    is_active: bool
    created_at: datetime


class HeadcountIn(BaseModel):
    department: str
    job_family: str
    approved: int = Field(ge=0)
    filled: int = Field(ge=0, default=0)


class HeadcountOut(HeadcountIn, ORM):
    id: int


# ---------------------------------------------------------------- BO-15: JD
class JDGenerateIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    level: str = "junior"
    department: str = ""
    job_family: str = ""
    context: str = Field(default="", max_length=8000)


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
    department: str = ""
    job_family: str = ""
    headcount: int = Field(ge=1, le=500, default=1)
    content: str
    competencies: list[JDCompetencyIO]


class JobOut(BaseModel):
    id: uuid.UUID
    title: str
    level: str
    department: str
    job_family: str
    headcount: int
    content: str
    status: JobStatus
    created_at: datetime
    created_by: uuid.UUID
    org_id: uuid.UUID | None
    competencies: list[JDCompetencyIO]
    bias_issues: list
    question_bank: list
    approvals: list = []
    can_edit: bool = False
    company: str | None = None
    my_application: str | None = None  # trạng thái đơn ứng tuyển của chính người xem (sinh viên)
    internal: bool = False  # người xem là nhân sự công ty sở hữu JD


class JobCheckOut(BaseModel):
    bias: list[dict]
    consistency: list[dict]
    headcount: dict | None


class NeutralizeIn(BaseModel):
    content: str


class ReviewIn(BaseModel):
    decision: Literal["approved", "rejected"]
    comment: str = Field(default="", max_length=2000)


class StatusIn(BaseModel):
    status: Literal["closed", "draft"]


# ---------------------------------------------------------------- EDU-17: CV
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
    ats_score: float
    ats: dict
    result: dict
    model_used: str
    created_at: datetime


class ATSCompareIn(BaseModel):
    jd_ids: list[uuid.UUID] = Field(min_length=1, max_length=10)


# ---------------------------------------------------------------- EDU-17: phỏng vấn thử
class InterviewStartIn(BaseModel):
    jd_id: uuid.UUID
    question_count: int = Field(ge=1, le=10, default=5)
    round_type: Literal["screening", "behavioral", "technical", "final"] = "behavioral"


class AnswerIn(BaseModel):
    answer: str = Field(min_length=1, max_length=5000)


class InterviewOut(ORM):
    id: uuid.UUID
    jd_id: uuid.UUID
    mode: InterviewMode
    round_type: str
    status: InterviewStatus
    turns: list
    summary: dict | None
    average_score: float | None
    created_at: datetime


# ---------------------------------------------------------------- Chất lượng
class FeedbackIn(BaseModel):
    target_type: Literal["cv_assessment", "interview", "jd_draft", "hiring_recommendation",
                         "survey_insights", "question_bank"]
    target_id: str = Field(max_length=64)
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)


class AdvisorNoteIn(BaseModel):
    target_type: Literal["general", "cv_assessment", "interview"] = "general"
    target_id: str | None = None
    content: str = Field(min_length=1, max_length=4000)


# ---------------------------------------------------------------- BO-17
class CandidateIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: str = ""
    jd_id: uuid.UUID
    cv_text: str = Field(default="", max_length=30000)


class RoundIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    focus_competencies: list[str] = []
    interviewer_ids: list[uuid.UUID] = Field(min_length=1)
    question_count: int = Field(ge=1, le=12, default=6)


class ScoreItem(BaseModel):
    competency: str
    score: int | None = Field(default=None, ge=1, le=5)
    evidence: str = ""


class QuestionNote(BaseModel):
    index: int
    asked: bool = False
    notes: str = ""


class ScorecardIn(BaseModel):
    scores: list[ScoreItem]
    question_notes: list[QuestionNote] = []
    raw_notes: str = Field(default="", max_length=20000)
    recommendation: Literal["", "strong_no_hire", "no_hire", "hire", "strong_hire"] = ""
    submit: bool = False


class StructureNotesIn(BaseModel):
    raw_notes: str = Field(min_length=1, max_length=20000)


class DecisionIn(BaseModel):
    decision: Literal["hire", "reject", "hold"]
    rationale: str = Field(min_length=10, max_length=4000)
    committee: list[str] = []


# ---------------------------------------------------------------- BO-16
class SurveyQuestionIO(BaseModel):
    id: str = ""
    type: Literal["likert", "text"]
    text: str = Field(min_length=3, max_length=500)
    dimension: str = "Chung"


class SurveyIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = ""
    period_label: str = ""
    questions: list[SurveyQuestionIO] = Field(min_length=1, max_length=40)


class SurveyDraftIn(BaseModel):
    goal: str = Field(default="", max_length=2000)


class SurveyAnswerIn(BaseModel):
    answers: dict[str, int | str]


class InsightReviewIn(BaseModel):
    status: Literal["approved", "rejected"]
    selected_actions: list[str] = []
    hr_note: str = ""
