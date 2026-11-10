"""Guardrail chống bịa kinh nghiệm (EDU-17).

Sau khi AI gợi ý viết lại CV, kiểm tra bằng code: mọi con số và thuật ngữ riêng (công nghệ,
tên tổ chức) trong câu gợi ý phải xuất hiện trong CV gốc. Nếu không, đánh dấu "cần xác minh"
và thay số liệu bằng chỗ trống để sinh viên tự điền số thật."""

import re

from app.core.text import contains_term, fold

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?\s*%?")
_PROPER = re.compile(r"\b[A-Z][A-Za-z0-9+#.\-]{1,}\b")
_PLACEHOLDER = re.compile(r"\[[^\]]+\]")
COMMON_WORDS = {"CV", "STAR", "ATS", "Tôi", "Xây", "Phát", "Thiết", "Quản", "Hỗ", "Dẫn", "Tham", "Triển"}


def _numbers(text: str) -> set[str]:
    return {re.sub(r"\s+", "", n).replace(",", ".") for n in _NUMBER.findall(text)}


def check_rewrite(rewrite: str, cv_text: str) -> list[str]:
    """Trả về danh sách chi tiết không có trong CV gốc."""
    body = _PLACEHOLDER.sub("", rewrite)
    cv_numbers = _numbers(cv_text)
    cv_folded = fold(cv_text)
    unverified = [n for n in _numbers(body) if n.rstrip("%") not in {c.rstrip("%") for c in cv_numbers}]
    for term in _PROPER.findall(body):
        if term in COMMON_WORDS or len(term) < 3:
            continue
        if not contains_term(cv_folded, term):
            unverified.append(term)
    return sorted(set(unverified))


def neutralize_numbers(rewrite: str, unverified: list[str]) -> str:
    out = rewrite
    for n in unverified:
        if any(ch.isdigit() for ch in n):
            out = re.sub(re.escape(n), "[số liệu thật của bạn]", out)
    return out


def apply(suggestions: list[dict], cv_text: str) -> tuple[list[dict], int]:
    """Gắn cờ từng gợi ý; trả về (gợi ý đã xử lý, số gợi ý bị gắn cờ)."""
    flagged = 0
    out = []
    for s in suggestions:
        s = dict(s)
        unverified = check_rewrite(s.get("example_rewrite", ""), cv_text)
        s["unverified_details"] = unverified
        if unverified:
            flagged += 1
            s["example_rewrite"] = neutralize_numbers(s.get("example_rewrite", ""), unverified)
            s["guardrail_note"] = (
                "Câu gợi ý có chi tiết không tìm thấy trong CV của bạn: "
                + ", ".join(unverified)
                + ". Chỉ dùng nếu đúng sự thật."
            )
        out.append(s)
    return out, flagged
