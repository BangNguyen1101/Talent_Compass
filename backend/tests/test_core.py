"""Kiểm thử các luật chạy bằng code (không cần database, không cần AI)."""

from app.ai.pii import redact
from app.core import aggregation, ats, bias, guardrails, jd_checks, survey_stats
from app.core.text import fold


def test_fold_vietnamese():
    assert fold("Kỹ năng Đội nhóm") == "ky nang doi nhom"


def test_redact_pii():
    out = redact("Email: an@gmail.com\nSĐT: 0912 345 678\nNgày sinh: 01/01/2003\nKỹ năng: Python")
    assert "an@gmail.com" not in out and "0912" not in out and "01/01/2003" not in out
    assert "Python" in out


def test_bias_detects_age_gender_appearance():
    text = "Yêu cầu nam, tuổi từ 22 đến 28 tuổi.\nNgoại hình ưa nhìn.\nThành thạo Python."
    cats = {i["category"] for i in bias.detect(text)}
    assert {"Tuổi", "Giới tính", "Ngoại hình"} <= cats
    assert bias.has_high(bias.detect(text))
    assert bias.detect("Thành thạo Python và SQL, giao tiếp tốt.") == []


def test_ats_keywords_and_sections():
    jd = "Yêu cầu: Python, SQL, Docker. Biết CI/CD là lợi thế."
    cv = "Kinh nghiệm: thực tập Python và SQL.\nHọc vấn: Đại học X\nKỹ năng: Git\nEmail: [EMAIL]"
    r = ats.score(cv, jd, ["Python"])
    assert "Python" in r["matched_keywords"] and "SQL" in r["matched_keywords"]
    assert "Docker" in r["missing_keywords"]
    assert r["sections"]["Kinh nghiệm"] and r["sections"]["Học vấn"]
    assert 0 < r["score"] < 100


def test_guardrail_flags_invented_numbers_and_tools():
    cv = "Thực tập tại công ty A, viết API bằng Python cho 50 người dùng."
    ok = guardrails.check_rewrite("Xây dựng API Python phục vụ 50 người dùng", cv)
    bad = guardrails.check_rewrite("Xây dựng API bằng Kubernetes phục vụ 2000 người dùng, giảm 40%", cv)
    assert ok == []
    assert "2000" in bad and "Kubernetes" in bad and "40%" in bad
    fixed, flagged = guardrails.apply([{"example_rewrite": "Phục vụ 2000 người dùng"}], cv)
    assert flagged == 1 and "[số liệu thật của bạn]" in fixed[0]["example_rewrite"]


def test_aggregation_disagreement_and_untested():
    cards = [
        {"interviewer": "A", "scores": [{"competency": "Python", "score": 5}], "recommendation": "hire"},
        {"interviewer": "B", "scores": [{"competency": "Python", "score": 2}], "recommendation": "no_hire"},
    ]
    agg = aggregation.aggregate(["Python", "Giao tiếp"], {"python": 3, "giao tiếp": 3}, cards)
    assert agg["disagreements"] == ["Python"]
    assert agg["untested"] == ["Giao tiếp"]
    assert agg["recommendation_split"] is True


def test_survey_small_group_suppressed():
    qs = [{"id": "q1", "type": "likert", "text": "x", "dimension": "Quản lý"}]
    resp = [{"department": "A", "answers": {"q1": 4}, "sentiment": "positive", "topics": [], "risk_signal": False}] * 5
    resp += [{"department": "B", "answers": {"q1": 1}, "sentiment": "negative", "topics": [], "risk_signal": True}] * 2
    s = survey_stats.compute(qs, resp, 5)
    assert s["departments"]["A"]["suppressed"] is False
    assert s["departments"]["B"] == {"n": 2, "suppressed": True}


def test_jd_consistency_and_headcount():
    senior = {"level": "senior", "competencies": [{"name": "Python", "required_level": 2}]}
    junior = {"title": "Junior Dev", "level": "junior", "competencies": [{"name": "Python", "required_level": 3},
                                                                          {"name": "Git", "required_level": 2}]}
    w = jd_checks.consistency_warnings(senior, [junior])
    assert any(x["type"] == "level_inversion" for x in w)
    assert any(x["type"] == "missing_common" and x["competency"] == "Git" for x in w)
    assert jd_checks.headcount_warning(3, {"approved": 4, "filled": 2}, 0)["type"] == "over_headcount"
    assert jd_checks.headcount_warning(1, {"approved": 4, "filled": 2}, 0) is None
