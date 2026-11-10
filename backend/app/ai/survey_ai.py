"""Tác vụ AI cho BO-16: soạn khảo sát, gán nhãn phản hồi mở (theo lô để tiết kiệm), sinh insight."""

import json

from app.ai import prompts
from app.ai.llm import generate
from app.ai.schemas import (
    InsightDraft,
    InsightSet,
    ResponseLabel,
    ResponseLabels,
    SurveyDraft,
    SurveyQuestionDraft,
)
from app.core.knowledge import ENGAGEMENT_PRACTICES
from app.core.text import fold

BATCH_SIZE = 40  # gom nhiều phản hồi vào một lượt gọi để giảm chi phí

_TOPIC_NAMES = ["Đãi ngộ", "Quản lý trực tiếp", "Khối lượng công việc", "Phát triển nghề nghiệp", "Ghi nhận",
                "Giao tiếp nội bộ", "Linh hoạt", "Đồng nghiệp", "Môi trường làm việc", "Ý định nghỉ việc"]
_NEG = ["khong", "chua", "met", "ap luc", "qua tai", "thap", "kem", "te", "chan", "bat cong", "nghi viec", "roi di"]
_POS = ["tot", "hai long", "thich", "vui", "ho tro", "tuyet", "cam on", "tu hao", "gan bo"]
_RISK = ["nghi viec", "roi di", "tim viec", "chuyen viec", "kiet suc", "burnout", "khong chiu noi"]


def draft_survey(goal: str) -> SurveyDraft:
    def mock() -> SurveyDraft:
        q = [("likert", "Quản lý trực tiếp hỗ trợ tôi hoàn thành công việc", "Quản lý"),
             ("likert", "Tôi thấy rõ cơ hội phát triển nghề nghiệp ở đây", "Phát triển"),
             ("likert", "Đãi ngộ tương xứng với đóng góp của tôi", "Đãi ngộ & ghi nhận"),
             ("likert", "Khối lượng công việc của tôi hợp lý", "Khối lượng công việc"),
             ("likert", "Tôi được ghi nhận khi làm tốt", "Đãi ngộ & ghi nhận"),
             ("likert", "Đồng nghiệp sẵn sàng phối hợp", "Đồng nghiệp"),
             ("likert", "Tôi muốn gắn bó với công ty ít nhất 2 năm nữa", "Gắn bó"),
             ("text", "Điều gì khiến bạn hài lòng nhất khi làm việc ở đây?", "Chung"),
             ("text", "Công ty nên thay đổi điều gì để bạn làm việc tốt hơn?", "Chung")]
        return SurveyDraft(questions=[SurveyQuestionDraft(type=t, text=f"[MẪU] {x}", dimension=d) for t, x, d in q])

    return generate(feature="survey.draft", tier="fast", system=prompts.SURVEY_DRAFT_SYSTEM,
                    prompt=f"<muc_tieu>\n{goal or 'Khảo sát gắn kết định kỳ'}\n</muc_tieu>",
                    output=SurveyDraft, mock=mock)


def _mock_label(i: int, text: str) -> ResponseLabel:
    f = fold(text)
    neg = sum(k in f for k in _NEG)
    pos = sum(k in f for k in _POS)
    sentiment = "negative" if neg > pos else "positive" if pos > neg else "neutral"
    topics = [_TOPIC_NAMES[idx] for idx, (kws, _) in enumerate(ENGAGEMENT_PRACTICES)
              if any(k in f for k in kws)]
    return ResponseLabel(index=i, sentiment=sentiment, topics=topics[:3] or ["Khác"],
                         risk_signal=any(k in f for k in _RISK))


def label_responses(texts: list[str], known_topics: list[str]) -> list[ResponseLabel]:
    labels: list[ResponseLabel] = []
    for start in range(0, len(texts), BATCH_SIZE):
        chunk = texts[start:start + BATCH_SIZE]
        items = "\n".join(f"[{start + i}] {t}" for i, t in enumerate(chunk))
        prompt = (f"<chu_de_da_co>\n{', '.join(known_topics or _TOPIC_NAMES)}\n</chu_de_da_co>\n\n"
                  f"<phan_hoi>\n{items}\n</phan_hoi>\nTrả về nhãn cho từng index.")

        def mock(chunk=chunk, start=start) -> ResponseLabels:
            return ResponseLabels(labels=[_mock_label(start + i, t) for i, t in enumerate(chunk)])

        result = generate(feature="survey.label", tier="fast", system=prompts.RESPONSE_LABEL_SYSTEM,
                          prompt=prompt, output=ResponseLabels, mock=mock)
        labels.extend(result.labels)
    return labels


def insights(stats: dict, topics: list, persistent: list[str], comparison: dict | None,
             practices: list[str]) -> InsightSet:
    prompt = "\n\n".join([
        f"<thong_ke>\n{json.dumps(stats, ensure_ascii=False)}\n</thong_ke>",
        f"<chu_de>\n{json.dumps(topics, ensure_ascii=False)}\n</chu_de>",
        f"<chu_de_ton_dong>\n{json.dumps(persistent, ensure_ascii=False)}\n</chu_de_ton_dong>",
        f"<so_sanh_ky_truoc>\n{json.dumps(comparison, ensure_ascii=False)}\n</so_sanh_ky_truoc>",
        f"<thuc_hanh_tot>\n" + "\n".join(f"- {p}" for p in practices) + "\n</thuc_hanh_tot>",
    ])

    def mock() -> InsightSet:
        out: list[InsightDraft] = []
        visible = {d: v for d, v in stats["departments"].items() if not v.get("suppressed")}
        risky = [d for d, v in visible.items() if v.get("risk_ratio", 0) >= 0.2 or v.get("negative_ratio", 0) >= 0.5]
        if risky:
            out.append(InsightDraft(kind="risk", title="[MẪU] Tín hiệu rủi ro nghỉ việc",
                                    detail="Tỷ lệ phản hồi tiêu cực/có ý định nghỉ việc cao ở: " + ", ".join(risky),
                                    departments=risky, priority="high", suggested_actions=practices[:2]))
        for name, count in topics[:3]:
            out.append(InsightDraft(kind="theme", title=f"[MẪU] Chủ đề nổi bật: {name}",
                                    detail=f"{count} phản hồi đề cập '{name}'.", departments=list(visible),
                                    priority="high" if name in persistent else "medium",
                                    suggested_actions=practices[:2]))
        for name in persistent:
            out.append(InsightDraft(kind="theme", title=f"[MẪU] Vấn đề tồn đọng nhiều kỳ: {name}",
                                    detail="Chủ đề này xuất hiện ở ít nhất 2 kỳ khảo sát liên tiếp.",
                                    departments=list(visible), priority="high", suggested_actions=practices[:1]))
        return InsightSet(insights=out[:6])

    return generate(feature="survey.insights", tier="smart", system=prompts.INSIGHT_SYSTEM,
                    prompt=prompt, output=InsightSet, mock=mock)
