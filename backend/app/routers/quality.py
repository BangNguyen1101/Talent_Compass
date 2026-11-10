"""Chất lượng & chi phí dùng chung: CSAT, LLM-as-Judge, thống kê chi phí AI."""

from datetime import UTC, datetime, timedelta
from statistics import mean

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import String, cast, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.ai import judge
from app.ai.llm import LLMError, model_name
from app.config import get_settings
from app.db import get_db
from app.models import CV, CVAssessment, Feedback, LLMUsage, QualityEval, Role, User
from app.schemas import FeedbackIn
from app.security import get_current_user, require_org, require_roles

router = APIRouter(tags=["quality"])


@router.post("/feedback", status_code=201)
def submit_feedback(body: FeedbackIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = insert(Feedback).values(user_id=user.id, org_id=user.org_id, **body.model_dump())
    stmt = stmt.on_conflict_do_update(index_elements=["user_id", "target_type", "target_id"],
                                      set_={"rating": body.rating, "comment": body.comment})
    db.execute(stmt)
    db.commit()
    return {"ok": True}


@router.get("/feedback/mine")
def my_feedback(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Feedback).where(Feedback.user_id == user.id)).all()
    return {f"{f.target_type}:{f.target_id}": f.rating for f in rows}


@router.get("/feedback/summary")
def feedback_summary(user: User = Depends(require_roles(Role.advisor, Role.hr, Role.hiring_lead)),
                     db: Session = Depends(get_db)):
    org_id = require_org(user)
    rows = db.execute(select(Feedback.target_type, func.avg(Feedback.rating), func.count())
                      .where(Feedback.org_id == org_id).group_by(Feedback.target_type)).all()
    return [{"target_type": t, "csat": round(float(a), 2), "responses": n} for t, a, n in rows]


# ---------------------------------------------------------------- LLM-as-Judge

@router.post("/evals/run")
def run_evals(limit: int = 10, user: User = Depends(require_roles(Role.advisor)), db: Session = Depends(get_db)):
    """Chấm chất lượng các lượt chấm CV gần nhất chưa được đánh giá (của sinh viên trong trường)."""
    org_id = require_org(user)
    done = select(QualityEval.target_id).where(QualityEval.target_type == "cv_assessment")
    rows = db.execute(select(CVAssessment, CV.redacted_text).join(CV, CV.id == CVAssessment.cv_id)
                      .join(User, User.id == CV.user_id)
                      .where(User.org_id == org_id, cast(CVAssessment.id, String).not_in(done))
                      .order_by(CVAssessment.created_at.desc()).limit(min(limit, 20))).all()
    evaluated = 0
    for a, cv_text in rows:
        try:
            r = judge.judge(cv_text, a.result)
        except LLMError as e:
            raise HTTPException(502, str(e)) from e
        scores = r.model_dump(exclude={"issues"})
        db.add(QualityEval(org_id=org_id, target_type="cv_assessment", target_id=str(a.id), scores=scores,
                           overall=round(mean(scores.values()), 2), issues=r.issues, judge_model=model_name("smart")))
        evaluated += 1
    db.commit()
    return {"evaluated": evaluated}


@router.get("/evals/summary")
def evals_summary(user: User = Depends(require_roles(Role.advisor)), db: Session = Depends(get_db)):
    org_id = require_org(user)
    evals = db.scalars(select(QualityEval).where(QualityEval.org_id == org_id)
                       .order_by(QualityEval.created_at.desc())).all()
    if not evals:
        return {"count": 0, "overall": None, "dimensions": {}, "recent_issues": []}
    dims = {k: round(mean(e.scores[k] for e in evals), 2) for k in evals[0].scores}
    issues = [i for e in evals[:10] for i in e.issues][:10]
    return {"count": len(evals), "overall": round(mean(e.overall for e in evals), 2), "dimensions": dims,
            "recent_issues": issues}


# ---------------------------------------------------------------- Chi phí AI

@router.get("/usage")
def usage_summary(days: int = 30, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    since = datetime.now(UTC) - timedelta(days=days)
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    mine_today = db.scalar(select(func.count(LLMUsage.id)).where(LLMUsage.user_id == user.id,
                                                                 LLMUsage.created_at >= today)) or 0
    out = {"my_calls_today": mine_today, "daily_quota": get_settings().daily_ai_quota_per_user}
    if user.role in (Role.hr, Role.advisor, Role.manager, Role.hiring_lead, Role.admin) and user.org_id:
        rows = db.execute(select(LLMUsage.feature, LLMUsage.model, func.count(), func.sum(LLMUsage.input_tokens),
                                 func.sum(LLMUsage.output_tokens), func.sum(LLMUsage.cost_usd))
                          .where(LLMUsage.org_id == user.org_id, LLMUsage.created_at >= since)
                          .group_by(LLMUsage.feature, LLMUsage.model)).all()
        out["org"] = {
            "days": days,
            "total_cost_usd": round(sum(r[5] or 0 for r in rows), 4),
            "total_calls": sum(r[2] for r in rows),
            "by_feature": [{"feature": f, "model": m, "calls": n, "input_tokens": int(i or 0),
                            "output_tokens": int(o or 0), "cost_usd": round(c or 0, 4)}
                           for f, m, n, i, o, c in sorted(rows, key=lambda r: -(r[5] or 0))],
        }
    return out
