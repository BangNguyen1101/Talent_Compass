"""BO-15: JD & khung năng lực. HR đăng JD cho tổ chức; sinh viên có thể tạo JD riêng
(dán JD từ tin tuyển dụng) để luyện CV/phỏng vấn — JD riêng chỉ người tạo thấy."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai import services
from app.ai.llm import LLMError, model_name
from app.ai.schemas import JDDraft
from app.db import get_db
from app.models import AuditLog, Competency, JDCompetency, JobDescription, JobStatus, Role, User
from app.schemas import JDCompetencyIO, JDGenerateIn, JobIn, JobOut
from app.security import get_current_user

router = APIRouter(prefix="/jobs", tags=["jobs"])


def jd_markdown(d: JDDraft) -> str:
    def bullets(items: list[str]) -> str:
        return "\n".join(f"- {i}" for i in items) or "- (chưa có)"

    return (f"## Tổng quan\n{d.summary}\n\n## Trách nhiệm\n{bullets(d.responsibilities)}\n\n"
            f"## Yêu cầu\n{bullets(d.requirements)}\n\n## Ưu tiên\n{bullets(d.nice_to_have)}")


def to_out(jd: JobDescription) -> JobOut:
    return JobOut(
        id=jd.id, title=jd.title, level=jd.level, content=jd.content, status=jd.status,
        created_at=jd.created_at,
        competencies=[
            JDCompetencyIO(name=l.competency.name, category=l.competency.category,
                           description=l.competency.description, required_level=l.required_level,
                           weight=l.weight, rubric=l.competency.rubric.get("levels", []))
            for l in jd.competencies
        ],
    )


def competencies_for_ai(jd: JobDescription) -> list[dict]:
    return [c.model_dump() for c in to_out(jd).competencies]


def can_view(jd: JobDescription, user: User) -> bool:
    if jd.created_by == user.id or user.role == Role.admin:
        return True
    if user.org_id and jd.org_id == user.org_id:
        return True
    return jd.status == JobStatus.published and jd.org_id is not None


def get_job_or_404(db: Session, jd_id: uuid.UUID, user: User) -> JobDescription:
    jd = db.get(JobDescription, jd_id)
    if not jd or not can_view(jd, user):
        raise HTTPException(404, "Không tìm thấy JD")
    return jd


def _can_edit(jd: JobDescription, user: User) -> bool:
    return jd.created_by == user.id or (
        user.role == Role.hr and user.org_id is not None and jd.org_id == user.org_id
    )


def _apply(db: Session, jd: JobDescription, body: JobIn, user: User) -> None:
    jd.title, jd.level, jd.content = body.title, body.level, body.content
    # Sinh viên không được công khai JD riêng
    jd.status = body.status if user.role in (Role.hr, Role.admin) else JobStatus.draft
    jd.competencies.clear()
    db.flush()
    seen: set[str] = set()
    for c in body.competencies:
        key = c.name.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        comp = None
        if jd.org_id:  # dùng lại năng lực cùng tên trong tổ chức
            comp = db.scalar(select(Competency).where(
                Competency.org_id == jd.org_id, Competency.name.ilike(c.name.strip())))
        if comp is None:
            comp = Competency(org_id=jd.org_id, name=c.name.strip())
            db.add(comp)
        comp.category, comp.description = c.category, c.description
        comp.rubric = {"levels": [r.model_dump() for r in c.rubric]}
        db.flush()
        jd.competencies.append(JDCompetency(competency_id=comp.id, required_level=c.required_level,
                                            weight=c.weight, competency=comp))


@router.post("/generate", response_model=JobIn)
def generate_jd(body: JDGenerateIn, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    """AI soạn bản nháp JD + khung năng lực. Chưa lưu: người dùng xem, sửa rồi mới lưu."""
    try:
        draft = services.draft_jd(body.title, body.level, body.context)
    except LLMError as e:
        raise HTTPException(502, str(e)) from e
    db.add(AuditLog(actor_id=user.id, action="jd.generate", target=body.title,
                    detail={"model": model_name("fast")}))
    db.commit()
    return JobIn(
        title=draft.title, level=body.level, content=jd_markdown(draft),
        competencies=[JDCompetencyIO(**c.model_dump()) for c in draft.competencies],
    )


@router.post("", response_model=JobOut, status_code=201)
def create_job(body: JobIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    jd = JobDescription(created_by=user.id,
                        org_id=user.org_id if user.role == Role.hr else None, title=body.title)
    db.add(jd)
    _apply(db, jd, body, user)
    db.commit()
    db.refresh(jd)
    return to_out(jd)


@router.get("", response_model=list[JobOut])
def list_jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conds = [JobDescription.created_by == user.id,
             (JobDescription.status == JobStatus.published) & JobDescription.org_id.is_not(None)]
    if user.org_id:
        conds.append(JobDescription.org_id == user.org_id)
    jobs = db.scalars(select(JobDescription).where(or_(*conds))
                      .order_by(JobDescription.created_at.desc())).unique().all()
    return [to_out(j) for j in jobs]


@router.get("/{jd_id}", response_model=JobOut)
def get_job(jd_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return to_out(get_job_or_404(db, jd_id, user))


@router.put("/{jd_id}", response_model=JobOut)
def update_job(jd_id: uuid.UUID, body: JobIn, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    jd = get_job_or_404(db, jd_id, user)
    if not _can_edit(jd, user):
        raise HTTPException(403, "Không có quyền sửa JD này")
    _apply(db, jd, body, user)
    db.commit()
    db.refresh(jd)
    return to_out(jd)


@router.delete("/{jd_id}", status_code=204)
def delete_job(jd_id: uuid.UUID, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    jd = get_job_or_404(db, jd_id, user)
    if not _can_edit(jd, user):
        raise HTTPException(403, "Không có quyền xóa JD này")
    db.delete(jd)
    db.commit()
