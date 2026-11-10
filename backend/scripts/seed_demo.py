"""Tạo dữ liệu demo qua API (chạy được với local hoặc server đã deploy).

    python scripts/seed_demo.py                         # mặc định http://localhost:8000
    python scripts/seed_demo.py https://xxx.onrender.com

Tạo 1 công ty + 1 trường với đủ các vai trò, JD đã duyệt, ứng viên, khảo sát có phản hồi.
Mật khẩu chung của mọi tài khoản demo: DEMO_PASSWORD bên dưới. Chỉ dùng cho môi trường thử nghiệm."""

import random
import sys
import uuid

import httpx

sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định không in được tiếng Việt
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
DEMO_PASSWORD = "demo-pass-2026"
SUFFIX = uuid.uuid4().hex[:4]
c = httpx.Client(base_url=BASE, timeout=120)


def reg(role: str, name: str, org: str | None = None, code: str | None = None, dept: str | None = None,
        tag: str = "") -> dict:
    email = f"{role}{tag}.{SUFFIX}@demo.vn"
    r = c.post("/auth/register", json={"email": email, "full_name": name, "password": DEMO_PASSWORD, "role": role,
                                       "organization_name": org, "join_code": code, "department": dept})
    r.raise_for_status()
    d = r.json()
    return {"email": email, "h": {"Authorization": f"Bearer {d['access_token']}"}, "id": d["user"]["id"]}


def ok(r: httpx.Response) -> dict:
    if r.status_code >= 400:
        raise SystemExit(f"{r.request.method} {r.request.url} -> {r.status_code}: {r.text}")
    return r.json() if r.content else {}


def main() -> None:
    # ---------------- Công ty
    hr = reg("hr", "Lan (HR)", org=f"Công ty Demo {SUFFIX}", dept="Nhân sự")
    code = ok(c.get("/org", headers=hr["h"]))["join_code"]
    ok(c.patch("/org", json={"brand_voice": "Thân thiện, xưng 'bạn'; giá trị cốt lõi: Tận tâm - Đổi mới - Hợp tác."},
               headers=hr["h"]))
    mgr = reg("manager", "Minh (Quản lý)", code=code, dept="Kỹ thuật")
    lead = reg("hiring_lead", "Hà (Trưởng nhóm TD)", code=code, dept="Nhân sự")
    iv1 = reg("interviewer", "Tuấn (Phỏng vấn)", code=code, dept="Kỹ thuật", tag="1")
    iv2 = reg("interviewer", "Vy (Phỏng vấn)", code=code, dept="Kỹ thuật", tag="2")
    ok(c.post("/org/headcount", json={"department": "Kỹ thuật", "job_family": "Backend", "approved": 3, "filled": 1},
              headers=hr["h"]))

    draft = ok(c.post("/jobs/generate", json={"title": "Backend Developer", "level": "junior", "department": "Kỹ thuật",
                                              "job_family": "Backend", "context": "Python, FastAPI, PostgreSQL, Docker"},
                      headers=hr["h"]))
    job = ok(c.post("/jobs", json={**draft, "department": "Kỹ thuật", "job_family": "Backend", "headcount": 1},
                    headers=hr["h"]))
    ok(c.post(f"/jobs/{job['id']}/submit", headers=hr["h"]))
    ok(c.post(f"/jobs/{job['id']}/review", json={"decision": "approved", "comment": "Đạt"}, headers=mgr["h"]))
    ok(c.post(f"/jobs/{job['id']}/question-bank", headers=hr["h"]))

    # JD thứ 2 còn chờ duyệt (để quản lý thử duyệt)
    d2 = ok(c.post("/jobs/generate", json={"title": "Data Analyst", "level": "junior", "department": "Kinh doanh",
                                           "job_family": "Data"}, headers=hr["h"]))
    j2 = ok(c.post("/jobs", json={**d2, "department": "Kinh doanh", "job_family": "Data"}, headers=hr["h"]))
    ok(c.post(f"/jobs/{j2['id']}/submit", headers=hr["h"]))

    cand = ok(c.post("/hiring/candidates", json={"full_name": "Nguyễn Văn An", "jd_id": job["id"],
                                                 "cv_text": "2 năm Python, FastAPI; thực tập tại công ty phần mềm."},
                     headers=lead["h"]))
    ok(c.post(f"/hiring/candidates/{cand['id']}/rounds",
              json={"name": "Vòng 1 - Chuyên môn", "interviewer_ids": [iv1["id"], iv2["id"]], "question_count": 4},
              headers=lead["h"]))

    # Khảo sát với nhân viên 2 phòng ban
    qs = ok(c.post("/surveys/draft", json={"goal": "Gắn kết quý"}, headers=hr["h"]))["questions"]
    sv = ok(c.post("/surveys", json={"title": "Khảo sát gắn kết Q3", "period_label": "Q3/2026", "questions": qs},
                   headers=hr["h"]))
    ok(c.post(f"/surveys/{sv['id']}/status/open", headers=hr["h"]))
    texts_neg = ["Áp lực quá tải, tăng ca nhiều, lương thấp", "Quản lý ít hỗ trợ, tôi đang tìm việc khác",
                 "Không có lộ trình thăng tiến rõ ràng"]
    texts_pos = ["Đồng nghiệp hỗ trợ tốt, tôi hài lòng", "Môi trường thân thiện, được học hỏi nhiều"]
    for i in range(8):
        dept = "Kinh doanh" if i < 6 else "Kế toán"
        e = reg("employee", f"Nhân viên {i + 1}", code=code, dept=dept, tag=str(i + 1))
        neg = i % 2 == 0
        answers = {q["id"]: (random.choice([1, 2, 3]) if neg else random.choice([3, 4, 5])) if q["type"] == "likert"
                   else random.choice(texts_neg if neg else texts_pos) for q in qs}
        ok(c.post(f"/surveys/{sv['id']}/respond", json={"answers": answers}, headers=e["h"]))

    # ---------------- Trường
    adv = reg("advisor", "Cô Thảo (Cố vấn)", org=f"Trường Demo {SUFFIX}")
    scode = ok(c.get("/org", headers=adv["h"]))["join_code"]
    sj = ok(c.post("/jobs/generate", json={"title": "Thực tập sinh Python", "level": "intern"}, headers=adv["h"]))
    sjob = ok(c.post("/jobs", json=sj, headers=adv["h"]))
    ok(c.post(f"/jobs/{sjob['id']}/submit", headers=adv["h"]))
    st = reg("student", "Bình (Sinh viên)", code=scode)

    print("\nĐã tạo dữ liệu demo. Mật khẩu chung:", DEMO_PASSWORD)
    for label, acc in [("HR", hr), ("Quản lý duyệt", mgr), ("Trưởng nhóm TD", lead), ("Người phỏng vấn 1", iv1),
                       ("Người phỏng vấn 2", iv2), ("Cố vấn", adv), ("Sinh viên", st)]:
        print(f"  {label:20s} {acc['email']}")
    print(f"  Mã công ty: {code} · Mã trường: {scode}")


if __name__ == "__main__":
    main()
