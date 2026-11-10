"""Phát hiện ngôn ngữ thiên vị/phân biệt đối xử (BO-15 JD, BO-17 ghi chú phỏng vấn).

Dùng luật cố định (chạy nhanh, không tốn tiền, giải thích được). AI chỉ dùng để viết lại câu.
Căn cứ: Bộ luật Lao động 2019 (Điều 8) cấm phân biệt đối xử vì giới tính, tuổi, tôn giáo,
tình trạng hôn nhân, khuyết tật..."""

import re
from dataclasses import asdict, dataclass

from app.core.text import fold, sentences


@dataclass
class BiasRule:
    category: str
    pattern: str  # regex trên văn bản đã bỏ dấu
    severity: str  # high | medium
    suggestion: str


RULES: list[BiasRule] = [
    BiasRule("Tuổi", r"\b(duoi|tren|tu|khong qua|toi da|toi thieu)\s*\d{2}\s*(den\s*\d{2}\s*)?tuoi\b",
             "high", "Bỏ giới hạn tuổi; mô tả kinh nghiệm/năng lực cần có thay vì độ tuổi."),
    BiasRule("Tuổi", r"\b(do tuoi|tuoi doi|tre trung|tre tuoi|nang dong tuoi tre|under \d{2}|young)\b",
             "high", "Thay bằng yêu cầu về năng lực, ví dụ 'chủ động, học hỏi nhanh'."),
    BiasRule("Giới tính", r"\b(uu tien|chi tuyen|tuyen|yeu cau)\s+(nam|nu)\b|\b(nam gioi|nu gioi|gioi tinh)\b|\b(male|female)\s+only\b",
             "high", "Không yêu cầu giới tính; dùng 'ứng viên' chung cho mọi người."),
    BiasRule("Ngoại hình", r"\b(ngoai hinh|ua nhin|xinh xan|dep trai|chieu cao|can nang|than hinh|good looking)\b",
             "high", "Bỏ yêu cầu ngoại hình trừ khi là yêu cầu nghề nghiệp chính đáng và có căn cứ."),
    BiasRule("Hôn nhân/gia đình", r"\b(da lap gia dinh|chua lap gia dinh|chua ket hon|da ket hon|doc than|chua co con|da co con|married|single)\b",
             "high", "Không hỏi/yêu cầu tình trạng hôn nhân hay con cái."),
    BiasRule("Quê quán/vùng miền", r"\b(ho khau|que quan|nguoi mien (bac|trung|nam)|nguoi (ha noi|sai gon)|dan toc)\b",
             "high", "Không yêu cầu quê quán/hộ khẩu/dân tộc."),
    BiasRule("Tôn giáo", r"\b(ton giao|theo dao|religion)\b",
             "high", "Không đề cập tôn giáo."),
    BiasRule("Sức khỏe", r"\b(suc khoe tot|khong benh tat|khong khuyet tat|the luc tot)\b",
             "medium", "Chỉ nêu yêu cầu thể chất cụ thể nếu công việc thực sự cần (vd. 'nâng vật 20kg')."),
    BiasRule("Ngôn ngữ loại trừ", r"\b(anh em ky thuat|cac anh|chi em van phong|rockstar|ninja)\b",
             "medium", "Dùng từ trung tính như 'đội ngũ', 'ứng viên'."),
    BiasRule("Trường học", r"\b(chi nhan|bat buoc) (sinh vien|ung vien) (truong|dai hoc)\b|\btop \d+ truong\b",
             "medium", "Đánh giá theo năng lực, tránh giới hạn theo tên trường."),
]

_COMPILED = [(r, re.compile(r.pattern)) for r in RULES]


@dataclass
class BiasIssue:
    category: str
    severity: str
    excerpt: str
    suggestion: str


def detect(text: str) -> list[dict]:
    issues: list[BiasIssue] = []
    seen: set[tuple[str, str]] = set()
    for sent in sentences(text):
        folded = fold(sent)
        for rule, rx in _COMPILED:
            if rx.search(folded):
                key = (rule.category, sent)
                if key not in seen:
                    seen.add(key)
                    issues.append(BiasIssue(rule.category, rule.severity, sent[:200], rule.suggestion))
    return [asdict(i) for i in issues]


def has_high(issues: list[dict]) -> bool:
    return any(i["severity"] == "high" for i in issues)
