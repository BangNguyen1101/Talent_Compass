"""EDU-17: tải CV, chấm ATS + AI theo JD, guardrail chống bịa, so sánh nhiều vị trí."""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import services
from app.ai.cv_parser import UnsupportedFileError, extract_text
from app.ai.llm import LLMError, model_name
from app.ai.pii import redact
from app.core import ats, guardrails
from app.db import get_db
from app.models import CV, AuditLog, CVAssessment, User
from app.routers.jobs import competencies_for_ai, get_job_or_404
from app.schemas import AssessIn, AssessmentOut, ATSCompareIn, CVOut
from app.security import get_current_user

router = APIRouter(prefix="/cvs", tags=["cvs"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def _own_cv(db: Session, cv_id: uuid.UUID, user: User) -> CV:
    cv = db.get(CV, cv_id)
    if not cv or cv.user_id != user.id:
        raise HTTPException(404, "Không tìm thấy CV")
    return cv


@router.post("", response_model=CVOut, status_code=201)
async def upload_cv(file: UploadFile = File(...), user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File tối đa 5 MB")
    try:
        text = extract_text(file.filename or "cv.txt", data)
    except UnsupportedFileError as e:
        raise HTTPException(422, str(e)) from e
    redacted = redact(text)
    try:
        parsed = services.parse_cv(redacted)
    except LLMError as e:
        raise HTTPException(502, str(e)) from e
    cv = CV(user_id=user.id, filename=file.filename or "cv", raw_text=text, redacted_text=redacted,
            parsed=parsed.model_dump())
    db.add(cv)
    db.commit()
    return cv


@router.get("", response_model=list[CVOut])
def list_cvs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(CV).where(CV.user_id == user.id).order_by(CV.created_at.desc())).all()


@router.post("/{cv_id}/assess", response_model=AssessmentOut, status_code=201)
def assess(cv_id: uuid.UUID, body: AssessIn, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    cv = _own_cv(db, cv_id, user)
    jd = get_job_or_404(db, body.jd_id, user)
    comps = competencies_for_ai(jd)
    if not comps:
        raise HTTPException(422, "JD chưa có khung năng lực")
    ats_result = ats.score(cv.redacted_text, jd.content, [c["name"] for c in comps])
    try:
        result = services.assess_cv(cv.redacted_text, f"# {jd.title}\n{jd.content}", comps, ats_result)
    except LLMError as e:
        raise HTTPException(502, str(e)) from e

    data = result.model_dump()
    # Guardrail: kiểm tra từng câu gợi ý so với CV gốc
    data["suggestions"], flagged = guardrails.apply(data["suggestions"], cv.redacted_text)
    data["guardrail_flagged"] = flagged
    data["disclaimer"] = "Gợi ý chỉ giúp trình bày tốt hơn kinh nghiệm thật của bạn; AI không đảm bảo bạn trúng tuyển."

    a = CVAssessment(cv_id=cv.id, jd_id=jd.id, overall_score=services.weighted_score(result.competency_scores, comps),
                     ats_score=ats_result["score"], ats=ats_result, result=data, model_used=model_name("smart"))
    db.add(a)
    db.add(AuditLog(actor_id=user.id, action="cv.assess", target=str(cv.id),
                    detail={"jd_id": str(jd.id), "score": a.overall_score, "ats": a.ats_score,
                            "guardrail_flagged": flagged, "model": a.model_used}))
    db.commit()
    return a


@router.post("/{cv_id}/ats-compare")
def ats_compare(cv_id: uuid.UUID, body: ATSCompareIn, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    """Tối ưu CV theo ATS cho nhiều vị trí cùng lúc (không tốn AI)."""
    cv = _own_cv(db, cv_id, user)
    rows = []
    for jd_id in body.jd_ids:
        jd = get_job_or_404(db, jd_id, user)
        r = ats.score(cv.redacted_text, jd.content, [c["name"] for c in competencies_for_ai(jd)])
        rows.append({"jd_id": str(jd.id), "title": jd.title, "level": jd.level, **r})
    rows.sort(key=lambda r: -r["score"])
    # Từ khóa thiếu ở nhiều vị trí = kỹ năng nên ưu tiên học
    freq: dict[str, int] = {}
    for r in rows:
        for k in r["missing_keywords"]:
            freq[k] = freq.get(k, 0) + 1
    common_gaps = sorted(freq.items(), key=lambda kv: -kv[1])[:10]
    return {"results": rows, "common_gaps": [{"keyword": k, "positions": n} for k, n in common_gaps]}


@router.get("/{cv_id}/assessments", response_model=list[AssessmentOut])
def list_assessments(cv_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _own_cv(db, cv_id, user)
    return db.scalars(select(CVAssessment).where(CVAssessment.cv_id == cv_id)
                      .order_by(CVAssessment.created_at.desc())).all()


@router.delete("/{cv_id}", status_code=204)
def delete_cv(cv_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_own_cv(db, cv_id, user))
    db.commit()
