"""EDU-17: cố vấn hướng nghiệp (HITL) và tiến bộ của sinh viên.

KPI theo đề: tỷ lệ sinh viên sử dụng ≥60%, CSAT ≥4/5, điểm phỏng vấn trước/sau."""

import uuid
from statistics import mean

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    CV,
    AdvisorNote,
    CVAssessment,
    Feedback,
    InterviewSession,
    InterviewStatus,
    JobDescription,
    Role,
    User,
)
from app.schemas import AdvisorNoteIn
from app.security import get_current_user, require_org, require_roles

router = APIRouter(tags=["advisor"])

KPI_USAGE_TARGET = 0.6
KPI_CSAT_TARGET = 4.0


def student_progress(db: Session, student_id: uuid.UUID) -> dict:
    """Điểm trước/sau: buổi phỏng vấn thử đầu tiên vs gần nhất; CV lần chấm đầu vs gần nhất."""
    interviews = db.scalars(select(InterviewSession).where(
        InterviewSession.user_id == student_id, InterviewSession.status == InterviewStatus.completed,
        InterviewSession.average_score.is_not(None)).order_by(InterviewSession.created_at)).all()
    assessments = db.execute(select(CVAssessment, JobDescription.title)
                             .join(CV, CV.id == CVAssessment.cv_id)
                             .join(JobDescription, JobDescription.id == CVAssessment.jd_id)
                             .where(CV.user_id == student_id).order_by(CVAssessment.created_at)).all()

    def first_last(vals: list[float]) -> dict:
        if not vals:
            return {"first": None, "latest": None, "delta": None, "count": 0}
        return {"first": vals[0], "latest": vals[-1],
                "delta": round(vals[-1] - vals[0], 2) if len(vals) > 1 else None, "count": len(vals)}

    return {
        "interview": first_last([i.average_score for i in interviews]),
        "cv": first_last([a.overall_score for a, _ in assessments]),
        "ats": first_last([a.ats_score for a, _ in assessments]),
        "interview_history": [{"id": str(i.id), "date": i.created_at.isoformat(), "round_type": i.round_type,
                               "average_score": i.average_score} for i in interviews],
        "cv_history": [{"id": str(a.id), "date": a.created_at.isoformat(), "jd": title,
                        "score": a.overall_score, "ats": a.ats_score} for a, title in assessments],
    }


def _notes(db: Session, student_id: uuid.UUID) -> list[dict]:
    rows = db.execute(select(AdvisorNote, User.full_name).join(User, User.id == AdvisorNote.advisor_id)
                      .where(AdvisorNote.student_id == student_id).order_by(AdvisorNote.created_at.desc())).all()
    return [{"id": n.id, "advisor": name, "target_type": n.target_type, "target_id": n.target_id,
             "content": n.content, "created_at": n.created_at.isoformat()} for n, name in rows]


# ---------------------------------------------------------------- phía sinh viên

@router.get("/me/progress")
def my_progress(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {**student_progress(db, user.id), "advisor_notes": _notes(db, user.id)}


# ---------------------------------------------------------------- phía cố vấn

def _students(db: Session, org_id: uuid.UUID) -> list[User]:
    return list(db.scalars(select(User).where(User.org_id == org_id, User.role == Role.student,
                                              User.is_active.is_(True)).order_by(User.full_name)).all())


@router.get("/advisor/dashboard")
def dashboard(user: User = Depends(require_roles(Role.advisor)), db: Session = Depends(get_db)):
    org_id = require_org(user)
    students = _students(db, org_id)
    ids = [s.id for s in students]
    active = set()
    if ids:
        active |= set(db.scalars(select(CV.user_id).join(CVAssessment, CVAssessment.cv_id == CV.id)
                                 .where(CV.user_id.in_(ids)).distinct()).all())
        active |= set(db.scalars(select(InterviewSession.user_id).where(InterviewSession.user_id.in_(ids))
                                 .distinct()).all())
    ratings = list(db.scalars(select(Feedback.rating).where(Feedback.user_id.in_(ids))).all()) if ids else []
    deltas = []
    for s in students:
        p = student_progress(db, s.id)["interview"]
        if p["delta"] is not None:
            deltas.append(p["delta"])
    usage_rate = len(active) / len(students) if students else 0
    csat = round(mean(ratings), 2) if ratings else None
    return {
        "students_total": len(students),
        "students_active": len(active),
        "usage_rate": round(usage_rate, 3),
        "usage_target": KPI_USAGE_TARGET,
        "usage_met": usage_rate >= KPI_USAGE_TARGET,
        "csat": csat,
        "csat_responses": len(ratings),
        "csat_target": KPI_CSAT_TARGET,
        "csat_met": csat is not None and csat >= KPI_CSAT_TARGET,
        "interview_improvement_avg": round(mean(deltas), 2) if deltas else None,
        "students_with_improvement_data": len(deltas),
    }


@router.get("/advisor/students")
def list_students(user: User = Depends(require_roles(Role.advisor)), db: Session = Depends(get_db)):
    out = []
    for s in _students(db, require_org(user)):
        row = {"id": str(s.id), "full_name": s.full_name, "email": s.email, "shared": s.share_with_advisor}
        if s.share_with_advisor:
            p = student_progress(db, s.id)
            row.update({"interview": p["interview"], "cv": p["cv"],
                        "last_activity": max([h["date"] for h in p["interview_history"] + p["cv_history"]],
                                             default=None)})
        out.append(row)
    return out


def _shared_student(db: Session, advisor: User, student_id: uuid.UUID) -> User:
    s = db.get(User, student_id)
    if not s or s.org_id != advisor.org_id or s.role != Role.student:
        raise HTTPException(404, "Không tìm thấy sinh viên")
    if not s.share_with_advisor:
        raise HTTPException(403, "Sinh viên chưa đồng ý chia sẻ báo cáo")
    return s


@router.get("/advisor/students/{student_id}")
def student_detail(student_id: uuid.UUID, user: User = Depends(require_roles(Role.advisor)),
                   db: Session = Depends(get_db)):
    s = _shared_student(db, user, student_id)
    assessments = db.execute(select(CVAssessment, JobDescription.title).join(CV, CV.id == CVAssessment.cv_id)
                             .join(JobDescription, JobDescription.id == CVAssessment.jd_id)
                             .where(CV.user_id == s.id).order_by(CVAssessment.created_at.desc())).all()
    interviews = db.execute(select(InterviewSession, JobDescription.title)
                            .join(JobDescription, JobDescription.id == InterviewSession.jd_id)
                            .where(InterviewSession.user_id == s.id)
                            .order_by(InterviewSession.created_at.desc())).all()
    return {
        "student": {"id": str(s.id), "full_name": s.full_name, "email": s.email},
        "progress": student_progress(db, s.id),
        "assessments": [{"id": str(a.id), "jd": t, "overall_score": a.overall_score, "ats_score": a.ats_score,
                         "result": a.result, "created_at": a.created_at.isoformat()} for a, t in assessments],
        "interviews": [{"id": str(i.id), "jd": t, "round_type": i.round_type, "status": i.status.value,
                        "average_score": i.average_score, "turns": i.turns, "summary": i.summary,
                        "created_at": i.created_at.isoformat()} for i, t in interviews],
        "notes": _notes(db, s.id),
    }


@router.post("/advisor/students/{student_id}/notes", status_code=201)
def add_note(student_id: uuid.UUID, body: AdvisorNoteIn, user: User = Depends(require_roles(Role.advisor)),
             db: Session = Depends(get_db)):
    s = _shared_student(db, user, student_id)
    note = AdvisorNote(advisor_id=user.id, student_id=s.id, **body.model_dump())
    db.add(note)
    db.commit()
    return {"id": note.id}


@router.get("/advisor/activity")
def activity(user: User = Depends(require_roles(Role.advisor)), db: Session = Depends(get_db)):
    """Số lượt dùng theo tuần (theo dõi tỷ lệ dùng theo thời gian)."""
    ids = [s.id for s in _students(db, require_org(user))]
    if not ids:
        return []
    week = func.date_trunc("week", InterviewSession.created_at)
    rows = db.execute(select(week, func.count()).where(InterviewSession.user_id.in_(ids))
                      .group_by(week).order_by(week)).all()
    return [{"week": w.date().isoformat(), "interviews": n} for w, n in rows]
