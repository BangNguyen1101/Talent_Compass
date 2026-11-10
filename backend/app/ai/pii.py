"""Che thông tin cá nhân trong CV trước khi gửi cho AI chấm điểm.
Bản MVP dùng regex; có thể thay bằng Microsoft Presidio sau."""

import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"(?:\+?84|0)(?:[\s.-]?\d){9,10}\b"), "[SĐT]"),
    (re.compile(r"https?://(?:www\.)?(?:facebook|fb|zalo)\.\S+", re.I), "[MẠNG XÃ HỘI]"),
    (re.compile(r"\b\d{9}(?:\d{3})?\b"), "[SỐ GIẤY TỜ]"),  # CMND 9 số / CCCD 12 số
    (
        re.compile(
            r"(?im)^\s*(ngày sinh|năm sinh|date of birth|dob|giới tính|gender|"
            r"tình trạng hôn nhân|marital status|quê quán|địa chỉ|address)\s*[:\-].*$"
        ),
        "[THÔNG TIN CÁ NHÂN ĐÃ ẨN]",
    ),
]


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
