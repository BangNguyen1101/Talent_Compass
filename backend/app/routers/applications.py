"""Ứng tuyển trên sàn việc làm.

Ứng viên chọn một CV đã tải lên và nộp vào JD đã ban hành. Đơn trở thành hồ sơ ứng viên
(stage=applied) trong quy trình tuyển dụng BO-17 của công ty đó. Chỉ bản CV đã che thông tin
liên hệ được chia sẻ; ứng viên có thể rút đơn khi công ty chưa mời phỏng vấn."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import ats
from app.db import get_db
from app.models import CV, AuditLog, Candidate, JobDescription, JobStatus, Organization, Role, User
from app.routers.jobs import competencies_for_ai
from app.security import get_current_user, require_roles

router = APIRouter(tags=["applications"])

# Trạng thái hiển thị cho ứng viên (không lộ chi tiết nội bộ như điểm, khuyến nghị AI)
APPLICANT_STATUS = {
    "applied": "Đã nộp, chờ công ty xem xét",
    "interviewing": "Được mời phỏng vấn",
    "review": "Đang được hội đồng xem xét",
    "on_hold": "Đang được cân nhắc thêm",
    "hired": "Trúng tuyển",
    "rejected": "Chưa phù hợp lần này",
    "withdrawn": "Bạn đã rút đơn",
}


class ApplyIn(BaseModel):
    cv_id: uuid.UUID
    cover_note: str = Field(default="", max_length=3000)


@router.post("/jobs/{jd_id}/apply", status_code=201)
def apply(jd_id: uuid.UUID, body: ApplyIn, user: User = Depends(require_roles(Role.student)),
          db: Session = Depends(get_db)):
    jd = db.get(JobDescription, jd_id)
    if not jd or jd.status != JobStatus.published or jd.org_id is None:
        raise HTTPException(404, "JD không tồn tại hoặc đã ngừng tuyển")
    cv = db.get(CV, body.cv_id)
    if not cv or cv.user_id != user.id:
        raise HTTPException(404, "Không tìm thấy CV")
    existing = db.scalar(select(Candidate).where(Candidate.jd_id == jd.id, Candidate.applicant_id == user.id))
    if existing and existing.stage != "withdrawn":
        raise HTTPException(409, "Bạn đã ứng tuyển vị trí này")

    match = ats.score(cv.redacted_text, jd.content, [c["name"] for c in competencies_for_ai(jd)])["score"]
    if existing:  # nộp lại sau khi đã rút đơn
        c = existing
        c.cv_id, c.cv_text, c.cover_note, c.match_score, c.stage = cv.id, cv.redacted_text, body.cover_note, match, "applied"
    else:
        c = Candidate(org_id=jd.org_id, jd_id=jd.id, full_name=user.full_name, email=user.email,
                      cv_text=cv.redacted_text, stage="applied", source="applied", applicant_id=user.id,
                      cv_id=cv.id, cover_note=body.cover_note, match_score=match, created_by=user.id)
        db.add(c)
    db.add(AuditLog(actor_id=user.id, action="application.submit", target=str(jd.id), detail={"match": match}))
    db.commit()
    return {"id": str(c.id), "status": APPLICANT_STATUS["applied"]}


@router.get("/me/applications")
def my_applications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Candidate, JobDescription, Organization.name)
                      .join(JobDescription, JobDescription.id == Candidate.jd_id)
                      .join(Organization, Organization.id == Candidate.org_id)
                      .where(Candidate.applicant_id == user.id)
                      .order_by(Candidate.created_at.desc())).all()
    return [{"id": str(c.id), "jd_id": str(jd.id), "title": jd.title, "level": jd.level, "company": company,
             "stage": c.stage, "status": APPLICANT_STATUS.get(c.stage, c.stage), "match_score": c.match_score,
             "applied_at": c.created_at.isoformat(), "can_withdraw": c.stage == "applied"}
            for c, jd, company in rows]


@router.post("/me/applications/{cid}/withdraw")
def withdraw(cid: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Candidate, cid)
    if not c or c.applicant_id != user.id:
        raise HTTPException(404, "Không tìm thấy đơn ứng tuyển")
    if c.stage != "applied":
        raise HTTPException(409, "Công ty đã xử lý đơn này, không thể rút")
    c.stage = "withdrawn"
    db.commit()
    return {"ok": True}
