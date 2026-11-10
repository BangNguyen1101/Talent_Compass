"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Job, JobInput } from "@/lib/types";
import { JobEditor, LEVELS } from "@/components/JobEditor";
import { AiNotice, ErrorBox, RequireAuth } from "@/components/ui";

function NewJob() {
  const router = useRouter();
  const { user } = useAuth();
  const [form, setForm] = useState({ title: "", level: "junior", department: user?.department ?? "", job_family: "", context: "" });
  const [draft, setDraft] = useState<JobInput | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isCompany = ["hr", "manager", "hiring_lead"].includes(user?.role ?? "");

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const d = await post<JobInput>("/jobs/generate", form);
      setDraft({ ...d, headcount: d.headcount || 1 });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function save(job: JobInput) {
    setBusy(true);
    setError(null);
    try {
      const saved = await post<Job>("/jobs", job);
      router.push(`/jobs/${saved.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Tạo JD & khung năng lực</h1>
      {!draft ? (
        <form onSubmit={generate} className="card space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="sm:col-span-2">
              <label className="label">Vị trí</label>
              <input className="input" required placeholder="VD: Backend Developer (Python)" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </div>
            <div>
              <label className="label">Cấp độ</label>
              <select className="input" value={form.level} onChange={(e) => setForm({ ...form, level: e.target.value })}>
                {LEVELS.map((l) => <option key={l}>{l}</option>)}
              </select>
            </div>
            {isCompany && (
              <>
                <div>
                  <label className="label">Phòng ban</label>
                  <input className="input" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} />
                </div>
                <div className="sm:col-span-2">
                  <label className="label">Nhóm vị trí (AI dùng JD cùng nhóm đã ban hành làm chuẩn)</label>
                  <input className="input" placeholder="VD: Backend" value={form.job_family} onChange={(e) => setForm({ ...form, job_family: e.target.value })} />
                </div>
              </>
            )}
          </div>
          <div>
            <label className="label">Mô tả sơ bộ hoặc dán JD gốc</label>
            <textarea className="input min-h-40" placeholder="Công nghệ, quy mô nhóm, sản phẩm, trách nhiệm chính..." value={form.context} onChange={(e) => setForm({ ...form, context: e.target.value })} />
          </div>
          <ErrorBox message={error} />
          <div className="flex flex-wrap items-center gap-4">
            <button className="btn" disabled={busy}>{busy ? "AI đang soạn..." : "Soạn bằng AI"}</button>
            <AiNotice extra={isCompany ? "AI dùng phong cách thương hiệu và từ điển năng lực của công ty." : undefined} />
          </div>
        </form>
      ) : (
        <>
          <p className="text-sm text-slate-600">Bản nháp do AI soạn. Hãy biên tập và chạy kiểm tra trước khi lưu.</p>
          <ErrorBox message={error} />
          <JobEditor initial={draft} onSave={save} saving={busy} />
        </>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth roles={["student", "advisor", "hr", "manager", "hiring_lead"]}>
      <NewJob />
    </RequireAuth>
  );
}
