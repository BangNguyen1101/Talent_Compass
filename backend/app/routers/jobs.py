"""BO-15: JD & khung năng lực.

Luồng ở tổ chức công ty (HITL bắt buộc):
  HR soạn (AI hỗ trợ) -> kiểm tra thiên vị/nhất quán/định biên -> gửi duyệt
  -> Quản lý duyệt đủ số cấp của tổ chức -> ban hành (published). Sửa JD đã gửi = phải duyệt lại.
Trường học: cố vấn ban hành JD mẫu cho sinh viên luyện tập. Sinh viên: JD riêng tư."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.ai import services
from app.ai.llm import LLMError, model_name
from app.core import ats, bias, jd_checks
from app.db import get_db
from app.models import (
    CV,
    AuditLog,
    Candidate,
    Competency,
    HeadcountPlan,
    JDApproval,
    JDCompetency,
    JobDescription,
    JobStatus,
    Organization,
    Role,
    User,
)
from app.schemas import (
    JDCompetencyIO,
    JDGenerateIn,
    JobCheckOut,
    JobIn,
    JobOut,
    NeutralizeIn,
    ReviewIn,
    StatusIn,
)
from app.security import get_current_user, require_org, require_roles

router = APIRouter(prefix="/jobs", tags=["jobs"])

HIRING_ROLES = {Role.hr, Role.manager, Role.hiring_lead, Role.interviewer, Role.admin}
COMPANY_STAFF = {Role.hr, Role.manager, Role.hiring_lead, Role.interviewer}


def require_hr(user: User = Depends(require_roles(Role.hr))) -> User:
    """Chỉ HR thuộc một công ty mới soạn/tạo JD."""
    require_org(user)
    return user
ACTIVE_STATUSES = (JobStatus.pending_approval, JobStatus.published)


# ---------------------------------------------------------------- helpers

def jd_markdown(d) -> str:
    def bullets(items: list[str]) -> str:
        return "\n".join(f"- {i}" for i in items) or "- (chưa có)"

    return (f"## Tổng quan\n{d.summary}\n\n## Trách nhiệm\n{bullets(d.responsibilities)}\n\n"
            f"## Yêu cầu\n{bullets(d.requirements)}\n\n## Ưu tiên\n{bullets(d.nice_to_have)}")


def comps_out(jd: JobDescription) -> list[JDCompetencyIO]:
    return [JDCompetencyIO(name=link.competency.name, category=link.competency.category,
                           description=link.competency.description, required_level=link.required_level,
                           weight=link.weight, rubric=link.competency.rubric.get("levels", []))
            for link in jd.competencies]


def competencies_for_ai(jd: JobDescription) -> list[dict]:
    return [c.model_dump() for c in comps_out(jd)]


def approvals_of(db: Session, jd_id: uuid.UUID) -> list[dict]:
    rows = db.execute(select(JDApproval, User.full_name).join(User, User.id == JDApproval.approver_id)
                      .where(JDApproval.jd_id == jd_id).order_by(JDApproval.id)).all()
    return [{"level": a.level, "decision": a.decision, "comment": a.comment, "by": name,
             "at": a.created_at.isoformat() if a.created_at else None} for a, name in rows]


def can_view(jd: JobDescription, user: User) -> bool:
    if jd.created_by == user.id or user.role == Role.admin:
        return True
    if user.org_id and jd.org_id == user.org_id and user.role in COMPANY_STAFF:
        return True  # nhân sự công ty thấy mọi JD của công ty mình (kể cả nháp, chờ duyệt)
    # Sàn việc làm: JD đã ban hành của mọi công ty ai cũng xem được
    return jd.status == JobStatus.published and jd.org_id is not None


def can_edit(jd: JobDescription, user: User) -> bool:
    """Chỉ HR của công ty sở hữu JD được sửa/xóa/gửi duyệt."""
    if user.role == Role.admin:
        return True
    return user.role == Role.hr and user.org_id is not None and jd.org_id == user.org_id


def to_out(db: Session, jd: JobDescription, user: User) -> JobOut:
    company = db.scalar(select(Organization.name).where(Organization.id == jd.org_id)) if jd.org_id else None
    my_app = None
    if user.role == Role.student:
        my_app = db.scalar(select(Candidate.stage).where(Candidate.jd_id == jd.id, Candidate.applicant_id == user.id))
    # Thông tin nội bộ (lịch sử duyệt, cảnh báo thiên vị, ngân hàng câu hỏi phỏng vấn) chỉ dành cho
    # nhân sự của công ty sở hữu JD; ứng viên trên sàn không được thấy.
    internal = user.role == Role.admin or (
        user.org_id is not None and jd.org_id == user.org_id and user.role in COMPANY_STAFF)
    return JobOut(company=company, my_application=my_app, internal=internal,
                  id=jd.id, title=jd.title, level=jd.level, department=jd.department, job_family=jd.job_family,
                  headcount=jd.headcount, content=jd.content, status=jd.status, created_at=jd.created_at,
                  created_by=jd.created_by, org_id=jd.org_id, competencies=comps_out(jd),
                  bias_issues=(jd.bias_issues or []) if internal else [],
                  question_bank=(jd.question_bank or []) if internal else [],
                  approvals=approvals_of(db, jd.id) if internal else [], can_edit=can_edit(jd, user))


def get_job_or_404(db: Session, jd_id: uuid.UUID, user: User) -> JobDescription:
    jd = db.get(JobDescription, jd_id)
    if not jd or not can_view(jd, user):
        raise HTTPException(404, "Không tìm thấy JD")
    return jd


def _org(db: Session, user: User) -> Organization | None:
    return db.get(Organization, user.org_id) if user.org_id else None


def _related(db: Session, org_id, job_family: str, exclude_id=None) -> list[JobDescription]:
    if not org_id or not job_family.strip():
        return []
    q = select(JobDescription).where(JobDescription.org_id == org_id,
                                     func.lower(JobDescription.job_family) == job_family.strip().lower(),
                                     JobDescription.status.in_(ACTIVE_STATUSES))
    if exclude_id:
        q = q.where(JobDescription.id != exclude_id)
    return list(db.scalars(q).unique().all())


def run_checks(db: Session, user: User, body: JobIn, exclude_id=None) -> JobCheckOut:
    issues = bias.detect(f"{body.title}\n{body.content}")
    related = _related(db, user.org_id, body.job_family, exclude_id)
    consistency = jd_checks.consistency_warnings(
        {"level": body.level, "competencies": [c.model_dump() for c in body.competencies]},
        [{"title": r.title, "level": r.level, "competencies": competencies_for_ai(r)} for r in related])

    headcount = None
    org = _org(db, user)
    if org and org.kind == "company" and body.department and body.job_family:
        plan = db.scalar(select(HeadcountPlan).where(
            HeadcountPlan.org_id == org.id,
            func.lower(HeadcountPlan.department) == body.department.strip().lower(),
            func.lower(HeadcountPlan.job_family) == body.job_family.strip().lower()))
        q = select(func.coalesce(func.sum(JobDescription.headcount), 0)).where(
            JobDescription.org_id == org.id,
            func.lower(JobDescription.department) == body.department.strip().lower(),
            func.lower(JobDescription.job_family) == body.job_family.strip().lower(),
            JobDescription.status.in_(ACTIVE_STATUSES))
        if exclude_id:
            q = q.where(JobDescription.id != exclude_id)
        committed = db.scalar(q) or 0
        headcount = jd_checks.headcount_warning(
            body.headcount, {"approved": plan.approved, "filled": plan.filled} if plan else None, committed)
    return JobCheckOut(bias=issues, consistency=consistency, headcount=headcount)


def _apply(db: Session, jd: JobDescription, body: JobIn) -> None:
    jd.title, jd.level, jd.content = body.title, body.level, body.content
    jd.department, jd.job_family, jd.headcount = body.department, body.job_family, body.headcount
    jd.bias_issues = bias.detect(f"{body.title}\n{body.content}")
    jd.competencies.clear()
    db.flush()
    seen: set[str] = set()
    for c in body.competencies:
        key = c.name.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        comp = None
        if jd.org_id:  # dùng lại năng lực cùng tên trong từ điển của tổ chức
            comp = db.scalar(select(Competency).where(Competency.org_id == jd.org_id,
                                                      func.lower(Competency.name) == key))
        if comp is None:
            comp = Competency(org_id=jd.org_id, name=c.name.strip())
            db.add(comp)
        comp.category, comp.description = c.category, c.description
        comp.rubric = {"levels": [r.model_dump() for r in c.rubric]}
        db.flush()
        jd.competencies.append(JDCompetency(competency_id=comp.id, required_level=c.required_level,
                                            weight=c.weight, competency=comp))


def _audit(db: Session, user: User, action: str, jd: JobDescription, **detail) -> None:
    db.add(AuditLog(actor_id=user.id, action=action, target=str(jd.id), detail=detail))


# ---------------------------------------------------------------- endpoints

@router.post("/generate", response_model=JobIn)
def generate_jd(body: JDGenerateIn, user: User = Depends(require_hr), db: Session = Depends(get_db)):
    """AI soạn bản nháp JD + khung năng lực (chưa lưu). Dùng phong cách thương hiệu, từ điển năng lực
    và JD đã ban hành cùng nhóm vị trí của tổ chức làm tham chiếu."""
    org = _org(db, user)
    dictionary, references = [], []
    if org:
        dictionary = list(db.scalars(select(Competency.name).where(Competency.org_id == org.id).distinct()).all())
        refs = _related(db, org.id, body.job_family) if body.job_family else []
        if not refs:
            refs = list(db.scalars(select(JobDescription).where(
                JobDescription.org_id == org.id, JobDescription.status == JobStatus.published,
                JobDescription.title.ilike(f"%{body.title.split()[0]}%")).limit(3)).unique().all())
        references = [{"title": r.title, "level": r.level,
                       "competencies": [{"name": c["name"], "required_level": c["required_level"]}
                                        for c in competencies_for_ai(r)]} for r in refs[:3]]
    try:
        draft = services.draft_jd(body.title, body.level, body.context,
                                  brand_voice=org.brand_voice if org else "",
                                  dictionary=dictionary[:60], references=references)
    except LLMError as e:
        raise HTTPException(502, str(e)) from e
    db.add(AuditLog(actor_id=user.id, action="jd.generate", target=body.title,
                    detail={"model": model_name("fast"), "references": len(references)}))
    db.commit()
    return JobIn(title=draft.title, level=body.level, department=body.department, job_family=body.job_family,
                 content=jd_markdown(draft),
                 competencies=[JDCompetencyIO(**c.model_dump()) for c in draft.competencies])


@router.post("/check", response_model=JobCheckOut)
def check_job(body: JobIn, exclude_id: uuid.UUID | None = None, user: User = Depends(require_hr),
              db: Session = Depends(get_db)):
    return run_checks(db, user, body, exclude_id)


@router.post("/neutralize")
def neutralize(body: NeutralizeIn, user: User = Depends(require_hr)):
    """Phát hiện và AI viết lại câu thiên vị."""
    issues = bias.detect(body.content)
    if not issues:
        return {"content": body.content, "changes": [], "remaining": []}
    try:
        result = services.neutral_rewrite(body.content, issues)
    except LLMError as e:
        raise HTTPException(502, str(e)) from e
    return {"content": result.content, "changes": result.changes, "remaining": bias.detect(result.content)}


@router.post("", response_model=JobOut, status_code=201)
def create_job(body: JobIn, user: User = Depends(require_hr), db: Session = Depends(get_db)):
    jd = JobDescription(created_by=user.id, org_id=user.org_id, title=body.title, status=JobStatus.draft)
    db.add(jd)
    _apply(db, jd, body)
    _audit(db, user, "jd.create", jd)
    db.commit()
    db.refresh(jd)
    return to_out(db, jd, user)


@router.get("", response_model=list[JobOut])
def list_jobs(scope: str = "all", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """scope=org: mọi JD của công ty mình (nhân sự công ty quản lý).
    scope=all: JD đã ban hành của mọi công ty (+ JD công ty mình nếu là nhân sự)."""
    is_staff = user.org_id is not None and user.role in COMPANY_STAFF
    if scope == "org":
        if not is_staff:
            return []
        q = select(JobDescription).where(JobDescription.org_id == user.org_id)
    else:
        companies = select(Organization.id).where(Organization.kind == "company")
        conds = [(JobDescription.status == JobStatus.published) & JobDescription.org_id.in_(companies)]
        if is_staff:
            conds.append(JobDescription.org_id == user.org_id)
        q = select(JobDescription).where(or_(*conds))
    jobs = db.scalars(q.order_by(JobDescription.created_at.desc())).unique().all()
    return [to_out(db, j, user) for j in jobs]


@router.get("/board")
def job_board(q: str = "", company: uuid.UUID | None = None, level: str = "", job_family: str = "",
              department: str = "", competency: str = "", cv_id: uuid.UUID | None = None,
              sort: str = "newest", limit: int = Query(50, le=100), offset: int = 0,
              user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Sàn việc làm: JD đã ban hành của mọi công ty, tìm kiếm + lọc.
    Có cv_id: chấm mức khớp CV-JD bằng luật ATS (không tốn AI) và cho phép sắp xếp theo độ phù hợp."""
    stmt = (select(JobDescription, Organization.name).join(Organization, Organization.id == JobDescription.org_id)
            .where(JobDescription.status == JobStatus.published, Organization.kind == "company"))
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(JobDescription.title.ilike(like), JobDescription.content.ilike(like),
                              Organization.name.ilike(like)))
    if company:
        stmt = stmt.where(JobDescription.org_id == company)
    if level:
        stmt = stmt.where(JobDescription.level == level)
    if job_family:
        stmt = stmt.where(func.lower(JobDescription.job_family) == job_family.lower())
    if department:
        stmt = stmt.where(func.lower(JobDescription.department) == department.lower())
    if competency.strip():
        stmt = stmt.where(JobDescription.id.in_(
            select(JDCompetency.jd_id).join(Competency, Competency.id == JDCompetency.competency_id)
            .where(Competency.name.ilike(f"%{competency.strip()}%"))))
    rows = db.execute(stmt.order_by(JobDescription.created_at.desc())).unique().all()

    cv_text = None
    if cv_id:
        cv = db.get(CV, cv_id)
        if not cv or cv.user_id != user.id:
            raise HTTPException(404, "Không tìm thấy CV")
        cv_text = cv.redacted_text
    applied = set(db.scalars(select(Candidate.jd_id).where(Candidate.applicant_id == user.id)).all())

    items = []
    for jd, company_name in rows:
        comps = comps_out(jd)
        item = {"id": str(jd.id), "title": jd.title, "level": jd.level, "department": jd.department,
                "job_family": jd.job_family, "headcount": jd.headcount, "company": company_name,
                "company_id": str(jd.org_id), "created_at": jd.created_at.isoformat(),
                "competencies": [c.name for c in comps], "summary": jd.content[:240],
                "applied": jd.id in applied, "match": None}
        if cv_text is not None:
            r = ats.score(cv_text, jd.content, [c.name for c in comps])
            item["match"] = {"score": r["score"], "matched": r["matched_keywords"][:8],
                             "missing": r["missing_keywords"][:8]}
        items.append(item)
    if sort == "match" and cv_text is not None:
        items.sort(key=lambda i: -i["match"]["score"])
    return {"total": len(items), "items": items[offset: offset + limit]}


@router.get("/board/facets")
def board_facets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Giá trị cho bộ lọc: công ty, cấp độ, nhóm vị trí, phòng ban (chỉ từ JD đã ban hành)."""
    base = (select(JobDescription, Organization).join(Organization, Organization.id == JobDescription.org_id)
            .where(JobDescription.status == JobStatus.published, Organization.kind == "company"))
    rows = db.execute(base).unique().all()
    companies = {str(o.id): o.name for _, o in rows}
    return {
        "companies": [{"id": k, "name": v, "jobs": sum(1 for j, _ in rows if str(j.org_id) == k)}
                      for k, v in sorted(companies.items(), key=lambda kv: kv[1])],
        "levels": sorted({j.level for j, _ in rows}, key=jd_checks.level_rank),
        "job_families": sorted({j.job_family for j, _ in rows if j.job_family}),
        "departments": sorted({j.department for j, _ in rows if j.department}),
    }


@router.get("/pending-approval", response_model=list[JobOut])
def pending(user: User = Depends(require_roles(Role.manager)), db: Session = Depends(get_db)):
    jobs = db.scalars(select(JobDescription).where(JobDescription.org_id == user.org_id,
                                                   JobDescription.status == JobStatus.pending_approval)
                      .order_by(JobDescription.created_at)).unique().all()
    return [to_out(db, j, user) for j in jobs]


@router.get("/{jd_id}", response_model=JobOut)
def get_job(jd_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return to_out(db, get_job_or_404(db, jd_id, user), user)


@router.get("/{jd_id}/checks", response_model=JobCheckOut)
def job_checks(jd_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    jd = get_job_or_404(db, jd_id, user)
    body = JobIn(title=jd.title, level=jd.level, department=jd.department, job_family=jd.job_family,
                 headcount=jd.headcount, content=jd.content, competencies=comps_out(jd))
    return run_checks(db, user, body, jd.id)


@router.put("/{jd_id}", response_model=JobOut)
def update_job(jd_id: uuid.UUID, body: JobIn, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    jd = get_job_or_404(db, jd_id, user)
    if not can_edit(jd, user):
        raise HTTPException(403, "Không có quyền sửa JD này")
    org = _org(db, user)
    was = jd.status
    _apply(db, jd, body)
    if org and org.kind == "company" and was in (JobStatus.pending_approval, JobStatus.published):
        jd.status = JobStatus.draft  # nội dung đã đổi -> phải duyệt lại (HITL)
    _audit(db, user, "jd.update", jd, previous_status=was.value)
    db.commit()
    db.refresh(jd)
    return to_out(db, jd, user)


@router.post("/{jd_id}/submit", response_model=JobOut)
def submit(jd_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    jd = get_job_or_404(db, jd_id, user)
    if not can_edit(jd, user):
        raise HTTPException(403, "Không có quyền")
    if not jd.org_id:
        raise HTTPException(422, "JD cá nhân không cần ban hành")
    if jd.status not in (JobStatus.draft, JobStatus.rejected):
        raise HTTPException(409, "JD đang chờ duyệt hoặc đã ban hành")
    if bias.has_high(jd.bias_issues or []):
        raise HTTPException(422, "JD còn ngôn ngữ thiên vị mức cao, hãy sửa trước khi gửi duyệt")
    if not jd.competencies:
        raise HTTPException(422, "JD cần có khung năng lực")
    org = db.get(Organization, jd.org_id)
    if org.jd_approval_levels > 0:
        managers = db.scalar(select(func.count(User.id)).where(
            User.org_id == org.id, User.role == Role.manager, User.is_active.is_(True))) or 0
        if managers < org.jd_approval_levels:
            raise HTTPException(422, f"Công ty cần ít nhất {org.jd_approval_levels} quản lý phê duyệt "
                                     f"(hiện có {managers}). Mời quản lý tham gia bằng mã công ty, "
                                     "hoặc đổi số cấp duyệt trong Cài đặt.")
    db.add(JDApproval(jd_id=jd.id, level=0, approver_id=user.id, decision="submitted"))
    if org.jd_approval_levels == 0:
        jd.status = JobStatus.published  # công ty chọn không cần duyệt: HR tự ban hành
    else:
        jd.status = JobStatus.pending_approval
    _audit(db, user, "jd.submit", jd)
    db.commit()
    return to_out(db, jd, user)


@router.post("/{jd_id}/review", response_model=JobOut)
def review(jd_id: uuid.UUID, body: ReviewIn, user: User = Depends(require_roles(Role.manager)),
           db: Session = Depends(get_db)):
    jd = get_job_or_404(db, jd_id, user)
    if jd.org_id != user.org_id or jd.status != JobStatus.pending_approval:
        raise HTTPException(409, "JD không ở trạng thái chờ duyệt")
    if jd.created_by == user.id:
        raise HTTPException(403, "Không thể tự duyệt JD do mình tạo")
    org = db.get(Organization, jd.org_id)
    last_submit = db.scalar(select(func.max(JDApproval.id)).where(JDApproval.jd_id == jd.id,
                                                                  JDApproval.decision == "submitted")) or 0
    cycle = list(db.scalars(select(JDApproval).where(JDApproval.jd_id == jd.id, JDApproval.id > last_submit,
                                                     JDApproval.decision == "approved")).all())
    if any(a.approver_id == user.id for a in cycle):
        raise HTTPException(409, "Bạn đã duyệt JD này ở cấp trước; cần người duyệt khác")
    if body.decision == "rejected" and not body.comment.strip():
        raise HTTPException(422, "Cần ghi lý do khi từ chối")
    level = len(cycle) + 1
    db.add(JDApproval(jd_id=jd.id, level=level, approver_id=user.id, decision=body.decision, comment=body.comment))
    if body.decision == "rejected":
        jd.status = JobStatus.rejected
    elif level >= org.jd_approval_levels:
        jd.status = JobStatus.published
    _audit(db, user, f"jd.{body.decision}", jd, level=level)
    db.commit()
    return to_out(db, jd, user)


@router.post("/{jd_id}/status", response_model=JobOut)
def set_status(jd_id: uuid.UUID, body: StatusIn, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    jd = get_job_or_404(db, jd_id, user)
    if not can_edit(jd, user):
        raise HTTPException(403, "Không có quyền")
    jd.status = JobStatus(body.status)
    _audit(db, user, f"jd.{body.status}", jd)
    db.commit()
    return to_out(db, jd, user)


@router.post("/{jd_id}/question-bank", response_model=JobOut)
def gen_question_bank(jd_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    jd = get_job_or_404(db, jd_id, user)
    if not (can_edit(jd, user) or user.role in HIRING_ROLES):
        raise HTTPException(403, "Không có quyền")
    comps = competencies_for_ai(jd)
    if not comps:
        raise HTTPException(422, "JD chưa có khung năng lực")
    try:
        bank = services.question_bank(f"# {jd.title}\n{jd.content}", jd.level, comps)
    except LLMError as e:
        raise HTTPException(502, str(e)) from e
    jd.question_bank = [i.model_dump() for i in bank.items]
    db.commit()
    return to_out(db, jd, user)


@router.delete("/{jd_id}", status_code=204)
def delete_job(jd_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    jd = get_job_or_404(db, jd_id, user)
    if not can_edit(jd, user):
        raise HTTPException(403, "Không có quyền xóa JD này")
    db.delete(jd)
    db.commit()
