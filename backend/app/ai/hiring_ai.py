"""Tác vụ AI cho BO-17: cấu trúc ghi chú phỏng vấn và khuyến nghị tổng hợp."""

import json

from app.ai import prompts
from app.ai.llm import generate
from app.ai.schemas import HiringRecommendation, NoteScore, StructuredNotes
from app.core.text import contains_term, fold


def structure_notes(raw_notes: str, competencies: list[dict]) -> StructuredNotes:
    prompt = (f"<khung_nang_luc>\n{json.dumps(competencies, ensure_ascii=False)}\n</khung_nang_luc>\n\n"
              f"<ghi_chu>\n{raw_notes}\n</ghi_chu>")

    def mock() -> StructuredNotes:
        folded = fold(raw_notes)
        scores = []
        for c in competencies:
            hit = contains_term(folded, c["name"])
            scores.append(NoteScore(competency=c["name"], suggested_score=3 if hit else 0,
                                    evidence=f"Ghi chú có nhắc tới {c['name']}" if hit else ""))
        return StructuredNotes(scores=scores, summary="[MẪU] " + raw_notes[:200])

    return generate(feature="hiring.structure_notes", tier="fast", system=prompts.STRUCTURE_NOTES_SYSTEM,
                    prompt=prompt, output=StructuredNotes, mock=mock)


def recommend(jd_title: str, aggregate: dict, memory: list[dict]) -> HiringRecommendation:
    prompt = (f"Vị trí: {jd_title}\n<so_lieu_tong_hop>\n{json.dumps(aggregate, ensure_ascii=False)}\n</so_lieu_tong_hop>\n"
              f"<cac_vong_truoc>\n{json.dumps(memory, ensure_ascii=False)}\n</cac_vong_truoc>")

    def mock() -> HiringRecommendation:
        comps = [c for c in aggregate["competencies"] if c["mean"] is not None]
        weak = [c["competency"] for c in comps if c.get("meets_requirement") is False]
        strong = [c["competency"] for c in comps if c.get("meets_requirement")]
        if aggregate["untested"] or aggregate["disagreements"]:
            rec, conf = "more_info", "low"
        elif (aggregate.get("fit_score") or 0) >= 80:
            rec, conf = "hire", "medium"
        else:
            rec, conf = "no_hire", "medium"
        return HiringRecommendation(
            recommendation=rec, confidence=conf,
            rationale=f"[MẪU] Mức phù hợp {aggregate.get('fit_score')}/100 từ {aggregate['scorecards_submitted']} scorecard.",
            strengths=strong, concerns=weak + [f"Bất đồng: {d}" for d in aggregate["disagreements"]],
            probe_next_round=aggregate["untested"] + aggregate["disagreements"] + weak,
        )

    return generate(feature="hiring.recommend", tier="smart", system=prompts.HIRING_RECOMMEND_SYSTEM,
                    prompt=prompt, output=HiringRecommendation, mock=mock)
