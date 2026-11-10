"use client";

import { useState } from "react";
import { post } from "@/lib/api";
import type { SurveyQuestion } from "@/lib/types";
import { ErrorBox, Notice } from "./ui";

export interface SurveyInput { title: string; description: string; period_label: string; questions: SurveyQuestion[] }

export function SurveyEditor({ initial, onSave, saving }: { initial: SurveyInput; onSave: (s: SurveyInput) => void; saving: boolean }) {
  const [s, setS] = useState<SurveyInput>(initial);
  const [goal, setGoal] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setQ = (i: number, patch: Partial<SurveyQuestion>) => setS({ ...s, questions: s.questions.map((q, j) => (j === i ? { ...q, ...patch } : q)) });

  async function draft() {
    setBusy(true);
    setError(null);
    try {
      const r = await post<{ questions: SurveyQuestion[] }>("/surveys/draft", { goal });
      setS({ ...s, questions: r.questions });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="card grid gap-3 sm:grid-cols-3">
        <div className="sm:col-span-2">
          <label className="label">Tiêu đề</label>
          <input className="input" value={s.title} onChange={(e) => setS({ ...s, title: e.target.value })} />
        </div>
        <div>
          <label className="label">Kỳ khảo sát (để so sánh giữa các kỳ)</label>
          <input className="input" placeholder="VD: Q3/2026" value={s.period_label} onChange={(e) => setS({ ...s, period_label: e.target.value })} />
        </div>
        <div className="sm:col-span-3">
          <label className="label">Lời giới thiệu cho nhân viên</label>
          <textarea className="input" value={s.description} onChange={(e) => setS({ ...s, description: e.target.value })} />
        </div>
      </div>

      <div className="card space-y-3">
        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-60 flex-1">
            <label className="label">Mục tiêu khảo sát (để AI soạn câu hỏi)</label>
            <input className="input" placeholder="VD: Đo mức gắn kết sau đợt tái cấu trúc phòng Kinh doanh" value={goal} onChange={(e) => setGoal(e.target.value)} />
          </div>
          <button className="btn-ghost" onClick={draft} disabled={busy}>{busy ? "AI đang soạn..." : "AI soạn câu hỏi"}</button>
        </div>
        <Notice>Không hỏi thông tin có thể nhận diện người trả lời (tên, tuổi, thâm niên chi tiết...). Phòng ban lấy từ hồ sơ và chỉ hiển thị khi đủ số người trả lời.</Notice>
        {s.questions.map((q, i) => (
          <div key={i} className="grid items-start gap-2 rounded-lg border border-slate-200 p-3 sm:grid-cols-12">
            <select className="input sm:col-span-2" value={q.type} onChange={(e) => setQ(i, { type: e.target.value as SurveyQuestion["type"] })}>
              <option value="likert">Thang 1-5</option>
              <option value="text">Câu mở</option>
            </select>
            <input className="input sm:col-span-7" value={q.text} onChange={(e) => setQ(i, { text: e.target.value })} />
            <input className="input sm:col-span-2" placeholder="Nhóm" value={q.dimension} onChange={(e) => setQ(i, { dimension: e.target.value })} />
            <button className="text-sm text-red-600 hover:underline sm:col-span-1" onClick={() => setS({ ...s, questions: s.questions.filter((_, j) => j !== i) })}>Xóa</button>
          </div>
        ))}
        <button className="btn-ghost" onClick={() => setS({ ...s, questions: [...s.questions, { id: "", type: "likert", text: "", dimension: "Chung" }] })}>+ Thêm câu hỏi</button>
      </div>
      <ErrorBox message={error} />
      <button className="btn" disabled={saving || !s.title || !s.questions.length} onClick={() => onSave(s)}>{saving ? "Đang lưu..." : "Lưu khảo sát"}</button>
    </div>
  );
}
