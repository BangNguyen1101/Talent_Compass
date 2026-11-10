from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Organization, Role, User
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut
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
    if body.role == Role.hr:
        if not body.organization_name:
            raise HTTPException(422, "Tài khoản HR cần tên tổ chức")
        org = Organization(name=body.organization_name)
        db.add(org)
        db.flush()
        org_id = org.id

    user = User(email=email, full_name=body.full_name, role=body.role,
                password_hash=hash_password(body.password), org_id=org_id)
    db.add(user)
    db.commit()
    return TokenOut(access_token=create_token(user), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sai email hoặc mật khẩu")
    return TokenOut(access_token=create_token(user), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
