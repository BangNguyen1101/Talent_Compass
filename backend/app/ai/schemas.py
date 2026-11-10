"""Định dạng đầu ra có cấu trúc mà AI phải trả về (structured outputs)."""

from pydantic import BaseModel, Field


class RubricLevel(BaseModel):
    level: int = Field(description="Mức 1-5")
    descriptor: str = Field(description="Biểu hiện hành vi quan sát được ở mức này")


class CompetencyDraft(BaseModel):
    name: str
    category: str = Field(description="technical | soft | domain")
    description: str
    required_level: int = Field(description="Mức yêu cầu 1-5 cho vị trí này")
    weight: float = Field(description="Trọng số 0.5-2.0, càng quan trọng càng cao")
    rubric: list[RubricLevel]


class JDDraft(BaseModel):
    title: str
    summary: str
    responsibilities: list[str]
    requirements: list[str]
    nice_to_have: list[str]
    competencies: list[CompetencyDraft]


class ExperienceItem(BaseModel):
    role: str
    organization: str
    duration: str
    highlights: list[str]


class ParsedCV(BaseModel):
    headline: str
    skills: list[str]
    education: list[str]
    experience: list[ExperienceItem]
    projects: list[str]
    certifications: list[str]


class CompetencyScore(BaseModel):
    competency: str = Field(description="Tên năng lực đúng như trong khung năng lực")
    score: int = Field(description="Mức đạt được 0-5 (0 = không có bằng chứng)")
    evidence: str = Field(description="Trích dẫn hoặc tóm tắt bằng chứng từ CV")
    gap: str = Field(description="Còn thiếu gì so với mức yêu cầu, rỗng nếu đã đạt")


class CVSuggestion(BaseModel):
    section: str
    issue: str
    suggestion: str
    example_rewrite: str


class CVAssessmentResult(BaseModel):
    overall_comment: str
    competency_scores: list[CompetencyScore]
    strengths: list[str]
    gaps: list[str]
    suggestions: list[CVSuggestion]


class InterviewQuestion(BaseModel):
    question: str
    competency: str
    what_good_looks_like: str


class InterviewQuestionSet(BaseModel):
    questions: list[InterviewQuestion]


class AnswerFeedback(BaseModel):
    score: int = Field(description="1-5 theo rubric của năng lực")
    feedback: str
    better_answer_hint: str


class CompetencySummary(BaseModel):
    competency: str
    average_score: float
    comment: str


class InterviewSummary(BaseModel):
    overall: str
    per_competency: list[CompetencySummary]
    next_steps: list[str]
