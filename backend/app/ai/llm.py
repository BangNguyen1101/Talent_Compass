"""Lớp gọi Claude. Mọi tác vụ AI đều đi qua đây để thống nhất model, xử lý lỗi và ghi log chi phí.

- "fast"  -> model rẻ (mặc định Claude Haiku 5.5): trích xuất CV, soạn JD, sinh câu hỏi
- "smart" -> model mạnh (mặc định Claude Sonnet 5.5): chấm CV, chấm câu trả lời phỏng vấn
  Có bật server-side fallback: nếu model từ chối do bộ lọc an toàn, API tự chạy lại trên model dự phòng.
"""

import logging
from collections.abc import Callable
from typing import Literal, TypeVar

import anthropic
from pydantic import BaseModel

from app.config import get_settings

log = logging.getLogger("talentcompass.llm")

T = TypeVar("T", bound=BaseModel)
Tier = Literal["fast", "smart"]


class LLMError(RuntimeError):
    """Lỗi khi gọi AI, thông điệp thân thiện để trả về cho người dùng."""


_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key, max_retries=2)
    return _client


def model_name(tier: Tier) -> str:
    s = get_settings()
    if s.use_mock_llm:
        return "mock"
    return s.llm_smart_model if tier == "smart" else s.llm_fast_model


def generate(
    *,
    tier: Tier,
    system: str,
    prompt: str,
    output: type[T],
    mock: Callable[[], T],
    max_tokens: int = 16000,
) -> T:
    """Gọi Claude và trả về đối tượng Pydantic đã được kiểm tra định dạng."""
    settings = get_settings()
    if settings.use_mock_llm:
        return mock()

    client = _get_client()
    model = model_name(tier)
    try:
        if tier == "smart":
            response = client.beta.messages.parse(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_format=output,
                output_config={"effort": "medium"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        else:
            response = client.messages.parse(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_format=output,
                output_config={"effort": "low"},
            )
    except anthropic.RateLimitError as e:
        raise LLMError("Hệ thống AI đang quá tải, vui lòng thử lại sau ít phút") from e
    except anthropic.AuthenticationError as e:
        raise LLMError("Sai hoặc thiếu ANTHROPIC_API_KEY trên server") from e
    except anthropic.APIStatusError as e:
        log.exception("Claude API error %s", e.status_code)
        raise LLMError("Dịch vụ AI gặp lỗi, vui lòng thử lại") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Không kết nối được tới dịch vụ AI") from e

    log.info(
        "llm call model=%s in=%s out=%s stop=%s",
        response.model,
        response.usage.input_tokens,
        response.usage.output_tokens,
        response.stop_reason,
    )
    if response.stop_reason == "refusal":
        raise LLMError("AI từ chối xử lý nội dung này. Hãy kiểm tra lại dữ liệu đầu vào.")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise LLMError("Kết quả AI bị cắt ngang hoặc sai định dạng, vui lòng thử lại")
    return response.parsed_output
