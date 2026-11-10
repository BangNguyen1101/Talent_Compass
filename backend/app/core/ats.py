"""EDU-17: chấm mức tương thích ATS (hệ thống lọc CV tự động) bằng luật, không dùng AI.

ATS thường lọc theo từ khóa có trong JD và cấu trúc CV dễ đọc. Kết quả giải thích được:
từ khóa nào có, từ khóa nào thiếu, mục nào thiếu."""

import re

from app.core.text import contains_term, fold

STOPWORDS = {
    "va", "hoac", "cac", "nhung", "cua", "cho", "voi", "trong", "tren", "the", "and", "or", "with",
    "for", "to", "of", "in", "a", "an", "kinh", "nghiem", "nam", "co", "biet", "ky", "nang",
    "tot", "kha", "uu", "tien", "yeu", "cau", "mo", "ta", "tong", "quan", "trach", "nhiem",
}

# Mục CV mà ATS/nhà tuyển dụng mong đợi
SECTIONS = {
    "Kinh nghiệm": ["kinh nghiem", "experience", "lam viec", "thuc tap", "internship"],
    "Học vấn": ["hoc van", "education", "dai hoc", "university", "truong"],
    "Kỹ năng": ["ky nang", "skills", "cong nghe", "technologies"],
    "Dự án": ["du an", "projects", "project"],
    "Liên hệ": ["email", "@", "dien thoai", "phone", "sdt", "[email]", "[sdt]"],
}

_TECH_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-/]{1,}")
_SPLIT = re.compile(r"[\s,;:()\[\]\"'“”]+")


def extract_keywords(jd_content: str, competency_names: list[str], limit: int = 30) -> list[str]:
    """Từ khóa = tên năng lực + thuật ngữ chuyên môn (chữ Latin viết hoa/có ký hiệu) trong JD."""
    keywords: list[str] = []

    def add(k: str) -> None:
        k = k.strip(" .,;:()")
        if len(k) >= 2 and fold(k) not in STOPWORDS and fold(k) not in {fold(x) for x in keywords}:
            keywords.append(k)

    for name in competency_names:
        add(name)
    for raw in _SPLIT.split(jd_content):
        tok = raw.rstrip(".")
        # Thuật ngữ kỹ thuật: toàn ký tự Latin không dấu, có chữ hoa (Python, SQL, AWS)
        # hoặc ký hiệu (C++, Node.js, CI/CD). Chữ tiếng Việt có dấu tự bị loại.
        if _TECH_TOKEN.fullmatch(tok) and (any(c.isupper() for c in tok) or any(c in tok for c in "+#./")):
            add(tok)
    return keywords[:limit]


def score(cv_text: str, jd_content: str, competency_names: list[str]) -> dict:
    folded = fold(cv_text)
    keywords = extract_keywords(jd_content, competency_names)
    matched = [k for k in keywords if contains_term(folded, k)]
    missing = [k for k in keywords if k not in matched]
    sections = {name: any(s in folded for s in signs) for name, signs in SECTIONS.items()}
    words = len(cv_text.split())

    tips: list[str] = []
    for name, ok in sections.items():
        if not ok:
            tips.append(f"Thêm mục '{name}' với tiêu đề rõ ràng để ATS nhận diện.")
    if words < 150:
        tips.append("CV khá ngắn (<150 từ); mô tả thêm nhiệm vụ và kết quả thực tế của bạn.")
    if words > 1200:
        tips.append("CV dài (>1200 từ); rút gọn còn 1-2 trang, giữ phần liên quan vị trí.")
    if missing:
        tips.append("Chỉ thêm từ khóa còn thiếu NẾU bạn thực sự có kinh nghiệm đó; không nhồi từ khóa.")

    kw_ratio = len(matched) / len(keywords) if keywords else 1.0
    section_ratio = sum(sections.values()) / len(sections)
    return {
        "score": round((0.75 * kw_ratio + 0.25 * section_ratio) * 100, 1),
        "matched_keywords": matched,
        "missing_keywords": missing,
        "sections": sections,
        "word_count": words,
        "tips": tips,
    }
