"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import type { Competency, JobInput } from "@/lib/types";
import { ErrorBox } from "./ui";

const EMPTY_COMP: Competency = {
  name: "",
  category: "technical",
  description: "",
  required_level: 3,
  weight: 1,
  rubric: [1, 2, 3, 4, 5].map((level) => ({ level, descriptor: "" })),
};

export function JobEditor({ initial, onSave, saving }: { initial: JobInput; onSave: (j: JobInput) => void; saving: boolean }) {
  const { user } = useAuth();
  const [job, setJob] = useState<JobInput>(initial);
  const [open, setOpen] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const updateComp = (i: number, patch: Partial<Competency>) =>
    setJob({ ...job, competencies: job.competencies.map((c, idx) => (idx === i ? { ...c, ...patch } : c)) });

  function save() {
    if (!job.title.trim()) return setError("Cần nhập tên vị trí");
    if (job.competencies.some((c) => !c.name.trim())) return setError("Mỗi năng lực cần có tên");
    if (job.competencies.length === 0) return setError("Cần ít nhất một năng lực");
    setError(null);
    onSave(job);
  }

  return (
    <div className="space-y-5">
      <div className="card grid gap-4 sm:grid-cols-3">
        <div className="sm:col-span-2">
          <label className="label">Tên vị trí</label>
          <input className="input" value={job.title} onChange={(e) => setJob({ ...job, title: e.target.value })} />
        </div>
        <div>
          <label className="label">Cấp độ</label>
          <input className="input" value={job.level} onChange={(e) => setJob({ ...job, level: e.target.value })} />
        </div>
        <div className="sm:col-span-3">
          <label className="label">Nội dung JD (Markdown)</label>
          <textarea className="input min-h-48 font-mono text-xs" value={job.content} onChange={(e) => setJob({ ...job, content: e.target.value })} />
        </div>
        {user?.role === "hr" && (
          <div>
            <label className="label">Trạng thái</label>
            <select className="input" value={job.status} onChange={(e) => setJob({ ...job, status: e.target.value as JobInput["status"] })}>
              <option value="draft">Nháp (chỉ công ty thấy)</option>
              <option value="published">Công khai cho ứng viên</option>
              <option value="closed">Đã đóng</option>
            </select>
          </div>
        )}
      </div>

      <div className="card space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Khung năng lực ({job.competencies.length})</h2>
          <button
            className="btn-ghost px-3 py-1"
            onClick={() => {
              setJob({ ...job, competencies: [...job.competencies, structuredClone(EMPTY_COMP)] });
              setOpen(job.competencies.length);
            }}
          >
            + Thêm năng lực
          </button>
        </div>
        {job.competencies.map((c, i) => (
          <div key={i} className="rounded-lg border border-slate-200 p-3">
            <div className="grid items-end gap-3 sm:grid-cols-12">
              <div className="sm:col-span-5">
                <label className="label">Tên</label>
                <input className="input" value={c.name} onChange={(e) => updateComp(i, { name: e.target.value })} />
              </div>
              <div className="sm:col-span-3">
                <label className="label">Loại</label>
                <select className="input" value={c.category} onChange={(e) => updateComp(i, { category: e.target.value })}>
                  <option value="technical">Chuyên môn</option>
                  <option value="soft">Kỹ năng mềm</option>
                  <option value="domain">Nghiệp vụ</option>
                </select>
              </div>
              <div className="sm:col-span-2">
                <label className="label">Mức yêu cầu</label>
                <input className="input" type="number" min={1} max={5} value={c.required_level} onChange={(e) => updateComp(i, { required_level: Number(e.target.value) })} />
              </div>
              <div className="sm:col-span-2">
                <label className="label">Trọng số</label>
                <input className="input" type="number" min={0.1} max={5} step={0.1} value={c.weight} onChange={(e) => updateComp(i, { weight: Number(e.target.value) })} />
              </div>
            </div>
            <div className="mt-2 flex gap-3 text-sm">
              <button className="text-indigo-700 hover:underline" onClick={() => setOpen(open === i ? null : i)}>
                {open === i ? "Ẩn rubric" : "Xem / sửa rubric"}
              </button>
              <button className="text-red-600 hover:underline" onClick={() => setJob({ ...job, competencies: job.competencies.filter((_, idx) => idx !== i) })}>
                Xóa
              </button>
            </div>
            {open === i && (
              <div className="mt-3 space-y-2">
                <textarea className="input" placeholder="Mô tả năng lực" value={c.description} onChange={(e) => updateComp(i, { description: e.target.value })} />
                {c.rubric.map((r, ri) => (
                  <div key={r.level} className="flex items-start gap-2">
                    <span className="mt-2 w-14 shrink-0 text-xs font-semibold text-slate-500">Mức {r.level}</span>
                    <input
                      className="input"
                      value={r.descriptor}
                      onChange={(e) => updateComp(i, { rubric: c.rubric.map((x, xi) => (xi === ri ? { ...x, descriptor: e.target.value } : x)) })}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <ErrorBox message={error} />
      <button className="btn" onClick={save} disabled={saving}>
        {saving ? "Đang lưu..." : "Lưu JD"}
      </button>
    </div>
  );
}
