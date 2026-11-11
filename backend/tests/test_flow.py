"""Kiểm thử luồng nghiệp vụ qua API ở chế độ dữ liệu mẫu (không gọi Claude thật).
Cần Postgres đang chạy (docker compose up -d db) và đã `alembic upgrade head`."""

import os
import uuid

os.environ["LLM_MOCK"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def register(role="student", org=None, code=None, dept=None) -> tuple[dict, dict]:
    body = {"email": f"{uuid.uuid4().hex[:10]}@test.vn", "full_name": f"{role} {uuid.uuid4().hex[:4]}",
            "password": "matkhau123", "role": role, "organization_name": org, "join_code": code,
            "department": dept}
    r = client.post("/auth/register", json=body)
    assert r.status_code == 201, r.text
    data = r.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]


def join_code(h) -> str:
    return client.get("/org", headers=h).json()["join_code"]


def make_job(h, title="Backend Developer", **extra) -> dict:
    draft = client.post("/jobs/generate", json={"title": title, **extra}, headers=h)
    assert draft.status_code == 200, draft.text
    body = {**draft.json(), **{k: v for k, v in extra.items() if k in ("department", "job_family")}}
    r = client.post("/jobs", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def published_job(company: str, title: str, level: str = "junior", **extra) -> dict:
    """HR công ty (không yêu cầu duyệt) tạo và ban hành một JD lên sàn."""
    hr, _ = register("hr", org=company)
    client.patch("/org", json={"jd_approval_levels": 0}, headers=hr)
    job = make_job(hr, title, level=level, **extra)
    r = client.post(f"/jobs/{job['id']}/submit", headers=hr)
    assert r.json()["status"] == "published", r.text
    return {**r.json(), "_hr": hr}


# ================================================================ Sàn việc làm & ứng tuyển

def test_only_hr_creates_jobs():
    hr, _ = register("hr", org="Cty Quyền")
    code = join_code(hr)
    body = {**client.post("/jobs/generate", json={"title": "Tester"}, headers=hr).json()}
    for role, extra in [("student", {}), ("advisor", {"org": "Trường Q"}), ("manager", {"code": code}),
                        ("hiring_lead", {"code": code})]:
        h, _ = register(role, **extra)
        assert client.post("/jobs", json=body, headers=h).status_code == 403, role
        assert client.post("/jobs/generate", json={"title": "x"}, headers=h).status_code == 403, role


def test_submit_requires_manager_when_approval_enabled():
    hr, _ = register("hr", org="Cty Không Quản Lý")
    job = make_job(hr, "Kế toán")
    r = client.post(f"/jobs/{job['id']}/submit", headers=hr)
    assert r.status_code == 422 and "quản lý" in r.json()["detail"]


def test_job_board_search_filter_match_and_apply():
    tag = uuid.uuid4().hex[:6]
    a = published_job(f"Alpha {tag}", f"Python Backend {tag}", "junior")
    b = published_job(f"Beta {tag}", f"Kế toán tổng hợp {tag}", "senior")

    # Mọi vai trò đều xem được sàn
    adv, _ = register("advisor", org="Trường B")
    st, _ = register("student")
    for h in (adv, st, b["_hr"]):
        ids = [i["id"] for i in client.get(f"/jobs/board?q={tag}", headers=h).json()["items"]]
        assert a["id"] in ids and b["id"] in ids

    # Lọc theo công ty, cấp độ, từ khóa
    only_a = client.get(f"/jobs/board?q={tag}&company={a['org_id']}", headers=st).json()["items"]
    assert [i["id"] for i in only_a] == [a["id"]]
    seniors = client.get(f"/jobs/board?q={tag}&level=senior", headers=st).json()["items"]
    assert [i["id"] for i in seniors] == [b["id"]]
    facets = client.get("/jobs/board/facets", headers=st).json()
    assert any(c["id"] == a["org_id"] for c in facets["companies"]) and "senior" in facets["levels"]

    # Ứng viên không thấy thông tin nội bộ của JD (câu hỏi phỏng vấn, lịch sử duyệt)
    client.post(f"/jobs/{a['id']}/question-bank", headers=a["_hr"])
    public = client.get(f"/jobs/{a['id']}", headers=st).json()
    assert public["question_bank"] == [] and public["approvals"] == [] and public["internal"] is False
    assert client.get(f"/jobs/{a['id']}", headers=a["_hr"]).json()["question_bank"]

    # JD nháp của công ty không xuất hiện trên sàn
    draft = make_job(a["_hr"], f"Nháp {tag}")
    assert draft["id"] not in [i["id"] for i in client.get(f"/jobs/board?q={tag}", headers=st).json()["items"]]

    # Khớp CV
    cv = client.post("/cvs", files={"file": ("cv.txt", f"Kinh nghiệm Python Backend {tag}".encode(), "text/plain")},
                     headers=st).json()
    ranked = client.get(f"/jobs/board?q={tag}&cv_id={cv['id']}&sort=match", headers=st).json()["items"]
    assert ranked[0]["match"] is not None and ranked[0]["match"]["score"] >= ranked[-1]["match"]["score"]

    # Ứng tuyển -> vào quy trình tuyển dụng của công ty A
    assert client.post(f"/jobs/{a['id']}/apply", json={"cv_id": cv["id"]}, headers=adv).status_code == 403
    r = client.post(f"/jobs/{a['id']}/apply", json={"cv_id": cv["id"], "cover_note": "Em rất quan tâm"}, headers=st)
    assert r.status_code == 201
    assert client.post(f"/jobs/{a['id']}/apply", json={"cv_id": cv["id"]}, headers=st).status_code == 409
    flags = {i["id"]: i["applied"] for i in client.get(f"/jobs/board?q={tag}", headers=st).json()["items"]}
    assert flags[a["id"]] is True and flags[b["id"]] is False

    cands = client.get("/hiring/candidates", headers=a["_hr"]).json()
    mine = [c for c in cands if c["source"] == "applied"]
    assert len(mine) == 1 and mine[0]["stage"] == "applied"
    assert client.get("/hiring/candidates", headers=b["_hr"]).json() == []  # công ty khác không thấy

    # Sàng lọc hồ sơ: từ chối trước phỏng vấn được, tuyển thì không
    cid = mine[0]["id"]
    assert client.post(f"/hiring/candidates/{cid}/decision", json={"decision": "hire", "rationale": "Chưa phỏng vấn"},
                       headers=a["_hr"]).status_code == 422
    assert client.post(f"/hiring/candidates/{cid}/decision",
                       json={"decision": "reject", "rationale": "Chưa đủ kinh nghiệm Python"},
                       headers=a["_hr"]).status_code == 201
    apps = client.get("/me/applications", headers=st).json()
    assert apps[0]["status"] == "Chưa phù hợp lần này" and apps[0]["can_withdraw"] is False

    # Rút đơn khi chưa được xử lý
    client.post(f"/jobs/{b['id']}/apply", json={"cv_id": cv["id"]}, headers=st)
    app_b = next(x for x in client.get("/me/applications", headers=st).json() if x["jd_id"] == b["id"])
    assert client.post(f"/me/applications/{app_b['id']}/withdraw", headers=st).json()["ok"]
    assert client.get("/hiring/candidates", headers=b["_hr"]).json() == []


# ================================================================ BO-15

def test_bo15_approval_bias_headcount():
    hr, _ = register("hr", org="Cty BO15")
    code = join_code(hr)
    mgr1, _ = register("manager", code=code)
    mgr2, _ = register("manager", code=code)
    register("employee", code=code)  # nhân viên tham gia được

    job = make_job(hr, department="Kỹ thuật", job_family="Backend")
    jid = job["id"]

    # JD có ngôn ngữ thiên vị -> không gửi duyệt được
    biased = {**job, "content": job["content"] + "\nƯu tiên nam, dưới 30 tuổi."}
    r = client.put(f"/jobs/{jid}", json=biased, headers=hr)
    assert r.json()["bias_issues"]
    assert client.post(f"/jobs/{jid}/submit", headers=hr).status_code == 422
    fixed = client.post("/jobs/neutralize", json={"content": biased["content"]}, headers=hr).json()
    assert fixed["remaining"] == []
    client.put(f"/jobs/{jid}", json={**job, "content": fixed["content"]}, headers=hr)

    # Định biên: duyệt 1, xin 2 -> cảnh báo
    client.post("/org/headcount", json={"department": "Kỹ thuật", "job_family": "Backend", "approved": 1}, headers=hr)
    check = client.post("/jobs/check", json={**job, "headcount": 2}, headers=hr).json()
    assert check["headcount"]["type"] == "over_headcount"

    # HITL 2 cấp
    client.patch("/org", json={"jd_approval_levels": 2}, headers=hr)
    assert client.post(f"/jobs/{jid}/submit", headers=hr).json()["status"] == "pending_approval"
    assert client.post(f"/jobs/{jid}/review", json={"decision": "approved"}, headers=hr).status_code == 403
    assert len(client.get("/jobs/pending-approval", headers=mgr1).json()) >= 1
    r1 = client.post(f"/jobs/{jid}/review", json={"decision": "approved"}, headers=mgr1)
    assert r1.json()["status"] == "pending_approval"
    assert client.post(f"/jobs/{jid}/review", json={"decision": "approved"}, headers=mgr1).status_code == 409
    r2 = client.post(f"/jobs/{jid}/review", json={"decision": "approved", "comment": "OK"}, headers=mgr2)
    assert r2.json()["status"] == "published"

    # Sửa JD đã ban hành -> quay về nháp, phải duyệt lại
    assert client.put(f"/jobs/{jid}", json=job, headers=hr).json()["status"] == "draft"

    # Từ chối phải có lý do
    client.post(f"/jobs/{jid}/submit", headers=hr)
    assert client.post(f"/jobs/{jid}/review", json={"decision": "rejected"}, headers=mgr1).status_code == 422
    assert client.post(f"/jobs/{jid}/review", json={"decision": "rejected", "comment": "Sửa yêu cầu"},
                       headers=mgr1).json()["status"] == "rejected"

    bank = client.post(f"/jobs/{jid}/question-bank", headers=hr).json()["question_bank"]
    assert bank and "good_signals" in bank[0]


def test_bo15_brand_voice_and_dictionary_reuse():
    hr, _ = register("hr", org="Cty Brand")
    client.patch("/org", json={"brand_voice": "Thân thiện, ngắn gọn"}, headers=hr)
    make_job(hr, "Data Analyst")
    draft = client.post("/jobs/generate", json={"title": "Data Engineer"}, headers=hr).json()
    assert "Thân thiện" in draft["content"]


# ================================================================ EDU-17

def test_edu17_student_advisor_flow():
    adv, _ = register("advisor", org="Trường X")
    code = join_code(adv)
    st, st_user = register("student", code=code)

    job = published_job("Cty EDU17", "Python Developer")
    assert job["id"] in [j["id"] for j in client.get("/jobs", headers=st).json()]

    cv_text = ("Kinh nghiệm: Thực tập Python tại Công ty A, viết API.\nHọc vấn: Đại học X\n"
               "Kỹ năng: Python, SQL\nEmail: a@gmail.com")
    cv = client.post("/cvs", files={"file": ("cv.txt", cv_text.encode(), "text/plain")}, headers=st).json()
    a = client.post(f"/cvs/{cv['id']}/assess", json={"jd_id": job["id"]}, headers=st)
    assert a.status_code == 201, a.text
    a = a.json()
    assert a["ats_score"] > 0 and "matched_keywords" in a["ats"]
    assert a["result"]["guardrail_flagged"] >= 1  # mock bịa số liệu -> bị gắn cờ
    assert "không đảm bảo" in a["result"]["disclaimer"]

    cmp = client.post(f"/cvs/{cv['id']}/ats-compare", json={"jd_ids": [job["id"]]}, headers=st).json()
    assert cmp["results"][0]["jd_id"] == job["id"]

    # Phỏng vấn thử: câu trả lời thiếu kết quả -> có câu hỏi đào sâu
    s = client.post("/interviews", json={"jd_id": job["id"], "question_count": 2, "round_type": "technical"},
                    headers=st).json()
    r = client.post(f"/interviews/{s['id']}/turns/0/answer", json={"answer": "Tôi làm API"}, headers=st).json()
    assert len(r["turns"]) == 3 and r["turns"][1]["parent"] == 0
    client.post(f"/interviews/{s['id']}/turns/1/answer", json={"answer": "Kết quả giảm 20% thời gian"}, headers=st)
    done = client.post(f"/interviews/{s['id']}/finish", headers=st).json()
    assert done["average_score"] is not None

    s2 = client.post("/interviews", json={"jd_id": job["id"], "question_count": 1}, headers=st).json()
    client.post(f"/interviews/{s2['id']}/turns/0/answer",
                json={"answer": "Tôi dẫn dắt nhóm 3 người hoàn thành dự án, kết quả tăng 15% hiệu suất " * 3},
                headers=st)
    client.post(f"/interviews/{s2['id']}/finish", headers=st)

    assert client.post("/feedback", json={"target_type": "interview", "target_id": s["id"], "rating": 5},
                       headers=st).status_code == 201
    client.post("/feedback", json={"target_type": "interview", "target_id": s["id"], "rating": 4}, headers=st)

    prog = client.get("/me/progress", headers=st).json()
    assert prog["interview"]["count"] == 2 and prog["interview"]["delta"] is not None

    dash = client.get("/advisor/dashboard", headers=adv).json()
    assert dash["students_total"] == 1 and dash["usage_rate"] == 1.0 and dash["usage_met"]
    assert dash["csat"] == 4.0 and dash["csat_responses"] == 1  # chấm lại = cập nhật, không nhân đôi

    detail = client.get(f"/advisor/students/{st_user['id']}", headers=adv).json()
    assert len(detail["assessments"]) == 1 and len(detail["interviews"]) == 2
    client.post(f"/advisor/students/{st_user['id']}/notes", json={"content": "Bổ sung số liệu thật"}, headers=adv)
    assert client.get("/me/progress", headers=st).json()["advisor_notes"][0]["content"] == "Bổ sung số liệu thật"

    assert client.post("/evals/run", headers=adv).json()["evaluated"] == 1
    assert client.get("/evals/summary", headers=adv).json()["count"] == 1

    # Sinh viên rút lại đồng ý chia sẻ -> cố vấn không xem được
    client.patch("/auth/me", json={"share_with_advisor": False}, headers=st)
    assert client.get(f"/advisor/students/{st_user['id']}", headers=adv).status_code == 403


def test_edu17_privacy_between_students():
    owner, _ = register()
    other, _ = register()
    cv = client.post("/cvs", files={"file": ("cv.txt", b"Python dev", "text/plain")}, headers=owner)
    assert client.get("/cvs", headers=other).json() == []
    assert client.post(f"/cvs/{cv.json()['id']}/assess", json={"jd_id": str(uuid.uuid4())},
                       headers=other).status_code == 404


def test_roles_need_org():
    r = client.post("/auth/register", json={"email": f"{uuid.uuid4().hex[:8]}@test.vn", "full_name": "x",
                                            "password": "matkhau123", "role": "manager"})
    assert r.status_code == 422
    adv, _ = register("advisor", org="Trường Y")
    r = client.post("/auth/register", json={"email": f"{uuid.uuid4().hex[:8]}@test.vn", "full_name": "x",
                                            "password": "matkhau123", "role": "hr", "join_code": join_code(adv)})
    assert r.status_code == 422  # HR không vào được tổ chức loại trường


# ================================================================ BO-17

def test_bo17_hiring_flow():
    hr, _ = register("hr", org="Cty BO17")
    code = join_code(hr)
    lead, _ = register("hiring_lead", code=code)
    iv1, u1 = register("interviewer", code=code)
    iv2, u2 = register("interviewer", code=code)
    iv3, _ = register("interviewer", code=code)

    job = make_job(hr, "QA Engineer")
    comps = [c["name"] for c in job["competencies"]]
    cand = client.post("/hiring/candidates", json={"full_name": "Ứng viên A", "jd_id": job["id"],
                                                   "cv_text": "Email: a@b.com, kinh nghiệm test"}, headers=lead).json()
    assert client.post("/hiring/candidates", json={"full_name": "x", "jd_id": job["id"]}, headers=iv1).status_code == 403

    rnd = client.post(f"/hiring/candidates/{cand['id']}/rounds",
                      json={"name": "Vòng 1", "focus_competencies": comps[:2], "interviewer_ids": [u1["id"], u2["id"]],
                            "question_count": 3}, headers=lead).json()
    rid = rnd["id"]
    assert len(rnd["questions"]) == 3

    # Người không được phân công không thấy ứng viên
    assert client.get(f"/hiring/candidates/{cand['id']}", headers=iv3).status_code == 404
    assert len(client.get("/hiring/candidates", headers=iv1).json()) == 1

    # Ghi chú thiên vị -> không nộp được
    biased = {"scores": [{"competency": comps[0], "score": 4}], "raw_notes": "Ứng viên ngoại hình ưa nhìn",
              "recommendation": "hire", "submit": True}
    assert client.put(f"/hiring/rounds/{rid}/scorecard", json=biased, headers=iv1).status_code == 422

    draft = client.put(f"/hiring/rounds/{rid}/scorecard",
                       json={"scores": [{"competency": comps[0], "score": 5}], "raw_notes": "Trả lời tốt"},
                       headers=iv1).json()
    assert comps[1] in draft["warnings"]["untested_competencies"]
    assert draft["warnings"]["unasked_questions"] == [0, 1, 2]

    sn = client.post(f"/hiring/rounds/{rid}/structure-notes", json={"raw_notes": f"Ứng viên mạnh về {comps[0]}"},
                     headers=iv1).json()
    assert any(s["suggested_score"] > 0 for s in sn["scores"])

    client.put(f"/hiring/rounds/{rid}/scorecard", json={
        "scores": [{"competency": comps[0], "score": 5, "evidence": "Giải thích rõ"}],
        "question_notes": [{"index": 0, "asked": True, "notes": "ok"}], "recommendation": "hire", "submit": True},
        headers=iv1)
    # Người phỏng vấn 2 không thấy điểm của người 1 (chấm độc lập)
    view2 = client.get(f"/hiring/rounds/{rid}", headers=iv2).json()
    assert "scorecards" not in view2 and view2["my_scorecard"] is None
    client.put(f"/hiring/rounds/{rid}/scorecard", json={
        "scores": [{"competency": comps[0], "score": 2, "evidence": "Còn lúng túng"}],
        "recommendation": "no_hire", "submit": True}, headers=iv2)
    assert client.put(f"/hiring/rounds/{rid}/scorecard", json={"scores": [], "submit": False},
                      headers=iv2).status_code == 409

    assert client.post(f"/hiring/candidates/{cand['id']}/decision",
                       json={"decision": "hire", "rationale": "Chưa đóng vòng nên phải lỗi"}, headers=lead).status_code == 422
    closed = client.post(f"/hiring/rounds/{rid}/close", headers=lead).json()
    assert comps[0] in closed["aggregate"]["disagreements"]
    assert comps[1] in closed["aggregate"]["untested"]
    assert closed["recommendation"]["recommendation"] == "more_info"

    detail = client.get(f"/hiring/candidates/{cand['id']}", headers=lead).json()
    assert detail["profile_memory"][0]["probe_next_round"]
    assert "[EMAIL]" in detail["cv_text"]

    d = client.post(f"/hiring/candidates/{cand['id']}/decision",
                    json={"decision": "hold", "rationale": "Cần thêm vòng để làm rõ năng lực", "committee": ["A", "B"]},
                    headers=lead).json()
    assert d["followed_ai"] is True


# ================================================================ BO-16

def _survey(hr) -> str:
    qs = client.post("/surveys/draft", json={"goal": "gắn kết quý"}, headers=hr).json()["questions"]
    s = client.post("/surveys", json={"title": f"Khảo sát {uuid.uuid4().hex[:4]}", "period_label": "Q",
                                      "questions": qs}, headers=hr).json()
    assert client.post(f"/surveys/{s['id']}/status/open", headers=hr).json()["status"] == "open"
    return s["id"]


def _answer(h, sid, likert: int, text: str):
    s = client.get(f"/surveys/{sid}", headers=h).json()
    answers = {q["id"]: (likert if q["type"] == "likert" else text) for q in s["questions"]}
    return client.post(f"/surveys/{sid}/respond", json={"answers": answers}, headers=h)


def test_bo16_survey_flow():
    hr, _ = register("hr", org="Cty BO16")
    code = join_code(hr)
    mgr, _ = register("manager", code=code)
    sid = _survey(hr)

    emps_a = [register("employee", code=code, dept="Kinh doanh")[0] for _ in range(6)]
    emps_b = [register("employee", code=code, dept="Kế toán")[0] for _ in range(2)]
    for i, h in enumerate(emps_a):
        text = "Áp lực quá tải, lương thấp, tôi đang tìm việc khác" if i < 3 else "Quản lý hỗ trợ tốt, tôi hài lòng"
        assert _answer(h, sid, 2 if i < 3 else 4, text).status_code == 201
    for h in emps_b:
        _answer(h, sid, 3, "Bình thường, email tôi là x@y.com")
    assert _answer(emps_a[0], sid, 5, "lần 2").status_code == 409

    # Nhân viên không xem được dashboard
    assert client.get(f"/surveys/{sid}/dashboard", headers=emps_a[0]).status_code == 403

    dash = client.post(f"/surveys/{sid}/analyze", headers=hr).json()
    stats = dash["analysis"]["stats"]
    assert stats["departments"]["Kế toán"]["suppressed"] is True
    assert stats["departments"]["Kinh doanh"]["risk_ratio"] > 0
    assert dash["participation"]["responses"] == 8
    assert any("Kế toán" in w for w in dash["analysis"]["warnings"])
    insights = dash["insights"]
    assert insights and all(i["status"] == "pending" for i in insights)
    assert all("Kế toán" not in i["departments"] for i in insights)

    # Báo cáo lãnh đạo chỉ có insight đã duyệt
    assert client.get(f"/surveys/{sid}/report", headers=mgr).json()["insights"] == []
    iid = insights[0]["id"]
    assert client.patch(f"/surveys/{sid}/insights/{iid}", json={"status": "approved"}, headers=hr).status_code == 422
    client.patch(f"/surveys/{sid}/insights/{iid}",
                 json={"status": "approved", "selected_actions": insights[0]["suggested_actions"][:1]}, headers=hr)
    assert len(client.get(f"/surveys/{sid}/report", headers=mgr).json()["insights"]) == 1

    # Kỳ 2: chủ đề lặp lại -> tồn đọng, có so sánh kỳ trước
    sid2 = _survey(hr)
    for h in emps_a:
        _answer(h, sid2, 2, "Vẫn quá tải và lương thấp")
    dash2 = client.post(f"/surveys/{sid2}/analyze", headers=hr).json()
    assert dash2["analysis"]["persistent_topics"]
    assert dash2["analysis"]["comparison"] is not None


def test_usage_tracking():
    hr, _ = register("hr", org="Cty Usage")
    client.post("/jobs/generate", json={"title": "Tester"}, headers=hr)
    u = client.get("/usage", headers=hr).json()
    assert u["my_calls_today"] >= 1 and u["org"]["total_calls"] >= 1
