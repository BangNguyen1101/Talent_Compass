"""Tác vụ AI cho BO-15 (JD) và EDU-17 (CV, phỏng vấn thử).
Mỗi hàm có dữ liệu mẫu (mock) để chạy thử khi chưa có API key."""

import json
import re

from app.ai import mock_content, prompts
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
    NeutralRewrite,
    ParsedCV,
    QuestionBank,
    QuestionBankItem,
    RubricLevel,
)
from app.core.knowledge import ROUND_TYPES


def _rubric(name: str) -> list[RubricLevel]:
    labels = ["Mới làm quen", "Cơ bản, cần hướng dẫn", "Tự làm độc lập", "Thành thạo, hướng dẫn người khác",
              "Chuyên gia, định hướng cho tổ chức"]
    return [RubricLevel(level=i + 1, descriptor=f"{name}: {lbl}") for i, lbl in enumerate(labels)]


def _xml(tag: str, content: str) -> str:
    return f"<{tag}>\n{content}\n</{tag}>"


def _json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1)


# ================================================================ BO-15

def draft_jd(title: str, level: str, context: str, *, brand_voice: str = "",
             dictionary: list[str] | None = None, references: list[dict] | None = None) -> JDDraft:
    parts = [f"Vị trí: {title}", f"Cấp độ: {level}", _xml("yeu_cau_tu_hr", context or "(không có)")]
    if brand_voice:
        parts.append(_xml("phong_cach_thuong_hieu", brand_voice))
    if dictionary:
        parts.append(_xml("tu_dien_nang_luc", ", ".join(dictionary)))
    if references:
        parts.append(_xml("jd_tham_khao", _json(references)))
    prompt = "\n\n".join(parts)

    def mock() -> JDDraft:
        req = mock_content.LEVEL_REQ.get(level, 3)
        comps = mock_content.competencies(title, level, context, dictionary or [])
        return JDDraft(
            title=title,
            content_markdown=mock_content.jd_markdown(title, level, context, brand_voice),
            competencies=[CompetencyDraft(name=n, category=c, description=f"[MẪU] Năng lực {n} cho vị trí {title}",
                                          required_level=req, weight=1.5 if c == "technical" else 1.0,
                                          rubric=_rubric(n)) for n, c in comps],
        )

    return generate(feature="jd.draft", tier="fast", system=prompts.JD_SYSTEM, prompt=prompt,
                    output=JDDraft, mock=mock)


def neutral_rewrite(content: str, issues: list[dict]) -> NeutralRewrite:
    prompt = _xml("van_de", _json(issues)) + "\n\n" + _xml("jd", content)

    def mock() -> NeutralRewrite:
        out = content
        for i in issues:
            out = out.replace(i["excerpt"], "")
        out = re.sub(r"\n{3,}", "\n\n", out)
        return NeutralRewrite(content=out, changes=[f"[MẪU] Đã bỏ câu: {i['excerpt']}" for i in issues])

    return generate(feature="jd.neutral_rewrite", tier="fast", system=prompts.NEUTRAL_REWRITE_SYSTEM,
                    prompt=prompt, output=NeutralRewrite, mock=mock)


def question_bank(jd_text: str, level: str, competencies: list[dict]) -> QuestionBank:
    prompt = f"Cấp độ: {level}\n" + _xml("jd", jd_text) + "\n" + _xml("khung_nang_luc", _json(competencies))

    def mock() -> QuestionBank:
        items = mock_content.question_items(jd_text, competencies, len(competencies) * 2, "mixed")
        return QuestionBank(items=[QuestionBankItem(**i) for i in items])

    return generate(feature="jd.question_bank", tier="fast", system=prompts.QUESTION_BANK_SYSTEM,
                    prompt=prompt, output=QuestionBank, mock=mock)


# ================================================================ EDU-17: CV

def parse_cv(redacted_text: str) -> ParsedCV:
    def mock() -> ParsedCV:
        skills = re.findall(r"\b(Python|SQL|Java|JavaScript|React|Excel|Git|Docker|Figma|C\+\+)\b", redacted_text)
        return ParsedCV(headline="[MẪU] Ứng viên", skills=sorted(set(skills)), education=[],
                        experience=[ExperienceItem(role="(mẫu)", organization="", duration="", highlights=[])],
                        projects=[], certifications=[])

    return generate(feature="cv.parse", tier="fast", system=prompts.CV_PARSE_SYSTEM,
                    prompt=_xml("cv", redacted_text), output=ParsedCV, mock=mock)


def assess_cv(redacted_text: str, jd_text: str, competencies: list[dict], ats: dict) -> CVAssessmentResult:
    prompt = "\n\n".join([
        _xml("jd", jd_text), _xml("khung_nang_luc", _json(competencies)),
        _xml("ket_qua_ats", _json({k: ats[k] for k in ("matched_keywords", "missing_keywords", "sections")})),
        _xml("cv", redacted_text),
        "Chấm từng năng lực trong khung (dùng đúng tên năng lực), rồi đưa gợi ý sửa CV.",
    ])

    def mock() -> CVAssessmentResult:
        matched = {k.lower() for k in ats["matched_keywords"]}
        scores = []
        for c in competencies:
            got = min(c["required_level"], 3) if c["name"].lower() in matched else 1
            scores.append(CompetencyScore(
                competency=c["name"], score=got,
                evidence="CV có nhắc tới năng lực này" if got > 1 else "Chưa thấy bằng chứng rõ trong CV",
                gap="" if got >= c["required_level"] else f"Cần minh chứng mức {c['required_level']}"))
        return CVAssessmentResult(
            overall_comment="[MẪU] CV có nền tảng; cần làm rõ kết quả và bổ sung minh chứng cho kỹ năng JD yêu cầu.",
            competency_scores=scores,
            strengths=[f"Có từ khóa: {', '.join(ats['matched_keywords'][:5])}"] if ats["matched_keywords"] else [],
            gaps=[f"Thiếu minh chứng: {', '.join(ats['missing_keywords'][:5])}"] if ats["missing_keywords"] else [],
            suggestions=[
                CVSuggestion(section="Kinh nghiệm", issue="Mô tả nhiệm vụ chưa có kết quả",
                             suggestion="Dùng động từ hành động và nêu kết quả thật",
                             example_rewrite="Xây dựng 5 API phục vụ 200 người dùng nội bộ, giảm 30% thời gian xử lý"),
            ],
        )

    return generate(feature="cv.assess", tier="smart", system=prompts.CV_ASSESS_SYSTEM, prompt=prompt,
                    output=CVAssessmentResult, mock=mock)


def weighted_score(scores: list[CompetencyScore], competencies: list[dict]) -> float:
    """Điểm phù hợp 0-100: mức đạt so với mức yêu cầu, có trọng số. Tính bằng code."""
    by_name = {s.competency.strip().lower(): s.score for s in scores}
    total_w = sum(c["weight"] for c in competencies) or 1.0
    acc = 0.0
    for c in competencies:
        got = by_name.get(c["name"].strip().lower(), 0)
        acc += c["weight"] * min(got / max(c["required_level"], 1), 1.0)
    return round(acc / total_w * 100, 1)


# ================================================================ EDU-17: phỏng vấn thử

def generate_questions(jd_text: str, competencies: list[dict], count: int, round_type: str = "behavioral",
                       probe: list[str] | None = None) -> InterviewQuestionSet:
    parts = [f"Loại vòng: {round_type} — {ROUND_TYPES.get(round_type, '')}", _xml("jd", jd_text),
             _xml("khung_nang_luc", _json(competencies))]
    if probe:
        parts.append(_xml("diem_can_lam_ro", "\n".join(probe)))
    parts.append(f"Tạo {count} câu hỏi, ưu tiên năng lực có trọng số cao.")

    def mock() -> InterviewQuestionSet:
        items = mock_content.question_items(jd_text, competencies, count, round_type)
        return InterviewQuestionSet(questions=[InterviewQuestion(**i) for i in items])

    return generate(feature="interview.questions", tier="fast", system=prompts.QUESTION_SYSTEM,
                    prompt="\n\n".join(parts), output=InterviewQuestionSet, mock=mock)


def feedback_answer(question: dict, answer: str, rubric: list | dict) -> AnswerFeedback:
    prompt = (f"Năng lực: {question['competency']}\n"
              f"Rubric: {_json(rubric)}\n"
              f"Câu hỏi: {question['question']}\n"
              f"Câu trả lời tốt cần có: {question.get('what_good_looks_like', '')}\n"
              + _xml("cau_tra_loi", answer))

    def mock() -> AnswerFeedback:
        words = len(answer.split())
        has_result = bool(re.search(r"\d|kết quả|giảm|tăng|hoàn thành", answer, re.I))
        score = 2 + (words > 40) + has_result + (words > 120)
        return AnswerFeedback(
            score=min(score, 5),
            feedback="[MẪU] " + ("Câu trả lời có kết quả cụ thể." if has_result else "Câu trả lời còn thiếu kết quả cụ thể."),
            better_answer_hint="Trả lời theo STAR và nêu kết quả đo được.",
            follow_up_question="" if has_result else "[MẪU] Kết quả cuối cùng của việc đó là gì, đo bằng cách nào?",
        )

    return generate(feature="interview.feedback", tier="smart", system=prompts.ANSWER_FEEDBACK_SYSTEM,
                    prompt=prompt, output=AnswerFeedback, mock=mock)


def summarize_interview(turns: list[dict]) -> InterviewSummary:
    def mock() -> InterviewSummary:
        groups: dict[str, list[int]] = {}
        for t in turns:
            if t.get("score") is not None:
                groups.setdefault(t["competency"], []).append(t["score"])
        return InterviewSummary(
            overall="[MẪU] Bạn trả lời khá ổn, cần luyện thêm cấu trúc STAR. Đây là luyện tập, không đảm bảo kết quả tuyển dụng.",
            per_competency=[CompetencySummary(competency=k, average_score=round(sum(v) / len(v), 2),
                                              comment="(dữ liệu mẫu)") for k, v in groups.items()],
            next_steps=["Chuẩn bị 3 câu chuyện STAR", "Luyện nói có số liệu"],
        )

    return generate(feature="interview.summary", tier="fast", system=prompts.INTERVIEW_SUMMARY_SYSTEM,
                    prompt=_xml("buoi_phong_van", _json(turns)), output=InterviewSummary, mock=mock)
