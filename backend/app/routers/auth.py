from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import COMPANY_ROLES, ORG_CREATOR_ROLES, SCHOOL_ROLES, Organization, Role, User
from app.schemas import LoginIn, MeUpdate, RegisterIn, TokenOut, UserOut
from app.security import create_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if body.role == Role.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Không thể tự đăng ký tài khoản admin")
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email đã được đăng ký")

    org_id = None
    if body.join_code:
        org = db.scalar(select(Organization).where(Organization.join_code == body.join_code.strip().upper()))
        if not org:
            raise HTTPException(404, "Mã tổ chức không đúng")
        allowed = COMPANY_ROLES if org.kind == "company" else SCHOOL_ROLES
        if body.role not in allowed:
            raise HTTPException(422, "Vai trò này không thuộc loại tổ chức của mã đã nhập")
        org_id = org.id
    elif body.organization_name:
        kind = ORG_CREATOR_ROLES.get(body.role)
        if kind is None:
            raise HTTPException(422, "Chỉ HR (công ty) hoặc cố vấn (trường) được tạo tổ chức mới")
        org = Organization(name=body.organization_name, kind=kind)
        db.add(org)
        db.flush()
        org_id = org.id
    elif body.role != Role.student:
        raise HTTPException(422, "Vai trò này cần mã tổ chức hoặc tạo tổ chức mới")

    user = User(email=email, full_name=body.full_name, role=body.role, department=body.department,
                password_hash=hash_password(body.password), org_id=org_id)
    db.add(user)
    db.commit()
    return TokenOut(access_token=create_token(user), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sai email hoặc mật khẩu")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Tài khoản đã bị vô hiệu hóa")
    return TokenOut(access_token=create_token(user), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: MeUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    db.commit()
    return user


@router.post("/join", response_model=UserOut)
def join_org(join_code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Sinh viên tự do tham gia trường (để cố vấn theo dõi) bằng mã."""
    if user.org_id:
        raise HTTPException(409, "Bạn đã thuộc một tổ chức")
    org = db.scalar(select(Organization).where(Organization.join_code == join_code.strip().upper()))
    allowed = COMPANY_ROLES if org and org.kind == "company" else SCHOOL_ROLES
    if not org or user.role not in allowed:
        raise HTTPException(404, "Mã tổ chức không đúng hoặc không phù hợp vai trò")
    user.org_id = org.id
    db.commit()
    return user
