import contextvars
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Role, User

_bearer = HTTPBearer(auto_error=False)

# Người dùng của request hiện tại: dùng để ghi chi phí AI và áp hạn mức
current_actor: contextvars.ContextVar[tuple[uuid.UUID, uuid.UUID | None] | None] = (
    contextvars.ContextVar("current_actor", default=None)
)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user: User) -> str:
    s = get_settings()
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "org": str(user.org_id) if user.org_id else None,
        "exp": datetime.now(UTC) + timedelta(minutes=s.jwt_expire_minutes),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Chưa đăng nhập")
    try:
        payload = jwt.decode(creds.credentials, get_settings().jwt_secret, algorithms=["HS256"])
        user = db.get(User, uuid.UUID(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        user = None
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Phiên đăng nhập không hợp lệ")
    current_actor.set((user.id, user.org_id))
    return user


def require_roles(*roles: Role):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles and user.role != Role.admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Vai trò của bạn không có quyền này")
        return user

    return checker


class ActorMiddleware:
    """Middleware ASGI: đọc JWT để biết ai đang gọi, phục vụ ghi chi phí AI theo người/tổ chức.
    (Biến ngữ cảnh đặt ở đây truyền được xuống endpoint đồng bộ chạy trong threadpool.)"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            auth = dict(scope.get("headers") or []).get(b"authorization", b"").decode()
            if auth.lower().startswith("bearer "):
                try:
                    p = jwt.decode(auth[7:], get_settings().jwt_secret, algorithms=["HS256"])
                    org = p.get("org")
                    current_actor.set((uuid.UUID(p["sub"]), uuid.UUID(org) if org else None))
                except (jwt.PyJWTError, KeyError, ValueError):
                    pass
        await self.app(scope, receive, send)


def require_org(user: User) -> uuid.UUID:
    if user.org_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bạn cần thuộc một tổ chức để dùng chức năng này")
    return user.org_id
