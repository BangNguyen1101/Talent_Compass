"""Kiểm thử nhánh Gemini của lớp gọi AI bằng client giả lập (không gọi mạng, không cần key thật)."""

from types import SimpleNamespace

import pytest
from google.genai import errors
from pydantic import BaseModel

from app.ai import llm
from app.config import Settings


class Out(BaseModel):
    title: str
    score: int


def _response(*, parsed=None, text="", finish="STOP", block=None, prompt_tokens=100, out_tokens=20, thoughts=5):
    return SimpleNamespace(
        parsed=parsed, text=text,
        usage_metadata=SimpleNamespace(prompt_token_count=prompt_tokens, candidates_token_count=out_tokens,
                                       thoughts_token_count=thoughts),
        prompt_feedback=SimpleNamespace(block_reason=block) if block else None,
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name=finish))],
    )


@pytest.fixture
def gemini(monkeypatch):
    settings = Settings(llm_provider="gemini", gemini_api_key="fake-key-for-tests", llm_mock=False,
                        gemini_fast_model="gemini-2.5-flash", gemini_smart_model="gemini-2.5-pro")
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    recorded = []
    monkeypatch.setattr(llm.usage, "check_quota", lambda: None)
    monkeypatch.setattr(llm.usage, "record", lambda *a: recorded.append(a))
    calls = {}

    def install(result):
        def generate_content(**kwargs):
            calls.update(kwargs)
            if isinstance(result, Exception):
                raise result
            return result
        llm._clients["gemini"] = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    yield install, calls, recorded
    llm._clients.pop("gemini", None)


def _call(tier="fast"):
    return llm.generate(feature="test", tier=tier, system="sys", prompt="hello", output=Out,
                        mock=lambda: Out(title="mock", score=0))


def test_success_uses_schema_and_records_tokens(gemini):
    install, calls, recorded = gemini
    install(_response(parsed=Out(title="JD", score=4)))
    assert _call("smart") == Out(title="JD", score=4)
    assert calls["model"] == "gemini-2.5-pro"
    assert calls["config"].response_schema is Out and calls["config"].system_instruction == "sys"
    assert recorded == [("test", "gemini-2.5-pro", 100, 25)]  # token suy nghĩ tính vào đầu ra


def test_falls_back_to_text_json(gemini):
    install, _, _ = gemini
    install(_response(parsed=None, text='{"title": "x", "score": 3}'))
    assert _call().score == 3


def test_safety_block_is_refusal(gemini):
    install, _, _ = gemini
    install(_response(finish="SAFETY"))
    with pytest.raises(llm.LLMError, match="từ chối"):
        _call()


def test_truncated_output(gemini):
    install, _, _ = gemini
    install(_response(finish="MAX_TOKENS"))
    with pytest.raises(llm.LLMError, match="cắt ngang"):
        _call()


def test_invalid_json(gemini):
    install, _, _ = gemini
    install(_response(parsed=None, text='{"title": "thiếu score"}'))
    with pytest.raises(llm.LLMError, match="sai định dạng"):
        _call()


@pytest.mark.parametrize("code,msg", [(429, "hạn mức"), (403, "GEMINI_API_KEY"), (404, "model Gemini")])
def test_api_errors(gemini, code, msg):
    install, _, _ = gemini
    install(errors.APIError(code, {"error": {"message": "boom", "status": "X"}}))
    with pytest.raises(llm.LLMError, match=msg):
        _call()


def test_mock_mode_when_no_gemini_key(monkeypatch):
    monkeypatch.setattr(llm, "get_settings", lambda: Settings(llm_provider="gemini", gemini_api_key=None,
                                                               anthropic_api_key="có key claude cũng không dùng"))
    monkeypatch.setattr(llm.usage, "check_quota", lambda: None)
    monkeypatch.setattr(llm.usage, "record", lambda *a: None)
    assert _call().title == "mock"
    assert llm.model_name("fast") == "mock"


@pytest.mark.parametrize("provider,anth,gem,expected", [
    ("auto", None, "g-key", "gemini"),
    ("auto", "a-key", "g-key", "anthropic"),
    ("auto", None, None, "anthropic"),
    ("gemini", "a-key", "g-key", "gemini"),
    ("", None, "g-key", "gemini"),
])
def test_provider_auto_detect(provider, anth, gem, expected):
    assert Settings(llm_provider=provider, anthropic_api_key=anth, gemini_api_key=gem).provider == expected
