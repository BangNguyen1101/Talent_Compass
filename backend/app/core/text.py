import re
import unicodedata


def fold(text: str) -> str:
    """Chữ thường, bỏ dấu tiếng Việt: 'Kỹ năng Đội nhóm' -> 'ky nang doi nhom'."""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.lower()


def contains_term(haystack_folded: str, term: str) -> bool:
    t = fold(term).strip()
    if not t:
        return False
    # Ranh giới từ "mềm" để khớp cả C++, Node.js, .NET
    pattern = r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])"
    return re.search(pattern, haystack_folded) is not None


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip(" -•*\t") for p in parts if p.strip(" -•*\t")]
