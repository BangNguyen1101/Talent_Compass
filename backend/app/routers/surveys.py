"""BO-16: khảo sát gắn kết & phân tích ý kiến nhân viên.

Ẩn danh: phản hồi không lưu user_id (bảng participation riêng chỉ để chống trả lời 2 lần),
che PII trong câu trả lời mở, ẩn số liệu nhóm < ngưỡng tối thiểu.
HITL: insight do AI đề xuất phải được HR duyệt trước khi vào báo cáo lãnh đạo."""

import uuid
from collections import Counter
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.ai import survey_ai
from app.ai.llm import LLMError
from app.ai.pii import redact
from app.config import get_settings
from app.core import knowledge, survey_stats
from app.db import get_db
from app.models import (
    COMPANY_ROLES,
    AuditLog,
    Survey,
    SurveyInsight,
    SurveyParticipation,
    SurveyResponse,
    TopicMemory,
    User,
    Role,
)
from app.schemas import InsightReviewIn, SurveyAnswerIn, SurveyDraftIn, SurveyIn
from app.security import get_current_user, require_org, require_roles

router = APIRouter(prefix="/surveys", tags=["surveys"])


def _survey(db: Session, sid: uuid.UUID, user: User) -> Survey:
    s = db.get(Survey, sid)
    if not s or s.org_id != require_org(user):
        raise HTTPException(404, "Không tìm thấy khảo sát")
    return s


def _questions(body: SurveyIn) -> list[dict]:
    return [{**q.model_dump(), "id": q.id or f"q{i + 1}"} for i, q in enumerate(body.questions)]


def _out(s: Survey, **extra) -> dict:
    return {"id": str(s.id), "title": s.title, "description": s.description, "period_label": s.period_label,
            "questions": s.questions, "status": s.status, "created_at": s.created_at.isoformat(),
            "analyzed_at": s.analyzed_at.isoformat() if s.analyzed_at else None, **extra}


def _insight_out(i: SurveyInsight) -> dict:
    return {"id": i.id, "kind": i.kind, "title": i.title, "detail": i.detail, "departments": i.departments,
            "evidence_count": i.evidence_count, "priority": i.priority, "suggested_actions": i.suggested_actions,
            "selected_actions": i.selected_actions, "status": i.status, "hr_note": i.hr_note}


# ---------------------------------------------------------------- HR: thiết kế khảo sát

@router.post("/draft")
def draft(body: SurveyDraftIn, user: User = Depends(require_roles(Role.hr))):
    try:
        d = survey_ai.draft_survey(body.goal)
    except LLMError as e:
        raise HTTPException(502, str(e)) from e
    return {"questions": [{**q.model_dump(), "id": f"q{i + 1}"} for i, q in enumerate(d.questions)]}


@router.post("", status_code=201)
def create(body: SurveyIn, user: User = Depends(require_roles(Role.hr)), db: Session = Depends(get_db)):
    s = Survey(org_id=require_org(user), title=body.title, description=body.description,
               period_label=body.period_label, questions=_questions(body), created_by=user.id)
    db.add(s)
    db.commit()
    return _out(s)


@router.put("/{sid}")
def update(sid: uuid.UUID, body: SurveyIn, user: User = Depends(require_roles(Role.hr)),
           db: Session = Depends(get_db)):
    s = _survey(db, sid, user)
    if s.status != "draft":
        raise HTTPException(409, "Chỉ sửa được khảo sát ở trạng thái nháp")
    s.title, s.description, s.period_label, s.questions = body.title, body.description, body.period_label, _questions(body)
    db.commit()
    return _out(s)


@router.post("/{sid}/status/{new_status}")
def set_status(sid: uuid.UUID, new_status: str, user: User = Depends(require_roles(Role.hr)),
               db: Session = Depends(get_db)):
    s = _survey(db, sid, user)
    allowed = {"draft": {"open"}, "open": {"closed"}, "closed": {"open"}}
    if new_status not in allowed.get(s.status, set()):
        raise HTTPException(409, f"Không thể chuyển từ {s.status} sang {new_status}")
    s.status = new_status
    db.commit()
    return _out(s)


# ---------------------------------------------------------------- Nhân viên trả lời

@router.get("")
def list_surveys(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = require_org(user)
    q = select(Survey).where(Survey.org_id == org_id)
    if user.role not in (Role.hr, Role.manager, Role.admin):
        q = q.where(Survey.status == "open")
    surveys = db.scalars(q.order_by(Survey.created_at.desc())).all()
    answered = set(db.scalars(select(SurveyParticipation.survey_id).where(SurveyParticipation.user_id == user.id)).all())
    counts = dict(db.execute(select(SurveyResponse.survey_id, func.count()).group_by(SurveyResponse.survey_id)).all())
    return [_out(s, answered=s.id in answered,
                 responses=counts.get(s.id, 0) if user.role in (Role.hr, Role.manager) else None) for s in surveys]


@router.get("/{sid}")
def get_survey(sid: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = _survey(db, sid, user)
    if user.role not in (Role.hr, Role.manager, Role.admin) and s.status != "open":
        raise HTTPException(404, "Khảo sát không mở")
    answered = db.get(SurveyParticipation, (s.id, user.id)) is not None
    return _out(s, answered=answered)


@router.post("/{sid}/respond", status_code=201)
def respond(sid: uuid.UUID, body: SurveyAnswerIn, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    s = _survey(db, sid, user)
    if user.role not in COMPANY_ROLES:
        raise HTTPException(403, "Chỉ thành viên công ty trả lời khảo sát")
    if s.status != "open":
        raise HTTPException(409, "Khảo sát đã đóng")
    if db.get(SurveyParticipation, (s.id, user.id)):
        raise HTTPException(409, "Bạn đã trả lời khảo sát này")
    clean: dict = {}
    for q in s.questions:
        v = body.answers.get(q["id"])
        if v is None or v == "":
            continue
        if q["type"] == "likert":
            if not isinstance(v, int) or not 1 <= v <= 5:
                raise HTTPException(422, f"Câu '{q['text'][:40]}' cần điểm 1-5")
            clean[q["id"]] = v
        else:
            clean[q["id"]] = redact(str(v))[:3000]  # che tên/email/SĐT người trả lời tự viết vào
    if not clean:
        raise HTTPException(422, "Bạn chưa trả lời câu nào")
    db.add(SurveyParticipation(survey_id=s.id, user_id=user.id))
    db.add(SurveyResponse(survey_id=s.id, department=user.department or "Chưa rõ", answers=clean))
    db.commit()
    return {"ok": True, "message": "Cảm ơn bạn. Câu trả lời đã được lưu ẩn danh."}


# ---------------------------------------------------------------- HR: phân tích

def _rows(db: Session, s: Survey) -> list[SurveyResponse]:
    return list(db.scalars(select(SurveyResponse).where(SurveyResponse.survey_id == s.id)).all())


def _text_of(s: Survey, r: SurveyResponse) -> str:
    text_ids = [q["id"] for q in s.questions if q["type"] == "text"]
    return " | ".join(str(r.answers[i]) for i in text_ids if r.answers.get(i))


def _previous(db: Session, s: Survey) -> Survey | None:
    return db.scalar(select(Survey).where(Survey.org_id == s.org_id, Survey.id != s.id,
                                          Survey.analysis.is_not(None), Survey.created_at < s.created_at)
                     .order_by(Survey.created_at.desc()))


def _update_topic_memory(db: Session, s: Survey, topic_counts: Counter, negative_counts: Counter) -> list[str]:
    persistent = []
    for topic, count in topic_counts.items():
        if count < 2 or topic == "Khác":
            continue
        mem = db.scalar(select(TopicMemory).where(TopicMemory.org_id == s.org_id, TopicMemory.topic == topic))
        entry = {"survey_id": str(s.id), "period": s.period_label or s.title, "count": count,
                 "negative": negative_counts.get(topic, 0)}
        if mem is None:
            mem = TopicMemory(org_id=s.org_id, topic=topic, occurrences=1, last_survey_id=s.id, history=[entry])
            db.add(mem)
        elif str(s.id) not in {h["survey_id"] for h in mem.history}:
            mem.occurrences += 1
            mem.last_survey_id = s.id
            mem.history = [*mem.history, entry]
            mem.status = "open"
        if mem.occurrences >= 2 and mem.status == "open" and negative_counts.get(topic, 0) > 0:
            persistent.append(topic)
    return persistent


@router.post("/{sid}/analyze")
def analyze(sid: uuid.UUID, user: User = Depends(require_roles(Role.hr)), db: Session = Depends(get_db)):
    s = _survey(db, sid, user)
    rows = _rows(db, s)
    if not rows:
        raise HTTPException(422, "Chưa có phản hồi để phân tích")
    min_group = get_settings().survey_min_group_size

    # 1) AI gán nhãn phản hồi mở chưa có nhãn (theo lô)
    pending = [r for r in rows if r.sentiment is None and _text_of(s, r)]
    known = list(db.scalars(select(TopicMemory.topic).where(TopicMemory.org_id == s.org_id)).all())
    if pending:
        try:
            labels = survey_ai.label_responses([_text_of(s, r) for r in pending], known)
        except LLMError as e:
            raise HTTPException(502, str(e)) from e
        for lab in labels:
            if 0 <= lab.index < len(pending):
                r = pending[lab.index]
                r.sentiment, r.topics, r.risk_signal = lab.sentiment, lab.topics, lab.risk_signal
    for r in rows:
        if r.sentiment is None:
            r.sentiment = "neutral"

    # 2) Thống kê bằng code + ẩn nhóm nhỏ
    data = [{"department": r.department, "answers": r.answers, "sentiment": r.sentiment, "topics": r.topics,
             "risk_signal": r.risk_signal} for r in rows]
    stats = survey_stats.compute(s.questions, data, min_group)
    topic_counts = Counter(t for r in rows for t in (r.topics or []))
    neg_counts = Counter(t for r in rows if r.sentiment == "negative" for t in (r.topics or []))

    # 3) Memory chủ đề qua các kỳ + so sánh kỳ trước
    persistent = _update_topic_memory(db, s, topic_counts, neg_counts)
    prev = _previous(db, s)
    comparison = survey_stats.compare(stats, prev.analysis.get("stats") if prev and prev.analysis else None)

    # 4) AI đề xuất insight dựa trên số liệu đã tính + thực hành tốt (RAG)
    practices = knowledge.engagement_practices([t for t, _ in topic_counts.most_common(6)])
    safe_stats = {"overall": stats["overall"],
                  "departments": {d: v for d, v in stats["departments"].items()}}
    try:
        result = survey_ai.insights(safe_stats, topic_counts.most_common(8), persistent, comparison, practices)
    except LLMError as e:
        raise HTTPException(502, str(e)) from e
    visible = {d for d, v in stats["departments"].items() if not v.get("suppressed")}
    db.execute(delete(SurveyInsight).where(SurveyInsight.survey_id == s.id, SurveyInsight.status == "pending"))
    for ins in result.insights:
        depts = [d for d in ins.departments if d in visible]  # không gắn insight vào nhóm bị ẩn
        db.add(SurveyInsight(survey_id=s.id, kind=ins.kind, title=ins.title, detail=ins.detail, departments=depts,
                             evidence_count=sum(topic_counts.get(t, 0) for t in topic_counts if t.lower() in ins.title.lower()),
                             priority=ins.priority, suggested_actions=ins.suggested_actions))

    s.analysis = {"stats": stats, "topics": topic_counts.most_common(15), "persistent_topics": persistent,
                  "comparison": comparison, "previous_survey": prev.title if prev else None,
                  "practices": practices,
                  "warnings": ([f"Tổng số phản hồi ({len(rows)}) nhỏ hơn ngưỡng ẩn danh {min_group}: kết quả bị ẩn."]
                               if len(rows) < min_group else [])
                  + [f"Phòng '{d}' có dưới {min_group} phản hồi nên không hiển thị chi tiết."
                     for d, v in stats["departments"].items() if v.get("suppressed")]}
    s.analyzed_at = datetime.now(UTC)
    flag_modified(s, "analysis")
    db.add(AuditLog(actor_id=user.id, action="survey.analyze", target=str(s.id), detail={"responses": len(rows)}))
    db.commit()
    return dashboard(sid, user, db)


@router.get("/{sid}/dashboard")
def dashboard(sid: uuid.UUID, user: User = Depends(require_roles(Role.hr)), db: Session = Depends(get_db)):
    s = _survey(db, sid, user)
    members = db.scalar(select(func.count(User.id)).where(User.org_id == s.org_id, User.is_active.is_(True),
                                                          User.role.in_(list(COMPANY_ROLES)))) or 0
    participated = db.scalar(select(func.count()).where(SurveyParticipation.survey_id == s.id)) or 0
    insights = db.scalars(select(SurveyInsight).where(SurveyInsight.survey_id == s.id)
                          .order_by(SurveyInsight.id)).all()
    memory = db.scalars(select(TopicMemory).where(TopicMemory.org_id == s.org_id)
                        .order_by(TopicMemory.occurrences.desc())).all()
    return _out(s, analysis=s.analysis, participation={"responses": participated, "members": members,
                                                       "rate": round(participated / members, 3) if members else 0},
                insights=[_insight_out(i) for i in insights],
                topic_memory=[{"id": m.id, "topic": m.topic, "occurrences": m.occurrences, "status": m.status,
                               "history": m.history} for m in memory])


@router.patch("/{sid}/insights/{iid}")
def review_insight(sid: uuid.UUID, iid: int, body: InsightReviewIn, user: User = Depends(require_roles(Role.hr)),
                   db: Session = Depends(get_db)):
    s = _survey(db, sid, user)
    ins = db.get(SurveyInsight, iid)
    if not ins or ins.survey_id != s.id:
        raise HTTPException(404, "Không tìm thấy insight")
    if body.status == "approved" and not body.selected_actions:
        raise HTTPException(422, "Chọn ít nhất một hành động khi duyệt insight")
    ins.status, ins.selected_actions, ins.hr_note, ins.reviewed_by = (body.status, body.selected_actions,
                                                                      body.hr_note, user.id)
    db.commit()
    return _insight_out(ins)


@router.patch("/topic-memory/{mid}/resolve")
def resolve_topic(mid: int, user: User = Depends(require_roles(Role.hr)), db: Session = Depends(get_db)):
    m = db.get(TopicMemory, mid)
    if not m or m.org_id != require_org(user):
        raise HTTPException(404, "Không tìm thấy chủ đề")
    m.status = "resolved"
    db.commit()
    return {"ok": True}


@router.get("/{sid}/report")
def report(sid: uuid.UUID, user: User = Depends(require_roles(Role.hr, Role.manager)), db: Session = Depends(get_db)):
    """Báo cáo cho lãnh đạo: chỉ chứa insight HR đã duyệt và số liệu tổng hợp đã ẩn danh."""
    s = _survey(db, sid, user)
    if not s.analysis:
        raise HTTPException(404, "Khảo sát chưa được phân tích")
    approved = db.scalars(select(SurveyInsight).where(SurveyInsight.survey_id == s.id,
                                                      SurveyInsight.status == "approved")).all()
    stats = s.analysis["stats"]
    return _out(s, overall=stats["overall"],
                departments={d: v for d, v in stats["departments"].items()},
                comparison=s.analysis.get("comparison"), persistent_topics=s.analysis.get("persistent_topics", []),
                insights=[_insight_out(i) for i in approved], warnings=s.analysis.get("warnings", []))
