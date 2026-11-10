"""EDU-17 (phỏng vấn thử) và nền cho BO-17: câu hỏi bám khung năng lực, AI chấm từng câu trả lời."""

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


def _own(db: Session, sid: uuid.UUID, user: User) -> InterviewSession:
    s = db.get(InterviewSession, sid)
    if not s or s.user_id != user.id:
        raise HTTPException(404, "Không tìm thấy buổi phỏng vấn")
    return s


@router.post("", response_model=InterviewOut, status_code=201)
def start(body: InterviewStartIn, user: User = Depends(get_current_user),
          db: Session = Depends(get_db)):
    jd = get_job_or_404(db, body.jd_id, user)
    comps = competencies_for_ai(jd)
    if not comps:
        raise HTTPException(422, "JD chưa có khung năng lực")
    try:
        qs = services.generate_questions(f"# {jd.title}\n{jd.content}", comps, body.question_count)
    except LLMError as e:
        raise HTTPException(502, str(e)) from e

    s = InterviewSession(
        user_id=user.id, jd_id=jd.id, mode=body.mode,
        turns=[{**q.model_dump(), "answer": None, "score": None, "feedback": None,
                "better_answer_hint": None} for q in qs.questions[: body.question_count]],
    )
    db.add(s)
    db.commit()
    return s


@router.get("", response_model=list[InterviewOut])
def list_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(InterviewSession).where(InterviewSession.user_id == user.id)
                      .order_by(InterviewSession.created_at.desc())).all()


@router.get("/{sid}", response_model=InterviewOut)
def get_session(sid: uuid.UUID, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
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
    jd = get_job_or_404(db, s.jd_id, user)
    rubric = next((c["rubric"] for c in competencies_for_ai(jd)
                   if c["name"].lower() == turn["competency"].lower()), [])
    try:
        fb = services.feedback_answer(turn, body.answer, rubric)
    except LLMError as e:
        raise HTTPException(502, str(e)) from e

    s.turns[index] = {**turn, "answer": body.answer, **fb.model_dump()}
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
    s.summary = summary.model_dump()
    s.status = InterviewStatus.completed
    db.commit()
    return s
