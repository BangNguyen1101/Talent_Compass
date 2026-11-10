"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ROUND_TYPES } from "@/lib/roles";
import type { Interview, Job } from "@/lib/types";
import { ErrorBox, RequireAuth } from "@/components/ui";

function InterviewList() {
  const [items, setItems] = useState<Interview[] | null>(null);
  const [jobs, setJobs] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api<Interview[]>("/interviews"), api<Job[]>("/jobs")])
      .then(([i, j]) => {
        setItems(i);
        setJobs(Object.fromEntries(j.map((x) => [x.id, x.title])));
      })
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Phỏng vấn thử</h1>
        <p className="text-sm text-slate-600">
          Để bắt đầu buổi mới, mở một JD ở mục <Link href="/jobs" className="text-indigo-700 underline">JD & năng lực</Link> và bấm “Phỏng vấn thử”.
        </p>
      </div>
      <ErrorBox message={error} />
      {items?.length === 0 && <div className="card text-slate-600">Bạn chưa có buổi phỏng vấn thử nào.</div>}
      <div className="space-y-3">
        {items?.map((s) => {
          const answered = s.turns.filter((t) => t.answer).length;
          return (
            <Link key={s.id} href={`/interviews/${s.id}`} className="card flex items-center justify-between hover:border-indigo-300">
              <div>
                <p className="font-medium">{jobs[s.jd_id] ?? "JD đã xóa"}</p>
                <p className="text-xs text-slate-500">{new Date(s.created_at).toLocaleString("vi-VN")}</p>
              </div>
              <span className="text-sm text-slate-600">
                {ROUND_TYPES[s.round_type] ?? s.round_type} ·{" "}
                {s.status === "completed" ? `Hoàn thành${s.average_score != null ? ` · ${s.average_score}/5` : ""}` : `${answered}/${s.turns.length} câu`}
              </span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <InterviewList />
    </RequireAuth>
  );
}
