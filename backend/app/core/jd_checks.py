"""BO-15: kiểm tra nhất quán giữa các vị trí liên quan và mâu thuẫn định biên (bằng code)."""

from app.core.text import fold

LEVEL_RANK = {"intern": 0, "fresher": 1, "junior": 2, "middle": 3, "senior": 4, "lead": 5, "manager": 6}


def level_rank(level: str) -> int:
    return LEVEL_RANK.get(fold(level).strip(), 2)


def consistency_warnings(jd: dict, related: list[dict]) -> list[dict]:
    """jd/related: {title, level, competencies:[{name, required_level}]} cùng job_family.

    Quy tắc: vị trí cấp cao hơn không được yêu cầu một năng lực THẤP hơn vị trí cấp dưới,
    và ngược lại. Cũng gợi ý năng lực mà các vị trí cùng nhóm đều có nhưng JD này thiếu."""
    warnings: list[dict] = []
    my_rank = level_rank(jd["level"])
    mine = {fold(c["name"]): c for c in jd["competencies"]}
    for other in related:
        o_rank = level_rank(other["level"])
        for oc in other["competencies"]:
            key = fold(oc["name"])
            if key not in mine:
                continue
            my_req, o_req = mine[key]["required_level"], oc["required_level"]
            if o_rank < my_rank and o_req > my_req:
                warnings.append({"type": "level_inversion", "competency": mine[key]["name"],
                                 "message": f"'{other['title']}' ({other['level']}) yêu cầu mức {o_req} "
                                            f"nhưng vị trí cấp cao hơn này chỉ yêu cầu mức {my_req}."})
            elif o_rank > my_rank and o_req < my_req:
                warnings.append({"type": "level_inversion", "competency": mine[key]["name"],
                                 "message": f"'{other['title']}' ({other['level']}) cấp cao hơn nhưng chỉ yêu cầu "
                                            f"mức {o_req}, thấp hơn mức {my_req} của vị trí này."})
    if related:
        common: dict[str, tuple[str, int]] = {}
        for other in related:
            for oc in other["competencies"]:
                k = fold(oc["name"])
                name, cnt = common.get(k, (oc["name"], 0))
                common[k] = (name, cnt + 1)
        for k, (name, cnt) in common.items():
            if cnt == len(related) and k not in mine:
                warnings.append({"type": "missing_common", "competency": name,
                                 "message": f"Mọi vị trí cùng nhóm đều có năng lực '{name}' nhưng JD này chưa có."})
    return warnings


def headcount_warning(requested: int, plan: dict | None, committed: int) -> dict | None:
    """plan: {approved, filled}; committed: số đang tuyển ở các JD khác cùng nhóm (đã duyệt/chờ duyệt)."""
    if plan is None:
        return {"type": "no_plan", "message": "Chưa có định biên được duyệt cho phòng ban/nhóm vị trí này."}
    available = plan["approved"] - plan["filled"] - committed
    if requested > available:
        return {"type": "over_headcount",
                "message": f"Xin tuyển {requested} người nhưng định biên còn trống {max(available, 0)} "
                           f"(duyệt {plan['approved']}, đã có {plan['filled']}, đang tuyển {committed})."}
    return None
