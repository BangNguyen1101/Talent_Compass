"""BO-17: trợ lý phỏng vấn & tổng hợp đánh giá ứng viên.

- Trưởng nhóm tuyển dụng tạo ứng viên, vòng phỏng vấn, phân công người phỏng vấn.
- Người phỏng vấn chấm ĐỘC LẬP (không thấy điểm người khác để tránh ảnh hưởng lẫn nhau).
- Đóng vòng: code tổng hợp điểm, phát hiện bất đồng/tiêu chí chưa hỏi; AI viết khuyến nghị.
- Hội đồng ra quyết định cuối cùng (HITL), ghi lý do."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import hiring_ai, services
from app.ai.llm import LLMError
from app.ai.pii import redact
from app.core import aggregation, bias
from app.db import get_db
from app.models import (
    AuditLog,
    Candidate,
    HiringDecision,
    InterviewRound,
    JobDescription,
    Role,
    Scorecard,
    User,
)
from app.routers.jobs import competencies_for_ai
from app.schemas import CandidateIn, DecisionIn, RoundIn, ScorecardIn, StructureNotesIn
from app.security import get_current_user, require_org, require_roles

router = APIRouter(prefix="/hiring", tags=["hiring"])

LEADS = (Role.hiring_lead, Role.hr)
REC_MATCH = {"hire": "hire", "reject": "no_hire", "hold": "more_info"}


def _is_lead(user: User) -> bool:
    return user.role in (*LEADS, Role.admin)


def _candidate(db: Session, cid: uuid.UUID, user: User) -> Candidate:
    c = db.get(Candidate, cid)
    if not c or c.org_id != require_org(user):
        raise HTTPException(404, "Không tìm thấy ứng viên")
    if not _is_lead(user):
        assigned = db.scalar(select(func.count(InterviewRound.id)).where(
            InterviewRound.candidate_id == c.id, InterviewRound.interviewer_ids.contains([str(user.id)])))
        if not assigned:
            raise HTTPException(404, "Không tìm thấy ứng viên")
    return c


def _round(db: Session, rid: uuid.UUID, user: User) -> tuple[InterviewRound, Candidate]:
    r = db.get(InterviewRound, rid)
    if not r:
        raise HTTPException(404, "Không tìm thấy vòng phỏng vấn")
    c = _candidate(db, r.candidate_id, user)
    if not _is_lead(user) and str(user.id) not in r.interviewer_ids:
        raise HTTPException(404, "Không tìm thấy vòng phỏng vấn")
    return r, c


def _jd(db: Session, c: Candidate) -> JobDescription:
    return db.get(JobDescription, c.jd_id)


def _names(db: Session, ids: list[str]) -> dict[str, str]:
    if not ids:
        return {}
    rows = db.execute(select(User.id, User.full_name).where(User.id.in_([uuid.UUID(i) for i in ids]))).all()
    return {str(i): n for i, n in rows}


def _scorecard_out(sc: Scorecard) -> dict:
    return {"id": sc.id, "interviewer_id": str(sc.interviewer_id), "scores": sc.scores,
            "question_notes": sc.question_notes, "raw_notes": sc.raw_notes, "recommendation": sc.recommendation,
            "bias_flags": sc.bias_flags, "submitted": sc.submitted,
            "submitted_at": sc.submitted_at.isoformat() if sc.submitted_at else None}


def _round_out(db: Session, r: InterviewRound, user: User) -> dict:
    names = _names(db, r.interviewer_ids)
    cards = db.scalars(select(Scorecard).where(Scorecard.round_id == r.id)).all()
    out = {"id": str(r.id), "round_no": r.round_no, "name": r.name, "focus_competencies": r.focus_competencies,
           "questions": r.questions, "status": r.status,
           "interviewers": [{"id": i, "name": names.get(i, "?"),
                             "submitted": any(str(c.interviewer_id) == i and c.submitted for c in cards)}
                            for i in r.interviewer_ids]}
    mine = next((c for c in cards if c.interviewer_id == user.id), None)
    out["my_scorecard"] = _scorecard_out(mine) if mine else None
    if _is_lead(user):
        out["scorecards"] = [{**_scorecard_out(c), "interviewer": names.get(str(c.interviewer_id), "?")}
                             for c in cards if c.submitted]
        out["aggregate"] = r.aggregate
        out["recommendation"] = r.recommendation
    return out


# ---------------------------------------------------------------- ứng viên

@router.get("/candidates")
def list_candidates(user: User = Depends(require_roles(Role.hiring_lead, Role.hr, Role.interviewer)),
                    db: Session = Depends(get_db)):
    q = select(Candidate, JobDescription.title).join(JobDescription, JobDescription.id == Candidate.jd_id) \
        .where(Candidate.org_id == require_org(user), Candidate.stage != "withdrawn")
    if not _is_lead(user):
        assigned = select(InterviewRound.candidate_id).where(
            InterviewRound.interviewer_ids.contains([str(user.id)]))
        q = q.where(Candidate.id.in_(assigned))
    rows = db.execute(q.order_by(Candidate.created_at.desc())).all()
    out = []
    for c, title in rows:
        rounds = db.scalars(select(InterviewRound).where(InterviewRound.candidate_id == c.id)).all()
        pending_mine = [str(r.id) for r in rounds if str(user.id) in r.interviewer_ids and r.status == "open"
                        and not db.scalar(select(Scorecard.submitted).where(Scorecard.round_id == r.id,
                                                                             Scorecard.interviewer_id == user.id))]
        out.append({"id": str(c.id), "full_name": c.full_name, "jd_title": title, "stage": c.stage,
                    "source": c.source, "match_score": c.match_score,
                    "rounds": len(rounds), "my_pending_rounds": pending_mine,
                    "created_at": c.created_at.isoformat()})
    return out


@router.post("/candidates", status_code=201)
def create_candidate(body: CandidateIn, user: User = Depends(require_roles(*LEADS)), db: Session = Depends(get_db)):
    jd = db.get(JobDescription, body.jd_id)
    if not jd or jd.org_id != require_org(user):
        raise HTTPException(404, "JD không thuộc tổ chức của bạn")
    c = Candidate(org_id=user.org_id, jd_id=jd.id, full_name=body.full_name, email=body.email,
                  cv_text=redact(body.cv_text) if body.cv_text else "", created_by=user.id)
    db.add(c)
    db.commit()
    return {"id": str(c.id)}


@router.get("/candidates/{cid}")
def get_candidate(cid: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = _candidate(db, cid, user)
    jd = _jd(db, c)
    rounds = db.scalars(select(InterviewRound).where(InterviewRound.candidate_id == c.id)
                        .order_by(InterviewRound.round_no)).all()
    visible = [r for r in rounds if _is_lead(user) or str(user.id) in r.interviewer_ids]
    out = {"id": str(c.id), "full_name": c.full_name, "stage": c.stage, "source": c.source,
           "match_score": c.match_score, "cover_note": c.cover_note if _is_lead(user) else "",
           "jd": {"id": str(jd.id), "title": jd.title, "level": jd.level, "competencies": competencies_for_ai(jd)},
           "rounds": [_round_out(db, r, user) for r in visible], "is_lead": _is_lead(user)}
    if _is_lead(user):
        out["email"] = c.email
        out["cv_text"] = c.cv_text
        out["profile_memory"] = c.profile_memory
        decisions = db.execute(select(HiringDecision, User.full_name).join(User, User.id == HiringDecision.decided_by)
                               .where(HiringDecision.candidate_id == c.id)
                               .order_by(HiringDecision.created_at.desc())).all()
        out["decisions"] = [{"decision": d.decision, "rationale": d.rationale, "committee": d.committee,
                             "followed_ai": d.followed_ai, "by": n, "at": d.created_at.isoformat()}
                            for d, n in decisions]
    return out


# ---------------------------------------------------------------- vòng phỏng vấn

@router.post("/candidates/{cid}/rounds", status_code=201)
def create_round(cid: uuid.UUID, body: RoundIn, user: User = Depends(require_roles(*LEADS)),
                 db: Session = Depends(get_db)):
    c = _candidate(db, cid, user)
    jd = _jd(db, c)
    comps = competencies_for_ai(jd)
    names = {x["name"].lower() for x in comps}
    focus = [f for f in body.focus_competencies if f.lower() in names] or [x["name"] for x in comps]
    members = set(db.scalars(select(User.id).where(User.org_id == user.org_id, User.is_active.is_(True))).all())
    if any(i not in members for i in body.interviewer_ids):
        raise HTTPException(422, "Người phỏng vấn phải thuộc tổ chức")

    focus_l = {f.lower() for f in focus}
    bank = [q for q in (jd.question_bank or []) if q["competency"].lower() in focus_l]
    if bank:  # dùng ngân hàng câu hỏi của JD: không tốn AI, nhất quán giữa các ứng viên
        questions = [{"question": q["question"], "competency": q["competency"], "type": q.get("type", ""),
                      "what_good_looks_like": "; ".join(q.get("good_signals", [])),
                      "red_flags": q.get("red_flags", []), "follow_ups": q.get("follow_ups", []),
                      "scoring_guide": q.get("scoring_guide")} for q in bank[: body.question_count]]
    else:
        probe = (c.profile_memory[-1].get("probe_next_round", []) if c.profile_memory else [])
        try:
            qs = services.generate_questions(f"# {jd.title}\n{jd.content}",
                                             [x for x in comps if x["name"].lower() in focus_l],
                                             body.question_count, "behavioral", probe)
        except LLMError as e:
            raise HTTPException(502, str(e)) from e
        questions = [q.model_dump() for q in qs.questions]

    no = (db.scalar(select(func.max(InterviewRound.round_no)).where(InterviewRound.candidate_id == c.id)) or 0) + 1
    r = InterviewRound(candidate_id=c.id, round_no=no, name=body.name, focus_competencies=focus,
                       questions=questions, interviewer_ids=[str(i) for i in body.interviewer_ids])
    db.add(r)
    c.stage = "interviewing"
    db.commit()
    return _round_out(db, r, user)


@router.get("/rounds/{rid}")
def get_round(rid: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r, c = _round(db, rid, user)
    jd = _jd(db, c)
    out = _round_out(db, r, user)
    out["candidate"] = {"id": str(c.id), "full_name": c.full_name}
    out["jd"] = {"title": jd.title, "level": jd.level,
                 "competencies": [x for x in competencies_for_ai(jd)
                                  if x["name"].lower() in {f.lower() for f in r.focus_competencies}]}
    # Memory qua các vòng: người phỏng vấn thấy điểm cần làm rõ từ vòng trước (không thấy điểm số)
    out["probe_from_previous"] = c.profile_memory[-1].get("probe_next_round", []) if c.profile_memory else []
    return out


@router.put("/rounds/{rid}/scorecard")
def save_scorecard(rid: uuid.UUID, body: ScorecardIn, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    r, _ = _round(db, rid, user)
    if str(user.id) not in r.interviewer_ids:
        raise HTTPException(403, "Bạn không được phân công vòng này")
    if r.status != "open":
        raise HTTPException(409, "Vòng phỏng vấn đã đóng")
    sc = db.scalar(select(Scorecard).where(Scorecard.round_id == r.id, Scorecard.interviewer_id == user.id))
    if sc and sc.submitted:
        raise HTTPException(409, "Scorecard đã nộp, không sửa được")
    if sc is None:
        sc = Scorecard(round_id=r.id, interviewer_id=user.id)
        db.add(sc)
    sc.scores = [s.model_dump() for s in body.scores]
    sc.question_notes = [q.model_dump() for q in body.question_notes]
    sc.raw_notes = body.raw_notes
    sc.recommendation = body.recommendation
    text = "\n".join([body.raw_notes] + [s.evidence for s in body.scores] + [q.notes for q in body.question_notes])
    sc.bias_flags = bias.detect(text)

    warnings = {
        "untested_competencies": aggregation.untested_competencies(r.focus_competencies, sc.scores),
        "unasked_questions": aggregation.unasked_questions(r.questions, sc.question_notes),
        "bias_flags": sc.bias_flags,
    }
    if body.submit:
        if not body.recommendation:
            raise HTTPException(422, "Cần chọn khuyến nghị trước khi nộp")
        if bias.has_high(sc.bias_flags):
            raise HTTPException(422, "Ghi chú có nội dung thiên vị (tuổi, giới tính, ngoại hình...). Hãy xóa trước khi nộp.")
        sc.submitted = True
        sc.submitted_at = datetime.now(UTC)
    db.commit()
    return {"scorecard": _scorecard_out(sc), "warnings": warnings}


@router.post("/rounds/{rid}/structure-notes")
def structure_notes(rid: uuid.UUID, body: StructureNotesIn, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    r, c = _round(db, rid, user)
    comps = [x for x in competencies_for_ai(_jd(db, c)) if x["name"].lower() in {f.lower() for f in r.focus_competencies}]
    try:
        result = hiring_ai.structure_notes(body.raw_notes, comps)
    except LLMError as e:
        raise HTTPException(502, str(e)) from e
    return {**result.model_dump(), "bias_flags": bias.detect(body.raw_notes)}


@router.post("/rounds/{rid}/close")
def close_round(rid: uuid.UUID, user: User = Depends(require_roles(*LEADS)), db: Session = Depends(get_db)):
    r, c = _round(db, rid, user)
    jd = _jd(db, c)
    cards = db.scalars(select(Scorecard).where(Scorecard.round_id == r.id, Scorecard.submitted.is_(True))).all()
    if not cards:
        raise HTTPException(422, "Chưa có scorecard nào được nộp")
    names = _names(db, r.interviewer_ids)
    required = {x["name"].lower(): x["required_level"] for x in competencies_for_ai(jd)}
    agg = aggregation.aggregate(r.focus_competencies, required,
                                [{"interviewer": names.get(str(s.interviewer_id), "?"), "scores": s.scores,
                                  "recommendation": s.recommendation} for s in cards])
    agg["missing_scorecards"] = [names.get(i, "?") for i in r.interviewer_ids
                                 if i not in {str(s.interviewer_id) for s in cards}]
    try:
        rec = hiring_ai.recommend(jd.title, agg, c.profile_memory or [])
    except LLMError as e:
        raise HTTPException(502, str(e)) from e
    r.aggregate, r.recommendation, r.status = agg, rec.model_dump(), "closed"
    c.profile_memory = [*(c.profile_memory or []), {
        "round_no": r.round_no, "name": r.name, "fit_score": agg["fit_score"], "summary": rec.rationale,
        "concerns": rec.concerns, "probe_next_round": rec.probe_next_round}]
    c.stage = "review"
    db.add(AuditLog(actor_id=user.id, action="hiring.round_close", target=str(r.id),
                    detail={"fit": agg["fit_score"], "recommendation": rec.recommendation}))
    db.commit()
    return _round_out(db, r, user)


@router.post("/candidates/{cid}/decision", status_code=201)
def decide(cid: uuid.UUID, body: DecisionIn, user: User = Depends(require_roles(*LEADS)),
           db: Session = Depends(get_db)):
    c = _candidate(db, cid, user)
    last = db.scalar(select(InterviewRound).where(InterviewRound.candidate_id == c.id,
                                                  InterviewRound.status == "closed")
                     .order_by(InterviewRound.round_no.desc()))
    if c.stage == "withdrawn":
        raise HTTPException(409, "Ứng viên đã rút đơn")
    # Sàng lọc hồ sơ: được từ chối đơn ứng tuyển trước khi phỏng vấn; tuyển thì bắt buộc qua phỏng vấn
    if not last and not (c.stage == "applied" and body.decision == "reject"):
        raise HTTPException(422, "Cần đóng ít nhất một vòng phỏng vấn trước khi quyết định")
    ai_rec = (last.recommendation or {}).get("recommendation") if last else None
    d = HiringDecision(candidate_id=c.id, decision=body.decision, rationale=body.rationale,
                       committee=body.committee or [user.full_name], decided_by=user.id,
                       followed_ai=(REC_MATCH[body.decision] == ai_rec) if ai_rec else None)
    db.add(d)
    c.stage = {"hire": "hired", "reject": "rejected", "hold": "on_hold"}[body.decision]
    db.add(AuditLog(actor_id=user.id, action="hiring.decision", target=str(c.id),
                    detail={"decision": body.decision, "ai_recommendation": ai_rec}))
    db.commit()
    return {"ok": True, "followed_ai": d.followed_ai}
