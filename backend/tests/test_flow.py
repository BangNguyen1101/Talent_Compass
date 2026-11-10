"""Kiểm thử luồng chính ở chế độ dữ liệu mẫu (không gọi Claude thật).
Cần Postgres đang chạy (docker compose up -d db) và đã `alembic upgrade head`."""

import os
import uuid

os.environ["LLM_MOCK"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app.ai.pii import redact  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def _register(role: str = "student", org: str | None = None) -> dict:
    body = {"email": f"{uuid.uuid4().hex[:8]}@test.vn", "full_name": "Test User",
            "password": "matkhau123", "role": role, "organization_name": org}
    r = client.post("/auth/register", json=body)
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_redact_pii():
    out = redact("Email: an@gmail.com\nSĐT: 0912 345 678\nNgày sinh: 01/01/2003\nKỹ năng: Python")
    assert "an@gmail.com" not in out and "0912" not in out and "01/01/2003" not in out
    assert "Python" in out


def test_full_student_flow():
    h = _register()

    draft = client.post("/jobs/generate", json={"title": "Backend Developer"}, headers=h)
    assert draft.status_code == 200, draft.text
    jd = client.post("/jobs", json=draft.json(), headers=h)
    assert jd.status_code == 201, jd.text
    jd_id = jd.json()["id"]
    assert len(jd.json()["competencies"]) >= 3
    assert jd.json()["status"] == "draft"  # sinh viên không được công khai JD

    cv_text = "Nguyen Van A\nEmail: a@gmail.com\nKỹ năng: Python, SQL\nThực tập: Công ty A"
    cv = client.post("/cvs", files={"file": ("cv.txt", cv_text.encode(), "text/plain")}, headers=h)
    assert cv.status_code == 201, cv.text
    cv_id = cv.json()["id"]

    a = client.post(f"/cvs/{cv_id}/assess", json={"jd_id": jd_id}, headers=h)
    assert a.status_code == 201, a.text
    assert 0 <= a.json()["overall_score"] <= 100

    s = client.post("/interviews", json={"jd_id": jd_id, "question_count": 2}, headers=h)
    assert s.status_code == 201, s.text
    sid = s.json()["id"]
    r = client.post(f"/interviews/{sid}/turns/0/answer", json={"answer": "Tôi đã..."}, headers=h)
    assert r.status_code == 200 and r.json()["turns"][0]["score"] is not None
    done = client.post(f"/interviews/{sid}/finish", headers=h)
    assert done.status_code == 200 and done.json()["status"] == "completed"


def test_private_data_is_isolated():
    owner, other = _register(), _register()
    cv = client.post("/cvs", files={"file": ("cv.txt", b"Python dev", "text/plain")}, headers=owner)
    assert client.get("/cvs", headers=other).json() == []
    r = client.post(f"/cvs/{cv.json()['id']}/assess",
                    json={"jd_id": str(uuid.uuid4())}, headers=other)
    assert r.status_code == 404


def test_hr_publishes_job_visible_to_students():
    hr = _register("hr", "Công ty Demo")
    draft = client.post("/jobs/generate", json={"title": "Data Analyst"}, headers=hr).json()
    draft["status"] = "published"
    jd = client.post("/jobs", json=draft, headers=hr).json()
    student = _register()
    ids = [j["id"] for j in client.get("/jobs", headers=student).json()]
    assert jd["id"] in ids
