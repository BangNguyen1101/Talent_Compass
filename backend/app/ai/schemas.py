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
    content_markdown: str = Field(
        description="Toàn bộ JD dạng Markdown, cấu trúc mục tự chọn cho phù hợp vị trí (tiêu đề ##, gạch đầu dòng)"
    )
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


QUESTION_TYPES = "technical | situational | behavioral | case | motivation"


class ScoringGuide(BaseModel):
    weak: str = Field(description="Câu trả lời mức 1-2 trông như thế nào (cụ thể cho câu hỏi này)")
    solid: str = Field(description="Câu trả lời mức 3 trông như thế nào")
    strong: str = Field(description="Câu trả lời mức 4-5 trông như thế nào")


class InterviewQuestion(BaseModel):
    question: str
    competency: str
    type: str = Field(description=QUESTION_TYPES)
    what_good_looks_like: str
    follow_ups: list[str] = Field(description="1-2 câu hỏi đào sâu người phỏng vấn có thể hỏi tiếp")
    scoring_guide: ScoringGuide


class InterviewQuestionSet(BaseModel):
    questions: list[InterviewQuestion]


class AnswerFeedback(BaseModel):
    score: int = Field(description="1-5 theo rubric của năng lực")
    feedback: str
    better_answer_hint: str
    follow_up_question: str = Field(
        description="Câu hỏi đào sâu nếu câu trả lời còn mơ hồ/thiếu kết quả; chuỗi rỗng nếu không cần"
    )


# ---------- BO-15 ----------

class NeutralRewrite(BaseModel):
    content: str = Field(description="Toàn bộ nội dung JD đã viết lại trung tính")
    changes: list[str] = Field(description="Liệt kê ngắn từng chỗ đã sửa")


class QuestionBankItem(BaseModel):
    question: str
    competency: str
    type: str = Field(description=QUESTION_TYPES)
    good_signals: list[str] = Field(description="Dấu hiệu câu trả lời tốt, cụ thể theo câu hỏi")
    red_flags: list[str] = Field(description="Dấu hiệu đáng lo ngại, cụ thể theo câu hỏi")
    follow_ups: list[str] = Field(description="1-2 câu hỏi đào sâu")
    scoring_guide: ScoringGuide


class QuestionBank(BaseModel):
    items: list[QuestionBankItem]


# ---------- BO-17 ----------

class NoteScore(BaseModel):
    competency: str
    suggested_score: int = Field(description="0 nếu ghi chú không có bằng chứng cho năng lực này, ngược lại 1-5")
    evidence: str


class StructuredNotes(BaseModel):
    scores: list[NoteScore]
    summary: str


class HiringRecommendation(BaseModel):
    recommendation: str = Field(description="hire | no_hire | more_info")
    confidence: str = Field(description="low | medium | high")
    rationale: str
    strengths: list[str]
    concerns: list[str]
    probe_next_round: list[str] = Field(description="Điểm cần làm rõ ở vòng sau")


# ---------- BO-16 ----------

class SurveyQuestionDraft(BaseModel):
    type: str = Field(description="likert | text")
    text: str
    dimension: str = Field(description="Nhóm chủ đề, vd. Quản lý, Phát triển, Đãi ngộ")


class SurveyDraft(BaseModel):
    questions: list[SurveyQuestionDraft]


class ResponseLabel(BaseModel):
    index: int
    sentiment: str = Field(description="positive | neutral | negative")
    topics: list[str] = Field(description="1-3 chủ đề, chọn từ danh sách chủ đề nếu phù hợp")
    risk_signal: bool = Field(description="True nếu có dấu hiệu muốn nghỉ việc/kiệt sức rõ ràng")


class ResponseLabels(BaseModel):
    labels: list[ResponseLabel]


class InsightDraft(BaseModel):
    kind: str = Field(description="theme | risk | strength")
    title: str
    detail: str
    departments: list[str]
    priority: str = Field(description="high | medium | low")
    suggested_actions: list[str]


class InsightSet(BaseModel):
    insights: list[InsightDraft]


# ---------- Đánh giá chất lượng (LLM-as-Judge) ----------

class JudgeResult(BaseModel):
    specificity: int = Field(description="1-5: phản hồi cụ thể, bám nội dung thực")
    grounding: int = Field(description="1-5: không bịa chi tiết ngoài dữ liệu đầu vào")
    actionability: int = Field(description="1-5: người nhận biết cần làm gì tiếp")
    fairness: int = Field(description="1-5: không thiên vị, không dựa trên thuộc tính nhạy cảm")
    tone: int = Field(description="1-5: tôn trọng, khích lệ, rõ ràng")
    issues: list[str]


class CompetencySummary(BaseModel):
    competency: str
    average_score: float
    comment: str


class InterviewSummary(BaseModel):
    overall: str
    per_competency: list[CompetencySummary]
    next_steps: list[str]
