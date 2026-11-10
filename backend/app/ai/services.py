"""Các tác vụ AI nghiệp vụ. Mỗi hàm có dữ liệu mẫu (mock) để chạy thử khi chưa có API key."""

import json

from app.ai import prompts
from app.ai.llm import generate
from app.ai.schemas import (
    AnswerFeedback,
    CompetencyDraft,
    CompetencyScore,
    CompetencySummary,
    CVAssessmentResult,
    CVSuggestion,
    ExperienceItem,
    InterviewQuestion,
    InterviewQuestionSet,
    InterviewSummary,
    JDDraft,
    ParsedCV,
    RubricLevel,
)


def _rubric(name: str) -> list[RubricLevel]:
    labels = ["Mới làm quen", "Cơ bản", "Thành thạo", "Nâng cao", "Chuyên gia"]
    return [RubricLevel(level=i + 1, descriptor=f"{name}: {lbl}") for i, lbl in enumerate(labels)]


# ---------- BO-15: JD & khung năng lực ----------

def draft_jd(title: str, level: str, context: str) -> JDDraft:
    prompt = f"Vị trí: {title}\nCấp độ: {level}\nThông tin bổ sung từ HR:\n{context or '(không có)'}"

    def mock() -> JDDraft:
        names = [("Python", "technical"), ("SQL & dữ liệu", "technical"),
                 ("Giải quyết vấn đề", "soft"), ("Giao tiếp", "soft"), ("Làm việc nhóm", "soft")]
        return JDDraft(
            title=title,
            summary=f"[MẪU] Tuyển {title} cấp {level}.",
            responsibilities=["Phát triển tính năng mới", "Viết test và tài liệu"],
            requirements=["Tốt nghiệp CNTT hoặc tương đương", "Có dự án cá nhân/thực tập"],
            nice_to_have=["Biết Docker"],
            competencies=[
                CompetencyDraft(name=n, category=c, description=f"Năng lực {n}",
                                required_level=3, weight=1.0, rubric=_rubric(n))
                for n, c in names
            ],
        )

    return generate(tier="fast", system=prompts.JD_SYSTEM, prompt=prompt, output=JDDraft, mock=mock)


# ---------- EDU-17: phân tích & chấm CV ----------

def parse_cv(redacted_text: str) -> ParsedCV:
    def mock() -> ParsedCV:
        return ParsedCV(
            headline="[MẪU] Sinh viên năm cuối CNTT",
            skills=["Python", "SQL", "Git"],
            education=["Đại học (ẩn tên)"],
            experience=[ExperienceItem(role="Thực tập sinh", organization="Công ty A",
                                       duration="3 tháng", highlights=["Viết API nội bộ"])],
            projects=["Website quản lý thư viện"],
            certifications=[],
        )

    return generate(tier="fast", system=prompts.CV_PARSE_SYSTEM,
                    prompt=f"<cv>\n{redacted_text}\n</cv>", output=ParsedCV, mock=mock)


def _framework_text(competencies: list[dict]) -> str:
    return json.dumps(competencies, ensure_ascii=False, indent=1)


def assess_cv(redacted_text: str, jd_text: str, competencies: list[dict]) -> CVAssessmentResult:
    prompt = (
        f"<jd>\n{jd_text}\n</jd>\n\n"
        f"<khung_nang_luc>\n{_framework_text(competencies)}\n</khung_nang_luc>\n\n"
        f"<cv>\n{redacted_text}\n</cv>\n\n"
        "Chấm từng năng lực trong khung (dùng đúng tên năng lực), rồi đưa gợi ý sửa CV."
    )

    def mock() -> CVAssessmentResult:
        return CVAssessmentResult(
            overall_comment="[MẪU] CV có nền tảng kỹ thuật, cần thêm số liệu kết quả.",
            competency_scores=[
                CompetencyScore(competency=c["name"], score=min(c["required_level"], 3),
                                evidence="(dữ liệu mẫu)", gap="" if c["required_level"] <= 3
                                else "Cần thêm dự án thể hiện mức cao hơn")
                for c in competencies
            ],
            strengths=["Có kinh nghiệm thực tập"],
            gaps=["Thiếu số liệu đo lường kết quả"],
            suggestions=[CVSuggestion(section="Kinh nghiệm", issue="Mô tả chung chung",
                                      suggestion="Dùng động từ hành động và số liệu",
                                      example_rewrite="Xây 5 API REST phục vụ 200 người dùng nội bộ")],
        )

    return generate(tier="smart", system=prompts.CV_ASSESS_SYSTEM, prompt=prompt,
                    output=CVAssessmentResult, mock=mock)


def weighted_score(scores: list[CompetencyScore], competencies: list[dict]) -> float:
    """Điểm tổng 0-100: mức đạt so với mức yêu cầu, có trọng số. Tính bằng code, không để AI tự cộng."""
    by_name = {s.competency.strip().lower(): s.score for s in scores}
    total_w = sum(c["weight"] for c in competencies) or 1.0
    acc = 0.0
    for c in competencies:
        got = by_name.get(c["name"].strip().lower(), 0)
        acc += c["weight"] * min(got / max(c["required_level"], 1), 1.0)
    return round(acc / total_w * 100, 1)


# ---------- EDU-17 / BO-17: phỏng vấn ----------

def generate_questions(jd_text: str, competencies: list[dict], count: int) -> InterviewQuestionSet:
    prompt = (f"<jd>\n{jd_text}\n</jd>\n<khung_nang_luc>\n{_framework_text(competencies)}\n"
              f"</khung_nang_luc>\nTạo {count} câu hỏi, ưu tiên năng lực có trọng số cao.")

    def mock() -> InterviewQuestionSet:
        return InterviewQuestionSet(questions=[
            InterviewQuestion(question=f"[MẪU] Kể về một lần bạn thể hiện năng lực {c['name']}.",
                              competency=c["name"],
                              what_good_looks_like="Có bối cảnh, hành động cụ thể, kết quả đo được")
            for c in competencies[:count]
        ])

    return generate(tier="fast", system=prompts.QUESTION_SYSTEM, prompt=prompt,
                    output=InterviewQuestionSet, mock=mock)


def feedback_answer(question: dict, answer: str, rubric: list | dict) -> AnswerFeedback:
    prompt = (f"Năng lực: {question['competency']}\n"
              f"Rubric: {json.dumps(rubric, ensure_ascii=False)}\n"
              f"Câu hỏi: {question['question']}\n"
              f"Câu trả lời tốt cần có: {question.get('what_good_looks_like', '')}\n"
              f"<cau_tra_loi>\n{answer}\n</cau_tra_loi>")

    def mock() -> AnswerFeedback:
        return AnswerFeedback(score=3, feedback="[MẪU] Câu trả lời có ý, nhưng thiếu kết quả cụ thể.",
                              better_answer_hint="Trả lời theo STAR và nêu số liệu kết quả.")

    return generate(tier="smart", system=prompts.ANSWER_FEEDBACK_SYSTEM, prompt=prompt,
                    output=AnswerFeedback, mock=mock)


def summarize_interview(turns: list[dict]) -> InterviewSummary:
    prompt = f"<buoi_phong_van>\n{json.dumps(turns, ensure_ascii=False, indent=1)}\n</buoi_phong_van>"

    def mock() -> InterviewSummary:
        groups: dict[str, list[int]] = {}
        for t in turns:
            if t.get("score") is not None:
                groups.setdefault(t["competency"], []).append(t["score"])
        return InterviewSummary(
            overall="[MẪU] Bạn trả lời khá ổn, cần luyện thêm cấu trúc STAR.",
            per_competency=[CompetencySummary(competency=k, average_score=sum(v) / len(v),
                                              comment="(dữ liệu mẫu)") for k, v in groups.items()],
            next_steps=["Chuẩn bị 3 câu chuyện STAR", "Luyện nói có số liệu"],
        )

    return generate(tier="fast", system=prompts.INTERVIEW_SUMMARY_SYSTEM, prompt=prompt,
                    output=InterviewSummary, mock=mock)
