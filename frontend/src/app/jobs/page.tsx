"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { JOB_STATUS } from "@/lib/roles";
import type { Job } from "@/lib/types";
import { Badge, ErrorBox, RequireAuth } from "@/components/ui";

function JobList() {
  const { user } = useAuth();
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [filter, setFilter] = useState<string>("all");
  const [error, setError] = useState<string | null>(null);
  const canCreate = ["student", "advisor", "hr", "manager", "hiring_lead"].includes(user!.role);

  useEffect(() => {
    api<Job[]>("/jobs").then(setJobs).catch((e) => setError(e.message));
  }, []);

  const shown = (jobs ?? []).filter((j) => filter === "all" || j.status === filter);
  const hint =
    user!.role === "student"
      ? "Chọn một JD để chấm CV hoặc phỏng vấn thử theo đúng vị trí đó. Bạn cũng có thể dán JD từ tin tuyển dụng thật."
      : user!.role === "advisor"
        ? "Ban hành JD mẫu để sinh viên trong trường luyện CV và phỏng vấn."
        : "Soạn JD, kiểm tra và gửi quản lý phê duyệt trước khi ban hành.";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">JD & khung năng lực</h1>
          <p className="text-sm text-slate-600">{hint}</p>
        </div>
        {canCreate && <Link href="/jobs/new" className="btn">+ Tạo JD bằng AI</Link>}
      </div>
      {jobs && jobs.length > 0 && (
        <div className="flex flex-wrap gap-2 text-sm">
          {["all", "draft", "pending_approval", "rejected", "published", "closed"].map((s) => (
            <button key={s} onClick={() => setFilter(s)} className={filter === s ? "btn px-3 py-1" : "btn-ghost px-3 py-1"}>
              {s === "all" ? "Tất cả" : JOB_STATUS[s as Job["status"]].label}
            </button>
          ))}
        </div>
      )}
      <ErrorBox message={error} />
      {jobs === null && !error && <p className="text-slate-500">Đang tải...</p>}
      {jobs?.length === 0 && <div className="card text-center text-slate-600">Chưa có JD nào.</div>}
      <div className="grid gap-4 sm:grid-cols-2">
        {shown.map((j) => (
          <Link key={j.id} href={`/jobs/${j.id}`} className="card block transition hover:border-indigo-300">
            <div className="flex items-start justify-between gap-2">
              <p className="font-semibold">{j.title}</p>
              <Badge cls={JOB_STATUS[j.status].cls}>{JOB_STATUS[j.status].label}</Badge>
            </div>
            <p className="mt-1 text-sm text-slate-500">
              {j.level}{j.department && ` · ${j.department}`}{j.job_family && ` · ${j.job_family}`}
              {j.org_id === null && " · JD cá nhân"}
            </p>
            {j.bias_issues.length > 0 && <p className="mt-1 text-xs text-red-600">⚠ {j.bias_issues.length} chỗ có thể thiên vị</p>}
            <div className="mt-3 flex flex-wrap gap-1">
              {j.competencies.map((c) => (
                <span key={c.name} className="rounded bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700">{c.name}</span>
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
