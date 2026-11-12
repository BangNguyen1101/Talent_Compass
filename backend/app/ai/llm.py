"""Lớp gọi AI. Mọi tác vụ AI đều đi qua đây để thống nhất model, xử lý lỗi và ghi log chi phí.

Hỗ trợ 2 nhà cung cấp (LLM_PROVIDER=auto|anthropic|gemini; auto = có key nào dùng key đó):
- anthropic (Claude): fast = Haiku, smart = Sonnet; có server-side fallback khi model từ chối.
- gemini (Google):    fast / smart = model cấu hình bằng GEMINI_FAST_MODEL / GEMINI_SMART_MODEL.

"fast"  -> tác vụ thường: trích xuất CV, soạn JD, sinh câu hỏi, gán nhãn khảo sát.
"smart" -> tác vụ cần lập luận: chấm CV, chấm câu trả lời, khuyến nghị tuyển dụng, insight.
Cả hai đều dùng chế độ trả JSON theo schema Pydantic, nên phần nghiệp vụ không phụ thuộc nhà cung cấp.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.core import usage

log = logging.getLogger("talentcompass.llm")

T = TypeVar("T", bound=BaseModel)
Tier = Literal["fast", "smart"]


class LLMError(RuntimeError):
    """Lỗi khi gọi AI, thông điệp thân thiện để trả về cho người dùng."""


@dataclass
class _Result:
    parsed: BaseModel | None
    model: str
    input_tokens: int
    output_tokens: int
    stop: str  # ok | refusal | max_tokens | invalid


_clients: dict[str, object] = {}


def model_name(tier: Tier) -> str:
    s = get_settings()
    if s.use_mock_llm:
        return "mock"
    if s.provider == "gemini":
        return s.gemini_smart_model if tier == "smart" else s.gemini_fast_model
    return s.llm_smart_model if tier == "smart" else s.llm_fast_model


def generate(
    *,
    feature: str,
    tier: Tier,
    system: str,
    prompt: str,
    output: type[T],
    mock: Callable[[], T],
    max_tokens: int = 16000,
) -> T:
    """Gọi AI và trả về đối tượng Pydantic đã được kiểm tra định dạng.
    feature: tên tác vụ, dùng để thống kê chi phí theo chức năng."""
    settings = get_settings()
    try:
        usage.check_quota()
    except usage.QuotaExceeded as e:
        raise LLMError(str(e)) from e

    if settings.use_mock_llm:
        usage.record(feature, "mock", 0, 0)
        return mock()

    model = model_name(tier)
    call = _call_gemini if settings.provider == "gemini" else _call_anthropic
    r = call(tier=tier, model=model, system=system, prompt=prompt, output=output, max_tokens=max_tokens)

    log.info("llm call provider=%s feature=%s model=%s in=%s out=%s stop=%s",
             settings.provider, feature, r.model, r.input_tokens, r.output_tokens, r.stop)
    usage.record(feature, r.model, r.input_tokens, r.output_tokens)
    if r.stop == "refusal":
        raise LLMError("AI từ chối xử lý nội dung này. Hãy kiểm tra lại dữ liệu đầu vào.")
    if r.stop == "max_tokens" or r.parsed is None:
        raise LLMError("Kết quả AI bị cắt ngang hoặc sai định dạng, vui lòng thử lại")
    return r.parsed  # type: ignore[return-value]


# ---------------------------------------------------------------- Claude (Anthropic)

def _call_anthropic(*, tier: Tier, model: str, system: str, prompt: str, output: type[BaseModel],
                    max_tokens: int) -> _Result:
    import anthropic

    client = _clients.get("anthropic")
    if client is None:
        client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key, max_retries=2)
        _clients["anthropic"] = client
    try:
        if tier == "smart":
            response = client.beta.messages.parse(
                model=model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": prompt}],
                output_format=output, output_config={"effort": "medium"},
                betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            )
        else:
            response = client.messages.parse(
                model=model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": prompt}],
                output_format=output, output_config={"effort": "low"},
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

    stop = {"refusal": "refusal", "max_tokens": "max_tokens"}.get(response.stop_reason or "", "ok")
    return _Result(response.parsed_output, response.model, response.usage.input_tokens,
                   response.usage.output_tokens, stop)


# ---------------------------------------------------------------- Gemini (Google)

GEMINI_BLOCKED = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"}


def _call_gemini(*, tier: Tier, model: str, system: str, prompt: str, output: type[BaseModel],
                 max_tokens: int) -> _Result:
    from google import genai
    from google.genai import errors, types

    client = _clients.get("gemini")
    if client is None:
        client = genai.Client(api_key=get_settings().gemini_api_key)
        _clients["gemini"] = client
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=output,
                max_output_tokens=max_tokens,
            ),
        )
    except errors.APIError as e:
        log.warning("Gemini API error %s: %s", e.code, e.message)
        if e.code == 429:
            raise LLMError("Đã hết hạn mức gọi Gemini (quota/phút hoặc/ngày), vui lòng thử lại sau") from e
        if e.code in (401, 403) or (e.code == 400 and "API key" in (e.message or "")):
            raise LLMError("Sai hoặc thiếu GEMINI_API_KEY trên server") from e
        if e.code == 404:
            raise LLMError(f"Không tìm thấy model Gemini '{model}'. Kiểm tra GEMINI_FAST_MODEL / GEMINI_SMART_MODEL") from e
        raise LLMError("Dịch vụ AI gặp lỗi, vui lòng thử lại") from e
    except Exception as e:  # lỗi mạng, timeout
        log.exception("Gemini call failed")
        raise LLMError("Không kết nối được tới dịch vụ AI") from e

    meta = response.usage_metadata
    in_tok = (meta.prompt_token_count or 0) if meta else 0
    # Token "suy nghĩ" của Gemini được tính tiền như token đầu ra
    out_tok = ((meta.candidates_token_count or 0) + (meta.thoughts_token_count or 0)) if meta else 0

    blocked = response.prompt_feedback and response.prompt_feedback.block_reason
    finish = response.candidates[0].finish_reason if response.candidates else None
    finish_name = getattr(finish, "name", str(finish or ""))
    if blocked or finish_name in GEMINI_BLOCKED:
        return _Result(None, model, in_tok, out_tok, "refusal")
    if finish_name == "MAX_TOKENS":
        return _Result(None, model, in_tok, out_tok, "max_tokens")

    parsed = response.parsed if isinstance(response.parsed, output) else None
    if parsed is None and response.text:
        try:
            parsed = output.model_validate_json(response.text)
        except ValidationError:
            log.warning("Gemini trả JSON không khớp schema %s", output.__name__)
    return _Result(parsed, model, in_tok, out_tok, "ok" if parsed else "invalid")
