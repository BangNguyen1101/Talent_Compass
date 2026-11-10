"""BO-16: thống kê khảo sát bằng code + bảo vệ ẩn danh (ngưỡng nhóm tối thiểu)."""

from collections import Counter, defaultdict
from statistics import mean

NEGATIVE = "negative"


def likert_questions(questions: list[dict]) -> list[dict]:
    return [q for q in questions if q["type"] == "likert"]


def compute(questions: list[dict], responses: list[dict], min_group: int) -> dict:
    """responses: [{department, answers, sentiment, topics, risk_signal}]"""
    lq = likert_questions(questions)
    by_dept: dict[str, list[dict]] = defaultdict(list)
    for r in responses:
        by_dept[r["department"] or "Chưa rõ"].append(r)

    def summarize(group: list[dict]) -> dict:
        q_avgs = {}
        for q in lq:
            vals = [r["answers"].get(q["id"]) for r in group]
            vals = [v for v in vals if isinstance(v, (int, float))]
            q_avgs[q["id"]] = round(mean(vals), 2) if vals else None
        dims: dict[str, list[float]] = defaultdict(list)
        for q in lq:
            if q_avgs[q["id"]] is not None:
                dims[q.get("dimension") or "Chung"].append(q_avgs[q["id"]])
        sentiments = Counter(r.get("sentiment") or "unknown" for r in group)
        topics = Counter(t for r in group for t in (r.get("topics") or []))
        engagement = [v for v in q_avgs.values() if v is not None]
        return {
            "n": len(group),
            "engagement_index": round(mean(engagement) / 5 * 100, 1) if engagement else None,
            "question_avgs": q_avgs,
            "dimension_avgs": {d: round(mean(v), 2) for d, v in dims.items()},
            "sentiment": dict(sentiments),
            "negative_ratio": round(sentiments.get(NEGATIVE, 0) / len(group), 2) if group else 0,
            "top_topics": topics.most_common(6),
            "risk_ratio": round(sum(1 for r in group if r.get("risk_signal")) / len(group), 2) if group else 0,
        }

    departments = {}
    for dept, group in sorted(by_dept.items()):
        if len(group) < min_group:
            # Cảnh báo mẫu quá nhỏ: không hiển thị chi tiết để tránh lộ danh tính
            departments[dept] = {"n": len(group), "suppressed": True}
        else:
            departments[dept] = {**summarize(group), "suppressed": False}

    overall = summarize(responses) if len(responses) >= min_group else {"n": len(responses), "suppressed": True}
    return {
        "min_group_size": min_group,
        "total_responses": len(responses),
        "overall": {**overall, "suppressed": len(responses) < min_group},
        "departments": departments,
    }


def compare(current: dict, previous: dict | None) -> dict | None:
    """So sánh kỳ này với kỳ trước (chỉ khi cả hai đủ mẫu)."""
    if not previous:
        return None
    cur, prev = current.get("overall", {}), previous.get("overall", {})
    if cur.get("suppressed") or prev.get("suppressed"):
        return None
    dims = {}
    for d, v in (cur.get("dimension_avgs") or {}).items():
        pv = (prev.get("dimension_avgs") or {}).get(d)
        dims[d] = {"current": v, "previous": pv, "delta": round(v - pv, 2) if pv is not None else None}
    ce, pe = cur.get("engagement_index"), prev.get("engagement_index")
    return {
        "engagement_index": {"current": ce, "previous": pe,
                             "delta": round(ce - pe, 1) if ce is not None and pe is not None else None},
        "dimensions": dims,
    }
