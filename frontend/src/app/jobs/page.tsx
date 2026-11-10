"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Job } from "@/lib/types";
import { ErrorBox, RequireAuth } from "@/components/ui";

const STATUS: Record<Job["status"], string> = { draft: "Nháp / riêng tư", published: "Đang tuyển", closed: "Đã đóng" };

function JobList() {
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Job[]>("/jobs").then(setJobs).catch((e) => setError(e.message));
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">JD & khung năng lực</h1>
          <p className="text-sm text-slate-600">Chọn một JD để chấm CV hoặc phỏng vấn thử theo đúng vị trí đó.</p>
        </div>
        <Link href="/jobs/new" className="btn">
          + Tạo JD bằng AI
        </Link>
      </div>
      <ErrorBox message={error} />
      {jobs === null && !error && <p className="text-slate-500">Đang tải...</p>}
      {jobs?.length === 0 && (
        <div className="card text-center text-slate-600">
          Chưa có JD nào. Hãy tạo JD đầu tiên, hoặc dán JD từ một tin tuyển dụng bạn quan tâm.
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {jobs?.map((j) => (
          <Link key={j.id} href={`/jobs/${j.id}`} className="card block transition hover:border-indigo-300">
            <div className="flex items-start justify-between gap-2">
              <p className="font-semibold">{j.title}</p>
              <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{STATUS[j.status]}</span>
            </div>
            <p className="mt-1 text-sm text-slate-500">Cấp độ: {j.level}</p>
            <div className="mt-3 flex flex-wrap gap-1">
              {j.competencies.map((c) => (
                <span key={c.name} className="rounded bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700">
                  {c.name}
                </span>
              ))}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <JobList />
    </RequireAuth>
  );
}
