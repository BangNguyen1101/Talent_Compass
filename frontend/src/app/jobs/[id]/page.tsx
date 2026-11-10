"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import type { Interview, Job, JobInput } from "@/lib/types";
import { JobEditor } from "@/components/JobEditor";
import { ErrorBox, RequireAuth } from "@/components/ui";

function JobDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [job, setJob] = useState<Job | null>(null);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Job>(`/jobs/${id}`).then(setJob).catch((e) => setError(e.message));
  }, [id]);

  async function save(input: JobInput) {
    setBusy(true);
    try {
      setJob(await api<Job>(`/jobs/${id}`, { method: "PUT", body: JSON.stringify(input) }));
      setEditing(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function startInterview() {
    setBusy(true);
    setError(null);
    try {
      const s = await post<Interview>("/interviews", { jd_id: id, question_count: 5 });
      router.push(`/interviews/${s.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  if (!job) return error ? <ErrorBox message={error} /> : <p className="text-slate-500">Đang tải...</p>;
  if (editing) return <JobEditor initial={job} onSave={save} saving={busy} />;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{job.title}</h1>
          <p className="text-sm text-slate-500">Cấp độ: {job.level}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href={`/cv?jd=${job.id}`} className="btn">
            Chấm CV theo JD này
          </Link>
          <button className="btn" onClick={startInterview} disabled={busy}>
            {busy ? "Đang tạo câu hỏi..." : "Phỏng vấn thử"}
          </button>
          <button className="btn-ghost" onClick={() => setEditing(true)}>
            Sửa
          </button>
        </div>
      </div>
      <ErrorBox message={error} />

      <div className="card whitespace-pre-wrap text-sm leading-relaxed">{job.content}</div>

      <div className="card">
        <h2 className="mb-3 font-semibold">Khung năng lực</h2>
        <div className="space-y-4">
          {job.competencies.map((c) => (
            <details key={c.name} className="rounded-lg border border-slate-200 p-3">
              <summary className="cursor-pointer">
                <span className="font-medium">{c.name}</span>
                <span className="ml-2 text-xs text-slate-500">
                  yêu cầu mức {c.required_level}/5 · trọng số {c.weight}
                </span>
              </summary>
              <p className="mt-2 text-sm text-slate-600">{c.description}</p>
              <ol className="mt-2 space-y-1 text-sm">
                {c.rubric.map((r) => (
                  <li key={r.level} className={r.level === c.required_level ? "font-medium text-indigo-700" : "text-slate-600"}>
                    <span className="inline-block w-14">Mức {r.level}</span>
                    {r.descriptor}
                  </li>
                ))}
              </ol>
            </details>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <JobDetail />
    </RequireAuth>
  );
}
