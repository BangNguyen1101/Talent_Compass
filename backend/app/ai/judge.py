"""LLM-as-Judge: đo chất lượng phản hồi AI (EDU-17 nâng cao)."""

import json

from app.ai import prompts
from app.ai.llm import generate
from app.ai.schemas import JudgeResult
from app.core import guardrails


def judge(input_text: str, ai_output: dict) -> JudgeResult:
    prompt = (f"<dau_vao>\n{input_text}\n</dau_vao>\n\n"
              f"<phan_hoi_ai>\n{json.dumps(ai_output, ensure_ascii=False)}\n</phan_hoi_ai>")

    def mock() -> JudgeResult:
        # Ước lượng bằng luật: grounding dựa trên guardrail, specificity theo độ dài/gợi ý
        suggestions = ai_output.get("suggestions", [])
        flagged = sum(1 for s in suggestions if guardrails.check_rewrite(s.get("example_rewrite", ""), input_text))
        issues = [f"{flagged} gợi ý có chi tiết không có trong CV"] if flagged else []
        return JudgeResult(specificity=4 if len(suggestions) >= 2 else 3,
                           grounding=5 if not flagged else 2, actionability=4, fairness=5, tone=4,
                           issues=issues)

    return generate(feature="eval.judge", tier="smart", system=prompts.JUDGE_SYSTEM, prompt=prompt,
                    output=JudgeResult, mock=mock)
