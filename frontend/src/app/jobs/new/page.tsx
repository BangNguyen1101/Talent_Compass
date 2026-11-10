"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { post } from "@/lib/api";
import type { Job, JobInput } from "@/lib/types";
import { JobEditor } from "@/components/JobEditor";
import { AiNotice, ErrorBox, RequireAuth } from "@/components/ui";

function NewJob() {
  const router = useRouter();
  const [form, setForm] = useState({ title: "", level: "junior", context: "" });
  const [draft, setDraft] = useState<JobInput | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setDraft(await post<JobInput>("/jobs/generate", form));
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
                <option value="intern">Thực tập</option>
                <option value="fresher">Fresher</option>
                <option value="junior">Junior</option>
                <option value="middle">Middle</option>
                <option value="senior">Senior</option>
              </select>
            </div>
          </div>
          <div>
            <label className="label">Thông tin thêm hoặc dán JD gốc (không bắt buộc)</label>
            <textarea
              className="input min-h-40"
              placeholder="Dán nguyên văn JD từ tin tuyển dụng, hoặc mô tả ngắn: công nghệ, quy mô nhóm, sản phẩm..."
              value={form.context}
              onChange={(e) => setForm({ ...form, context: e.target.value })}
            />
          </div>
          <ErrorBox message={error} />
          <div className="flex items-center gap-4">
            <button className="btn" disabled={busy}>
              {busy ? "AI đang soạn..." : "Soạn bằng AI"}
            </button>
            <AiNotice />
          </div>
        </form>
      ) : (
        <>
          <p className="text-sm text-slate-600">Bản nháp do AI soạn. Hãy kiểm tra và chỉnh sửa trước khi lưu.</p>
          <ErrorBox message={error} />
          <JobEditor initial={draft} onSave={save} saving={busy} />
        </>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <NewJob />
    </RequireAuth>
  );
}
