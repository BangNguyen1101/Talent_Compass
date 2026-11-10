"""EDU-17: phỏng vấn thử nhiều vòng, có câu hỏi đào sâu (follow-up) và nhớ điểm yếu từ buổi trước."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.ai import services
from app.ai.llm import LLMError
from app.db import get_db
from app.models import InterviewSession, InterviewStatus, User
from app.routers.jobs import competencies_for_ai, get_job_or_404
from app.schemas import AnswerIn, InterviewOut, InterviewStartIn
from app.security import get_current_user

router = APIRouter(prefix="/interviews", tags=["interviews"])

MAX_FOLLOW_UPS_PER_QUESTION = 1


def _own(db: Session, sid: uuid.UUID, user: User) -> InterviewSession:
    s = db.get(InterviewSession, sid)
    if not s or s.user_id != user.id:
        raise HTTPException(404, "Không tìm thấy buổi phỏng vấn")
    return s


def _blank_turn(q: dict, parent: int | None = None) -> dict:
    return {**q, "answer": None, "score": None, "feedback": None, "better_answer_hint": None,
            "follow_up_question": "", "parent": parent}


def weak_points(db: Session, user_id: uuid.UUID, jd_id: uuid.UUID) -> list[str]:
    """Memory: năng lực điểm thấp ở buổi phỏng vấn thử gần nhất cùng JD."""
    last = db.scalar(select(InterviewSession).where(
        InterviewSession.user_id == user_id, InterviewSession.jd_id == jd_id,
        InterviewSession.status == InterviewStatus.completed).order_by(InterviewSession.created_at.desc()))
    if not last:
        return []
    return sorted({t["competency"] for t in last.turns if (t.get("score") or 5) <= 2})


@router.post("", response_model=InterviewOut, status_code=201)
def start(body: InterviewStartIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    jd = get_job_or_404(db, body.jd_id, user)
    comps = competencies_for_ai(jd)
    if not comps:
        raise HTTPException(422, "JD chưa có khung năng lực")
    probe = weak_points(db, user.id, jd.id)
    try:
        qs = services.generate_questions(f"# {jd.title}\n{jd.content}", comps, body.question_count,
                                         body.round_type, [f"Năng lực còn yếu ở buổi trước: {p}" for p in probe])
    except LLMError as e:
        raise HTTPException(502, str(e)) from e
    s = InterviewSession(user_id=user.id, jd_id=jd.id, round_type=body.round_type,
                         turns=[_blank_turn(q.model_dump()) for q in qs.questions[: body.question_count]])
    db.add(s)
    db.commit()
    return s


@router.get("", response_model=list[InterviewOut])
def list_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(InterviewSession).where(InterviewSession.user_id == user.id)
                      .order_by(InterviewSession.created_at.desc())).all()


@router.get("/{sid}", response_model=InterviewOut)
def get_session(sid: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _own(db, sid, user)


@router.post("/{sid}/turns/{index}/answer", response_model=InterviewOut)
def answer(sid: uuid.UUID, index: int, body: AnswerIn, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    s = _own(db, sid, user)
    if s.status == InterviewStatus.completed:
        raise HTTPException(409, "Buổi phỏng vấn đã kết thúc")
    if not 0 <= index < len(s.turns):
        raise HTTPException(404, "Không có câu hỏi này")
    turn = s.turns[index]
    if turn.get("answer"):
        raise HTTPException(409, "Câu này đã được trả lời")
    jd = get_job_or_404(db, s.jd_id, user)
    rubric = next((c["rubric"] for c in competencies_for_ai(jd)
                   if c["name"].lower() == turn["competency"].lower()), [])
    try:
        fb = services.feedback_answer(turn, body.answer, rubric)
    except LLMError as e:
        raise HTTPException(502, str(e)) from e

    s.turns[index] = {**turn, "answer": body.answer, **fb.model_dump()}
    # Câu hỏi đào sâu: chèn ngay sau câu gốc (tối đa 1 lần mỗi câu gốc)
    root = turn.get("parent") if turn.get("parent") is not None else index
    follow_ups = sum(1 for t in s.turns if t.get("parent") == root)
    if fb.follow_up_question.strip() and follow_ups < MAX_FOLLOW_UPS_PER_QUESTION:
        s.turns.insert(index + 1, _blank_turn({
            "question": fb.follow_up_question, "competency": turn["competency"],
            "what_good_looks_like": turn.get("what_good_looks_like", "")}, parent=root))
        # Cập nhật chỉ số parent của các câu phía sau sau khi chèn
        for t in s.turns[index + 2:]:
            if t.get("parent") is not None and t["parent"] > index:
                t["parent"] += 1
    flag_modified(s, "turns")
    db.commit()
    return s


@router.post("/{sid}/finish", response_model=InterviewOut)
def finish(sid: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = _own(db, sid, user)
    answered = [t for t in s.turns if t.get("answer")]
    if not answered:
        raise HTTPException(422, "Hãy trả lời ít nhất một câu trước khi kết thúc")
    try:
        summary = services.summarize_interview(answered)
    except LLMError as e:
        raise HTTPException(502, str(e)) from e
    scores = [t["score"] for t in answered if t.get("score")]
    s.summary = summary.model_dump()
    s.average_score = round(sum(scores) / len(scores), 2) if scores else None
    s.status = InterviewStatus.completed
    db.commit()
    return s
