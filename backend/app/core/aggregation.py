"""BO-17: tổng hợp scorecard của nhiều người phỏng vấn bằng code (minh bạch, tái lập được).
AI chỉ viết phần diễn giải dựa trên số liệu này, không tự tính điểm."""

from statistics import mean, pstdev

DISAGREEMENT_SPREAD = 2  # chênh lệch ≥2 điểm giữa các người chấm = bất đồng
REC_ORDER = ["strong_no_hire", "no_hire", "hire", "strong_hire"]


def untested_competencies(focus: list[str], scores: list[dict]) -> list[str]:
    scored = {s["competency"].lower() for s in scores if s.get("score")}
    return [c for c in focus if c.lower() not in scored]


def unasked_questions(questions: list[dict], question_notes: list[dict]) -> list[int]:
    asked = {n["index"] for n in question_notes if n.get("asked") or (n.get("notes") or "").strip()}
    return [i for i in range(len(questions)) if i not in asked]


def aggregate(focus: list[str], required: dict[str, int], scorecards: list[dict]) -> dict:
    """scorecards: [{interviewer, scores:[{competency, score, evidence}], recommendation}]"""
    per_comp = []
    for comp in focus:
        entries = [
            {"interviewer": sc["interviewer"], "score": s["score"], "evidence": s.get("evidence", "")}
            for sc in scorecards for s in sc["scores"]
            if s["competency"].lower() == comp.lower() and s.get("score")
        ]
        vals = [e["score"] for e in entries]
        req = required.get(comp.lower())
        per_comp.append({
            "competency": comp,
            "required_level": req,
            "n": len(vals),
            "mean": round(mean(vals), 2) if vals else None,
            "min": min(vals) if vals else None,
            "max": max(vals) if vals else None,
            "stdev": round(pstdev(vals), 2) if len(vals) > 1 else 0.0,
            "disagreement": bool(vals) and max(vals) - min(vals) >= DISAGREEMENT_SPREAD,
            "meets_requirement": (mean(vals) >= req) if vals and req else None,
            "entries": entries,
        })

    recs = [sc["recommendation"] for sc in scorecards if sc.get("recommendation") in REC_ORDER]
    rec_counts = {r: recs.count(r) for r in REC_ORDER}
    rec_split = len({("hire" in r and "no" not in r) for r in recs}) > 1
    scored = [c for c in per_comp if c["mean"] is not None]
    total_w = len(scored) or 1
    fit = sum(min(c["mean"] / (c["required_level"] or 3), 1.0) for c in scored) / total_w * 100

    return {
        "scorecards_submitted": len(scorecards),
        "competencies": per_comp,
        "untested": [c["competency"] for c in per_comp if c["n"] == 0],
        "disagreements": [c["competency"] for c in per_comp if c["disagreement"]],
        "recommendation_counts": rec_counts,
        "recommendation_split": rec_split,
        "fit_score": round(fit, 1) if scored else None,
    }
