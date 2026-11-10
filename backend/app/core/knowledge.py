"""Kho tri thức nhỏ dùng để "grounding" cho AI (RAG theo từ khóa).

Chưa dùng vector search vì cần thêm nhà cung cấp embedding; truy hồi theo từ khóa đủ cho
kho tri thức vài chục mục. Có thể nâng cấp lên pgvector khi kho lớn hơn."""

from app.core.text import fold

ATS_GUIDELINES = """Tiêu chí ATS & nhà tuyển dụng:
- Tiêu đề mục chuẩn: Kinh nghiệm, Học vấn, Kỹ năng, Dự án; tránh bảng/ảnh/cột phức tạp.
- Dùng đúng thuật ngữ trong JD (nếu ứng viên thực sự có kỹ năng đó).
- Mỗi gạch đầu dòng: động từ hành động + việc đã làm + kết quả (có số liệu nếu có thật).
- 1-2 trang, ưu tiên nội dung liên quan vị trí ứng tuyển, sắp xếp mới nhất trước."""

STAR_GUIDE = """Rubric STAR cho câu trả lời phỏng vấn hành vi:
- S (Situation): bối cảnh cụ thể, ngắn gọn.
- T (Task): nhiệm vụ/vai trò của chính ứng viên.
- A (Action): hành động cụ thể ứng viên làm (dùng "tôi", không chỉ "chúng tôi").
- R (Result): kết quả đo được hoặc bài học rút ra.
Thiếu R hoặc A mơ hồ thường chỉ đạt mức 2-3."""

ROUND_TYPES = {
    "screening": "Vòng sàng lọc: động lực, hiểu biết về vị trí, kỳ vọng cơ bản.",
    "behavioral": "Vòng hành vi: câu hỏi STAR về tình huống đã trải qua.",
    "technical": "Vòng chuyên môn: kiến thức và cách giải quyết vấn đề kỹ thuật của vị trí.",
    "final": "Vòng cuối: phù hợp văn hóa, định hướng phát triển, câu hỏi tổng hợp.",
}

ENGAGEMENT_PRACTICES = [
    (["luong", "thu nhap", "phuc loi", "dai ngo", "thuong"],
     "Rà soát khung lương theo thị trường; minh bạch cách tính thưởng và lộ trình tăng lương."),
    (["quan ly", "sep", "lanh dao", "truong phong"],
     "Đào tạo kỹ năng quản lý (1:1 định kỳ, phản hồi xây dựng); khảo sát 360 cho quản lý trực tiếp."),
    (["qua tai", "ap luc", "tang ca", "khoi luong", "burnout", "met moi"],
     "Đánh giá lại phân bổ khối lượng; giới hạn tăng ca; ưu tiên hóa công việc theo quý."),
    (["phat trien", "thang tien", "dao tao", "hoc hoi", "lo trinh"],
     "Xây lộ trình nghề nghiệp rõ ràng; ngân sách đào tạo cá nhân; chương trình mentor nội bộ."),
    (["ghi nhan", "khen thuong", "cong nhan"],
     "Cơ chế ghi nhận kịp thời (peer recognition), công khai thành tích theo tháng."),
    (["giao tiep", "thong tin", "minh bach", "truyen thong"],
     "Họp toàn thể định kỳ; chia sẻ chiến lược và kết quả kinh doanh; kênh hỏi đáp ẩn danh."),
    (["linh hoat", "lam viec tu xa", "remote", "gio giac"],
     "Thí điểm chính sách làm việc linh hoạt có mục tiêu đo lường rõ."),
    (["dong nghiep", "lam viec nhom", "phoi hop", "xung dot"],
     "Hoạt động gắn kết liên phòng ban; quy trình phối hợp và giải quyết xung đột rõ ràng."),
    (["moi truong", "van phong", "co so vat chat", "cong cu", "thiet bi"],
     "Khảo sát nhu cầu công cụ/thiết bị; ưu tiên đầu tư vào điểm nghẽn năng suất."),
    (["nghi viec", "roi di", "tim viec", "chuyen viec"],
     "Phỏng vấn giữ chân (stay interview) với nhóm có rủi ro; rà soát nguyên nhân từ dữ liệu nghỉ việc."),
]


def engagement_practices(topics: list[str], limit: int = 6) -> list[str]:
    text = fold(" ".join(topics))
    hits = [p for kws, p in ENGAGEMENT_PRACTICES if any(k in text for k in kws)]
    return hits[:limit] or [p for _, p in ENGAGEMENT_PRACTICES[:3]]
