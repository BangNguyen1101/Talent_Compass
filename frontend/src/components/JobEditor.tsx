"use client";

import { useState } from "react";
import { post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Competency, JobChecks, JobInput } from "@/lib/types";
import { BiasList, ErrorBox, Notice } from "./ui";

const EMPTY_COMP: Competency = {
  name: "",
  category: "technical",
  description: "",
  required_level: 3,
  weight: 1,
  rubric: [1, 2, 3, 4, 5].map((level) => ({ level, descriptor: "" })),
};

export const LEVELS = ["intern", "fresher", "junior", "middle", "senior", "lead"];

export function JobEditor({ initial, onSave, saving, jobId }: { initial: JobInput; onSave: (j: JobInput) => void; saving: boolean; jobId?: string }) {
  const { user } = useAuth();
  const [job, setJob] = useState<JobInput>(initial);
  const [open, setOpen] = useState<number | null>(null);
  const [checks, setChecks] = useState<JobChecks | null>(null);
  const [changes, setChanges] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isCompany = user?.role === "hr" || user?.role === "manager" || user?.role === "hiring_lead";

  const updateComp = (i: number, patch: Partial<Competency>) =>
    setJob({ ...job, competencies: job.competencies.map((c, idx) => (idx === i ? { ...c, ...patch } : c)) });

  async function runChecks() {
    setBusy("check");
    setError(null);
    try {
      setChecks(await post<JobChecks>(`/jobs/check${jobId ? `?exclude_id=${jobId}` : ""}`, job));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function neutralize() {
    setBusy("fix");
    try {
      const r = await post<{ content: string; changes: string[]; remaining: unknown[] }>("/jobs/neutralize", { content: job.content });
      setJob({ ...job, content: r.content });
      setChanges(r.changes);
      setChecks(checks ? { ...checks, bias: r.remaining as JobChecks["bias"] } : null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  function save() {
    if (!job.title.trim()) return setError("Cần nhập tên vị trí");
    if (job.competencies.some((c) => !c.name.trim())) return setError("Mỗi năng lực cần có tên");
    if (job.competencies.length === 0) return setError("Cần ít nhất một năng lực");
    setError(null);
    onSave(job);
  }

  return (
    <div className="space-y-5">
      <div className="card grid gap-4 sm:grid-cols-6">
        <div className="sm:col-span-3">
          <label className="label">Tên vị trí</label>
          <input className="input" value={job.title} onChange={(e) => setJob({ ...job, title: e.target.value })} />
        </div>
        <div className="sm:col-span-1">
          <label className="label">Cấp độ</label>
          <select className="input" value={job.level} onChange={(e) => setJob({ ...job, level: e.target.value })}>
            {LEVELS.map((l) => <option key={l}>{l}</option>)}
          </select>
        </div>
        {isCompany && (
          <>
            <div className="sm:col-span-2">
              <label className="label">Số lượng cần tuyển</label>
              <input className="input" type="number" min={1} value={job.headcount} onChange={(e) => setJob({ ...job, headcount: Number(e.target.value) })} />
            </div>
            <div className="sm:col-span-3">
              <label className="label">Phòng ban</label>
              <input className="input" value={job.department} onChange={(e) => setJob({ ...job, department: e.target.value })} />
            </div>
            <div className="sm:col-span-3">
              <label className="label">Nhóm vị trí (để so sánh nhất quán, vd. Backend)</label>
              <input className="input" value={job.job_family} onChange={(e) => setJob({ ...job, job_family: e.target.value })} />
            </div>
          </>
        )}
        <div className="sm:col-span-6">
          <label className="label">Nội dung JD (Markdown)</label>
          <textarea className="input min-h-56 font-mono text-xs" value={job.content} onChange={(e) => setJob({ ...job, content: e.target.value })} />
        </div>
      </div>

      <div className="card space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Khung năng lực ({job.competencies.length})</h2>
          <button className="btn-ghost px-3 py-1" onClick={() => { setJob({ ...job, competencies: [...job.competencies, structuredClone(EMPTY_COMP)] }); setOpen(job.competencies.length); }}>
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
              <button className="text-indigo-700 hover:underline" onClick={() => setOpen(open === i ? null : i)}>{open === i ? "Ẩn rubric" : "Xem / sửa rubric"}</button>
              <button className="text-red-600 hover:underline" onClick={() => setJob({ ...job, competencies: job.competencies.filter((_, idx) => idx !== i) })}>Xóa</button>
            </div>
            {open === i && (
              <div className="mt-3 space-y-2">
                <textarea className="input" placeholder="Mô tả năng lực" value={c.description} onChange={(e) => updateComp(i, { description: e.target.value })} />
                {c.rubric.map((r, ri) => (
                  <div key={r.level} className="flex items-start gap-2">
                    <span className="mt-2 w-14 shrink-0 text-xs font-semibold text-slate-500">Mức {r.level}</span>
                    <input className="input" value={r.descriptor} onChange={(e) => updateComp(i, { rubric: c.rubric.map((x, xi) => (xi === ri ? { ...x, descriptor: e.target.value } : x)) })} />
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="card space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="mr-auto font-semibold">Kiểm tra trước khi lưu</h2>
          <button className="btn-ghost" onClick={runChecks} disabled={!!busy}>{busy === "check" ? "Đang kiểm tra..." : "Kiểm tra thiên vị, nhất quán, định biên"}</button>
        </div>
        {checks && (
          <div className="space-y-3">
            {checks.bias.length > 0 ? (
              <>
                <BiasList issues={checks.bias} />
                <button className="btn-ghost" onClick={neutralize} disabled={!!busy}>{busy === "fix" ? "AI đang viết lại..." : "AI viết lại trung tính"}</button>
              </>
            ) : (
              <Notice tone="ok">Không phát hiện ngôn ngữ thiên vị.</Notice>
            )}
            {changes.length > 0 && <Notice title="Đã sửa">{changes.map((c) => <p key={c}>• {c}</p>)}</Notice>}
            {checks.consistency.length > 0 ? (
              <Notice tone="warn" title="Chưa nhất quán với vị trí cùng nhóm">{checks.consistency.map((c, i) => <p key={i}>• {c.message}</p>)}</Notice>
            ) : (
              isCompany && <Notice tone="ok">Nhất quán với các vị trí cùng nhóm (hoặc chưa có vị trí liên quan).</Notice>
            )}
            {checks.headcount && <Notice tone="warn" title="Định biên">{checks.headcount.message}</Notice>}
          </div>
        )}
      </div>

      <ErrorBox message={error} />
      <button className="btn" onClick={save} disabled={saving}>{saving ? "Đang lưu..." : "Lưu JD"}</button>
    </div>
  );
}
