"""Đọc chữ từ file CV (PDF, DOCX, TXT)."""

import io

from docx import Document
from pypdf import PdfReader

MAX_CHARS = 30_000


class UnsupportedFileError(ValueError):
    pass


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif name.endswith(".docx"):
        doc = Document(io.BytesIO(data))
        text = "\n".join(p.text for p in doc.paragraphs)
    elif name.endswith((".txt", ".md")):
        text = data.decode("utf-8", errors="ignore")
    else:
        raise UnsupportedFileError("Chỉ hỗ trợ file PDF, DOCX hoặc TXT")

    text = text.strip()
    if not text:
        raise UnsupportedFileError(
            "Không đọc được chữ trong file (có thể là ảnh scan). Hãy dùng file PDF có chữ."
        )
    if len(text) > MAX_CHARS:
        raise UnsupportedFileError("CV quá dài, vui lòng rút gọn dưới 30.000 ký tự")
    return text
