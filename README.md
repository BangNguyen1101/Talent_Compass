# TalentCompass

Nền tảng nhân sự theo khung năng lực, dùng AI. Ghép 4 đề tài AI20K, dùng chung một khung năng lực:
**AI đề xuất, con người quyết định**; dữ liệu cá nhân được che và phân quyền theo vai trò.

## Vai trò

| Loại tổ chức | Vai trò | Dùng cho |
|---|---|---|
| Công ty | HR | Soạn JD (BO-15), tuyển dụng (BO-17), khảo sát (BO-16) |
| Công ty | Quản lý phê duyệt | Duyệt JD nhiều cấp, xem báo cáo khảo sát |
| Công ty | Trưởng nhóm tuyển dụng | Ứng viên, vòng phỏng vấn, quyết định của hội đồng |
| Công ty | Người phỏng vấn | Scorecard độc lập |
| Công ty | Nhân viên | Trả lời khảo sát ẩn danh |
| Trường | Cố vấn hướng nghiệp | KPI, theo dõi tiến bộ, nhận xét báo cáo sinh viên |
| Trường / tự do | Sinh viên | Chấm CV, phỏng vấn thử |

HR / cố vấn tạo tổ chức và nhận **mã mời**; thành viên khác đăng ký bằng mã đó.

## Đối chiếu yêu cầu đề tài

### BO-15 · JD & khung năng lực
- ✅ 2 vai trò HR / Quản lý phê duyệt; AI sinh JD + khung năng lực (rubric 5 mức); biên tập; duyệt & ban hành.
- ✅ **HITL nhiều cấp** (1–3 cấp cấu hình được; không tự duyệt; sửa JD đã gửi phải duyệt lại; từ chối phải có lý do).
- ✅ **Phát hiện & sửa ngôn ngữ thiên vị** (luật theo Bộ luật Lao động: tuổi, giới tính, ngoại hình, hôn nhân, quê quán...; AI viết lại trung tính; chặn gửi duyệt nếu còn lỗi mức cao).
- ✅ **Nhất quán với vị trí liên quan** (cùng nhóm vị trí: phát hiện mức yêu cầu đảo ngược giữa cấp, năng lực chung bị thiếu); **từ điển năng lực** dùng lại toàn tổ chức; JD đã ban hành làm tham chiếu khi soạn.
- ✅ **Memory phong cách thương hiệu** (cài đặt tổ chức, AI dùng mỗi lần soạn).
- ✅ **Cảnh báo mâu thuẫn định biên** (định biên được duyệt − đã có − đang tuyển).
- ✅ **Sinh câu hỏi phỏng vấn & tiêu chí chấm** theo JD (dùng lại ở BO-17).

### EDU-17 · Trợ lý nghề nghiệp
- ✅ 2 vai trò Sinh viên / Cố vấn; phân tích CV vs JD; phỏng vấn thử chấm theo rubric STAR; cố vấn xem báo cáo & nhận xét (HITL, sinh viên có quyền rút đồng ý chia sẻ).
- ✅ Metric: **CSAT**, **điểm trước/sau** (phỏng vấn, CV, ATS), **tỷ lệ sử dụng** so với mục tiêu ≥60% và CSAT ≥4/5.
- ✅ **Tối ưu CV theo ATS đa vị trí** (so sánh tối đa 10 JD, kỹ năng thiếu ở nhiều vị trí).
- ✅ **Phỏng vấn nhiều vòng** (sàng lọc / hành vi / chuyên môn / cuối), **câu hỏi đào sâu** khi trả lời mơ hồ, nhớ điểm yếu buổi trước.
- ✅ **Guardrail chống bịa kinh nghiệm**: prompt cấm + kiểm tra bằng code (số liệu/công nghệ/tổ chức không có trong CV bị gắn cờ và thay bằng chỗ trống).
- ✅ **Eval LLM-as-Judge** (5 tiêu chí) + dashboard cố vấn; cảnh báo "AI không đảm bảo trúng tuyển".

### BO-17 · Trợ lý phỏng vấn
- ✅ 2 vai trò Người phỏng vấn / Trưởng nhóm tuyển dụng; câu hỏi theo JD & cấp độ; scorecard theo khung năng lực; tổng hợp nhiều người phỏng vấn + khuyến nghị.
- ✅ **Chấm độc lập** (không thấy điểm người khác), **phát hiện bất đồng** (chênh ≥2 điểm), **phát hiện tiêu chí/câu hỏi chưa hỏi**.
- ✅ **Giọng nói → ghi chú** (đọc chính tả trên trình duyệt, miễn phí) + AI chuyển ghi chú thành bằng chứng theo năng lực.
- ✅ **Memory hồ sơ ứng viên qua các vòng** (điểm cần làm rõ chuyển sang vòng sau).
- ✅ **Hội đồng quyết định cuối** có lý do, ghi nhận có theo đề xuất AI hay không; **cảnh báo thiên vị** trong ghi chú (chặn nộp nếu mức cao).

### BO-16 · Khảo sát gắn kết
- ✅ 2 vai trò Nhân viên / HR; AI soạn khảo sát; thu phản hồi; phân tích cảm xúc + chủ đề; dashboard theo phòng ban.
- ✅ **Ẩn danh**: phản hồi không lưu người trả lời, che PII trong câu mở, **ẩn nhóm < 5 người** và cảnh báo mẫu nhỏ.
- ✅ **Tín hiệu rủi ro nghỉ việc** (chỉ ở cấp nhóm), **so sánh kỳ trước**, **memory chủ đề tồn đọng** qua các kỳ, gợi ý hành động từ kho thực hành tốt.
- ✅ **HITL**: HR duyệt từng insight và chọn hành động; báo cáo lãnh đạo chỉ gồm insight đã duyệt.

### Dùng chung
- ✅ **Kiểm soát chi phí**: ghi token & chi phí từng lượt AI theo chức năng, hạn mức lượt AI/người/ngày, model rẻ (Haiku) cho việc thường, model mạnh (Sonnet) chỉ cho chấm điểm, gán nhãn khảo sát theo lô.
- ✅ Nhật ký kiểm toán (`audit_logs`) cho các hành động AI và quyết định.

### Khác biệt so với tech stack gợi ý
- **Không dùng LangGraph**: các luồng agent viết trực tiếp bằng Python (dễ đọc, ít phụ thuộc). Có thể chuyển sang LangGraph nếu ban tổ chức yêu cầu.
- **RAG theo từ khóa** (từ điển năng lực, JD tham chiếu, kho thực hành tốt) thay vì vector DB, vì Anthropic không có API embedding; bảng `competencies` đã có cột `vector` (pgvector) để nâng cấp.
- **Topic modeling bằng LLM** (gán nhãn theo lô + memory chủ đề) thay vì embedding + clustering.
- **Whisper** thay bằng Web Speech API của trình duyệt (miễn phí, không gửi audio lên server).

## Kiến trúc

```
Next.js (Vercel) ──HTTPS/JWT──► FastAPI (Render, Docker) ──► PostgreSQL + pgvector (Render)
                                       │
                                       └──► Claude API (Haiku 5.5: việc nhanh · Sonnet 5.5: chấm điểm)
```

- Điểm số, ATS, tổng hợp scorecard, thống kê khảo sát, kiểm tra thiên vị/định biên/nhất quán: **tính bằng code** (`backend/app/core/`), giải thích và kiểm thử được. AI chỉ diễn giải và đề xuất.
- Không có `ANTHROPIC_API_KEY` → backend chạy **chế độ dữ liệu mẫu** (kết quả gắn nhãn [MẪU]).

## Chạy trên máy

Yêu cầu: Docker Desktop, Python 3.11+, Node 20+.

```bash
docker compose up -d db                 # 1. Database

cd backend                              # 2. Backend (cổng 8000)
python -m venv .venv
.venv/Scripts/activate                  # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                    # điền ANTHROPIC_API_KEY nếu muốn dùng AI thật
alembic upgrade head
uvicorn app.main:app --reload

cd frontend                             # 3. Frontend (cổng 3000), terminal khác
cp .env.example .env.local
npm install
npm run dev
```

**Dữ liệu demo** (đủ mọi vai trò, JD đã duyệt, ứng viên, khảo sát có phản hồi):

```bash
cd backend
python scripts/seed_demo.py                                   # local
python scripts/seed_demo.py https://talentcompass-api.onrender.com   # server đã deploy
```

Script in ra email các tài khoản demo; mật khẩu nằm trong `scripts/seed_demo.py`.

Test backend: `cd backend && pytest -q` (cần database đang chạy).

## Deploy

1. **Render** (backend + database): Dashboard → **New → Blueprint** → chọn repo; Render đọc `render.yaml`. Điền `ANTHROPIC_API_KEY` trong Environment của `talentcompass-api` (để trống = chế độ mẫu).
2. **Vercel** (frontend): Root Directory `frontend`, biến `NEXT_PUBLIC_API_URL` = link Render.
3. Mỗi lần `git push` lên `main`: GitHub Actions chạy test; Vercel và Render tự deploy. Migration chạy tự động khi backend khởi động.

**Gói miễn phí**: backend Render ngủ sau 15 phút; Postgres free hết hạn sau khoảng 30 ngày. Nâng gói trước khi demo/chạy thật.

## Cấu trúc thư mục

```
backend/app/
  core/       Luật chạy bằng code: bias, ats, guardrails, aggregation, survey_stats, jd_checks, knowledge, usage
  ai/         llm.py (gọi Claude + ghi chi phí), services.py (JD, CV, phỏng vấn thử), hiring_ai.py,
              survey_ai.py, judge.py, prompts.py, schemas.py, pii.py, cv_parser.py
  routers/    auth, orgs, jobs (BO-15), cvs + interviews + advisor (EDU-17), hiring (BO-17),
              surveys (BO-16), quality (CSAT, eval, chi phí)
backend/migrations/  Alembic · backend/tests/ · backend/scripts/seed_demo.py
frontend/src/app/    /, /settings, /jobs, /approvals, /cv, /interviews, /progress, /advisor,
                     /hiring, /hiring/candidates/[id], /hiring/rounds/[id], /surveys, /surveys/[id], .../respond, .../report
```
