"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/** Báo rõ khi backend chạy chế độ dữ liệu mẫu, để không ai nhầm nội dung khuôn mẫu là do AI viết. */
export function ModeBanner() {
  const [mock, setMock] = useState(false);
  useEffect(() => {
    api<{ llm: string }>("/health").then((h) => setMock(h.llm === "mock")).catch(() => {});
  }, []);
  if (!mock) return null;
  return (
    <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-xs text-amber-900">
      Đang chạy <b>chế độ dữ liệu mẫu</b>: JD, câu hỏi, nhận xét có nhãn [MẪU] được ghép từ khuôn có sẵn, không phải do AI viết.
      Quản trị viên cần đặt <code>GEMINI_API_KEY</code> hoặc <code>ANTHROPIC_API_KEY</code> trên server để bật AI.
    </div>
  );
}
