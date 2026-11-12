"""Dữ liệu mẫu khi chưa có API key (chế độ demo).

Không phải AI: chỉ ghép khuôn dựa trên thông tin HR nhập (công nghệ, cấp độ) để giao diện có nội dung
hợp lý khi chạy thử. Mọi nội dung đều gắn nhãn [MẪU]."""

from app.core.ats import extract_keywords

LEVEL_REQ = {"intern": 1, "fresher": 2, "junior": 2, "middle": 3, "senior": 4, "lead": 4}
LEVEL_SCOPE = {
    "intern": "học và hỗ trợ dưới sự hướng dẫn của mentor",
    "fresher": "thực hiện các đầu việc nhỏ, rõ ràng với hướng dẫn",
    "junior": "tự hoàn thành các đầu việc được giao, phối hợp trong nhóm",
    "middle": "chịu trách nhiệm một mảng tính năng từ thiết kế đến vận hành",
    "senior": "thiết kế giải pháp, ra quyết định kỹ thuật và hướng dẫn thành viên khác",
    "lead": "định hướng kỹ thuật, phân công và phát triển đội ngũ",
}


IGNORE = {"ai", "anthropic_api_key", "jd", "cv", "hr"}


def techs_from(text: str, limit: int = 6) -> list[str]:
    # Bỏ dòng ghi chú [MẪU] (bắt đầu bằng ">") để không lấy nhầm từ khóa trong chính lời nhắc
    body = "\n".join(line for line in (text or "").splitlines() if not line.lstrip().startswith((">", "#")))
    return [k for k in extract_keywords(body, [], limit=limit + 4) if k.lower() not in IGNORE][:limit]


def jd_markdown(title: str, level: str, context: str, brand_voice: str) -> str:
    techs = techs_from(context)
    stack = ", ".join(techs) if techs else "các công cụ của nhóm"
    scope = LEVEL_SCOPE.get(level, LEVEL_SCOPE["junior"])
    lines = [
        "> [MẪU] Nội dung này do chế độ dữ liệu mẫu ghép tự động, không phải do AI viết. "
        "Thêm GEMINI_API_KEY hoặc ANTHROPIC_API_KEY để AI soạn JD thật.",
        "",
        f"## Về vai trò {title}",
        f"Bạn sẽ {scope}, làm việc với {stack}." + (f" ({brand_voice[:120]})" if brand_voice else ""),
        "",
        "## Bạn sẽ làm gì",
    ]
    if techs:
        lines += [f"- Xây dựng và cải tiến tính năng sử dụng {t}" for t in techs[:3]]
    lines += ["- Viết tài liệu, review và kiểm thử phần việc của mình", "- Phối hợp với sản phẩm, thiết kế, kiểm thử"]
    lines += ["", "## Bạn cần có"]
    lines += [f"- Kinh nghiệm thực tế với {t}" for t in techs[:4]] or ["- [HR bổ sung yêu cầu chuyên môn]"]
    lines += ["- Giao tiếp rõ ràng, chủ động cập nhật tiến độ", "", "## Quyền lợi", "- [HR bổ sung]"]
    return "\n".join(lines)


def competencies(title: str, level: str, context: str, dictionary: list[str]) -> list[tuple[str, str]]:
    techs = techs_from(context, 3)
    tech = [(f"Thành thạo {t}", "technical") for t in techs] or [(f"Chuyên môn {title}", "technical")]
    out, seen = [], set()
    for name, cat in tech + [("Giải quyết vấn đề", "soft"), ("Giao tiếp", "soft"), ("Làm việc nhóm", "soft")]:
        if name.lower() not in seen:
            seen.add(name.lower())
            out.append((name, cat))
    return out


def question_items(jd_text: str, comps: list[dict], count: int, round_type: str = "technical") -> list[dict]:
    techs = techs_from(jd_text) or ["công cụ chính của vị trí"]
    ordered = sorted(comps, key=lambda c: -c["weight"]) or [{"name": "Chuyên môn", "weight": 1}]
    templates = {
        "technical": ("technical", "[MẪU] Với {tech}, bạn sẽ thiết kế giải pháp thế nào cho một tính năng có lượng người "
                                   "dùng tăng gấp 10 lần? Nêu các đánh đổi bạn cân nhắc."),
        "situational": ("situational", "[MẪU] Một tuần trước hạn chót, bạn phát hiện phần việc liên quan {tech} có lỗi "
                                       "ảnh hưởng khách hàng. Bạn xử lý và trao đổi với các bên thế nào?"),
        "behavioral": ("behavioral", "[MẪU] Kể về dự án gần nhất bạn dùng {tech}: vai trò của bạn, quyết định khó nhất "
                                     "và kết quả đo được."),
        "motivation": ("motivation", "[MẪU] Điều gì ở vị trí này và công việc với {tech} khiến bạn quan tâm?"),
    }
    order = {"screening": ["motivation", "behavioral"], "behavioral": ["behavioral", "situational"],
             "technical": ["technical", "situational"], "final": ["situational", "behavioral"]}.get(
        round_type, ["technical", "behavioral", "situational"])
    out = []
    for i in range(count):
        c = ordered[i % len(ordered)]
        qtype, tpl = templates[order[i % len(order)]]
        tech = techs[i % len(techs)]
        out.append({
            "question": tpl.format(tech=tech), "competency": c["name"], "type": qtype,
            "what_good_looks_like": f"Nêu bối cảnh cụ thể, lựa chọn có lý do, kết quả đo được; thể hiện {c['name']}.",
            "follow_ups": ["[MẪU] Nếu làm lại, bạn sẽ làm khác điều gì?", "[MẪU] Bạn đo kết quả bằng chỉ số nào?"],
            "scoring_guide": {"weak": "Trả lời lý thuyết, không có ví dụ hay đánh đổi.",
                              "solid": "Có ví dụ thật và các bước hợp lý, còn thiếu số liệu.",
                              "strong": "Ví dụ cụ thể, nêu rõ đánh đổi, có kết quả đo được và bài học."},
            "good_signals": ["Ví dụ cụ thể, vai trò rõ", "Nêu được đánh đổi và kết quả"],
            "red_flags": ["Chỉ nói lý thuyết", "Không rõ đóng góp của bản thân"],
        })
    return out
