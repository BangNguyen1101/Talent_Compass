# TalentCompass

Nền tảng tuyển dụng theo khung năng lực, dùng AI. Ghép từ các đề tài AI20K:

| Module | Đề tài | Trạng thái |
|---|---|---|
| JD & khung năng lực (rubric 5 mức) | BO-15 | ✅ MVP |
| Chấm CV theo JD, gợi ý sửa CV | EDU-17 | ✅ MVP |
| Phỏng vấn thử, AI chấm từng câu | EDU-17 | ✅ MVP |
| Hỗ trợ phỏng vấn cho HR, phiếu chấm | BO-17 | 🔜 Giai đoạn 2 (đã có nền `mode=real`) |
| Khảo sát gắn kết nhân viên | BO-16 | 🔜 Giai đoạn 3 |

## Kiến trúc

```
Next.js (Vercel)  ──HTTPS/JWT──►  FastAPI (Render, Docker)  ──►  PostgreSQL + pgvector (Render)
                                         │
                                         └──►  Claude API (Haiku 5.5: việc nhanh · Sonnet 5.5: chấm điểm)
```

- **Khung năng lực là dữ liệu trung tâm**: JD, chấm CV, câu hỏi phỏng vấn đều bám theo nó.
- **AI chỉ đề xuất**: mọi kết quả kèm bằng chứng, được ghi vào `audit_logs`. Điểm tổng tính bằng code, không để AI tự cộng.
- **Bảo vệ dữ liệu**: CV được che email, SĐT, ngày sinh, địa chỉ... trước khi gửi AI. CV và buổi phỏng vấn chỉ chủ sở hữu xem được.
- **Chế độ dữ liệu mẫu**: khi không có `ANTHROPIC_API_KEY`, backend trả kết quả mẫu để chạy thử miễn phí.

## Chạy trên máy

Yêu cầu: Docker Desktop, Python 3.11+, Node 20+.

```bash
# 1. Database
docker compose up -d db

# 2. Backend (cổng 8000)
cd backend
python -m venv .venv
.venv/Scripts/activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # điền ANTHROPIC_API_KEY nếu muốn dùng AI thật
alembic upgrade head
uvicorn app.main:app --reload

# 3. Frontend (cổng 3000), mở terminal khác
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Tài liệu API tự sinh: http://localhost:8000/docs

Chạy test backend: `cd backend && pytest -q` (cần database đang chạy).

## Deploy

1. **Đưa code lên GitHub** (repo gồm cả `backend/` và `frontend/`).
2. **Render** (backend + database): Dashboard → **New → Blueprint** → chọn repo. Render đọc `render.yaml`, tự tạo Postgres và web service ở Singapore.
   Sau đó vào service `talentcompass-api` → **Environment**, điền `ANTHROPIC_API_KEY`.
3. **Vercel** (frontend): **Add New → Project** → chọn repo → Root Directory: `frontend` →
   thêm biến `NEXT_PUBLIC_API_URL` = link Render (vd. `https://talentcompass-api.onrender.com`) → Deploy.
4. Quay lại Render, đặt `FRONTEND_URL` = link Vercel (để backend cho phép CORS).

Từ đó, mỗi lần `git push` lên `main`: GitHub Actions chạy test, Vercel và Render tự deploy bản mới.
Migration database chạy tự động khi backend khởi động (`alembic upgrade head` trong Dockerfile).

**Lưu ý gói miễn phí**: web service Render ngủ sau 15 phút (lần mở đầu chờ ~30-60 giây);
Postgres free hết hạn sau khoảng 30 ngày. Hãy kiểm tra chính sách hiện tại của Render và nâng gói trước khi demo/chạy thật.

## Cấu trúc thư mục

```
backend/
  app/
    ai/          llm.py (gọi Claude), services.py (nghiệp vụ AI), prompts.py, schemas.py (định dạng đầu ra),
                 pii.py (che thông tin cá nhân), cv_parser.py (đọc PDF/DOCX)
    routers/     auth, jobs (BO-15), cvs (EDU-17), interviews (EDU-17/BO-17)
    models.py    bảng dữ liệu · security.py JWT + phân quyền · config.py biến môi trường
  migrations/    Alembic
  tests/
frontend/src/
  app/           trang: / (đăng nhập), /jobs, /jobs/new, /jobs/[id], /cv, /interviews, /interviews/[id]
  components/    NavBar, JobEditor, ui
  lib/           api.ts, auth.tsx, types.ts
render.yaml      cấu hình Render · .github/workflows/ci.yml  CI
```
