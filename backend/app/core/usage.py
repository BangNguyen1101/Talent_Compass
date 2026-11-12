"""Kiểm soát chi phí AI: ghi nhận token/chi phí từng lượt gọi và áp hạn mức mỗi người/ngày."""

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal
from app.models import LLMUsage
from app.security import current_actor

log = logging.getLogger("talentcompass.usage")

# USD cho 1 triệu token (đầu vào, đầu ra) — giá công bố của Anthropic
PRICES: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
    # Giá Gemini tham khảo (gói trả phí, prompt ≤200K token); gói miễn phí của Google không tính tiền
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.00),
}


class QuotaExceeded(RuntimeError):
    pass


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    # Gemini có thể trả tên model kèm hậu tố phiên bản: khớp theo tiền tố dài nhất
    key = model if model in PRICES else max((k for k in PRICES if model.startswith(k)), key=len, default=None)
    pin, pout = PRICES.get(key, (2.00, 10.00)) if key else (2.00, 10.00)
    return round(input_tokens / 1e6 * pin + output_tokens / 1e6 * pout, 6)


def check_quota() -> None:
    actor = current_actor.get()
    if actor is None:
        return
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    with SessionLocal() as db:
        used = db.scalar(
            select(func.count(LLMUsage.id)).where(
                LLMUsage.user_id == actor[0], LLMUsage.created_at >= start
            )
        )
    if (used or 0) >= get_settings().daily_ai_quota_per_user:
        raise QuotaExceeded("Bạn đã dùng hết lượt AI hôm nay, vui lòng quay lại vào ngày mai")


def record(feature: str, model: str, input_tokens: int, output_tokens: int) -> None:
    actor = current_actor.get()
    try:
        with SessionLocal() as db:
            db.add(LLMUsage(
                user_id=actor[0] if actor else None,
                org_id=actor[1] if actor else None,
                feature=feature, model=model,
                input_tokens=input_tokens, output_tokens=output_tokens,
                cost_usd=estimate_cost(model, input_tokens, output_tokens) if model != "mock" else 0,
            ))
            db.commit()
    except Exception:  # ghi log chi phí không được làm hỏng tác vụ chính
        log.exception("Không ghi được llm_usage")
