"""Quản lý tổ chức: thông tin, phong cách thương hiệu, cấp duyệt, thành viên, định biên."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import COMPANY_ROLES, SCHOOL_ROLES, HeadcountPlan, Organization, Role, User
from app.schemas import HeadcountIn, HeadcountOut, MemberOut, MemberUpdate, OrgOut, OrgUpdate
from app.security import get_current_user, require_org, require_roles

router = APIRouter(prefix="/org", tags=["organization"])

ORG_ADMINS = (Role.hr, Role.advisor)
SEE_JOIN_CODE = {Role.hr, Role.advisor, Role.manager, Role.hiring_lead, Role.admin}


@router.get("", response_model=OrgOut)
def get_org(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.get(Organization, require_org(user))
    out = OrgOut.model_validate(org)
    if user.role not in SEE_JOIN_CODE:
        out.join_code = None
    return out


@router.patch("", response_model=OrgOut)
def update_org(body: OrgUpdate, user: User = Depends(require_roles(*ORG_ADMINS)),
               db: Session = Depends(get_db)):
    org = db.get(Organization, require_org(user))
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(org, field, value)
    db.commit()
    return org


@router.get("/members", response_model=list[MemberOut])
def members(user: User = Depends(require_roles(Role.hr, Role.advisor, Role.manager, Role.hiring_lead)),
            db: Session = Depends(get_db)):
    return db.scalars(select(User).where(User.org_id == require_org(user)).order_by(User.full_name)).all()


@router.patch("/members/{member_id}", response_model=MemberOut)
def update_member(member_id: uuid.UUID, body: MemberUpdate, user: User = Depends(require_roles(*ORG_ADMINS)),
                  db: Session = Depends(get_db)):
    member = db.get(User, member_id)
    if not member or member.org_id != require_org(user):
        raise HTTPException(404, "Không tìm thấy thành viên")
    org = db.get(Organization, user.org_id)
    if body.role is not None:
        allowed = COMPANY_ROLES if org.kind == "company" else SCHOOL_ROLES
        if body.role not in allowed:
            raise HTTPException(422, "Vai trò không phù hợp loại tổ chức")
        if member.id == user.id and body.role != user.role:
            raise HTTPException(422, "Không thể tự đổi vai trò của chính mình")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(member, field, value)
    db.commit()
    return member


# ---------------------------------------------------------------- Định biên (BO-15)

@router.get("/headcount", response_model=list[HeadcountOut])
def list_headcount(user: User = Depends(require_roles(Role.hr, Role.manager)), db: Session = Depends(get_db)):
    return db.scalars(select(HeadcountPlan).where(HeadcountPlan.org_id == require_org(user))
                      .order_by(HeadcountPlan.department, HeadcountPlan.job_family)).all()


@router.post("/headcount", response_model=HeadcountOut, status_code=201)
def create_headcount(body: HeadcountIn, user: User = Depends(require_roles(Role.hr, Role.manager)),
                     db: Session = Depends(get_db)):
    plan = HeadcountPlan(org_id=require_org(user), **body.model_dump())
    db.add(plan)
    db.commit()
    return plan


@router.put("/headcount/{plan_id}", response_model=HeadcountOut)
def update_headcount(plan_id: int, body: HeadcountIn, user: User = Depends(require_roles(Role.hr, Role.manager)),
                     db: Session = Depends(get_db)):
    plan = db.get(HeadcountPlan, plan_id)
    if not plan or plan.org_id != require_org(user):
        raise HTTPException(404, "Không tìm thấy định biên")
    for field, value in body.model_dump().items():
        setattr(plan, field, value)
    db.commit()
    return plan


@router.delete("/headcount/{plan_id}", status_code=204)
def delete_headcount(plan_id: int, user: User = Depends(require_roles(Role.hr, Role.manager)),
                     db: Session = Depends(get_db)):
    plan = db.get(HeadcountPlan, plan_id)
    if not plan or plan.org_id != require_org(user):
        raise HTTPException(404, "Không tìm thấy định biên")
    db.delete(plan)
    db.commit()
