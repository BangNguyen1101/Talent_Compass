"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Job } from "@/lib/types";
import { ErrorBox, RequireAuth } from "@/components/ui";

function Approvals() {
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Job[]>("/jobs/pending-approval").then(setJobs).catch((e) => setError(e.message));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">JD chờ phê duyệt</h1>
        <p className="text-sm text-slate-600">JD chỉ được ban hành sau khi đủ số cấp duyệt. Bạn không thể tự duyệt JD do mình tạo.</p>
      </div>
      <ErrorBox message={error} />
      {jobs?.length === 0 && <div className="card text-slate-600">Không có JD nào đang chờ duyệt.</div>}
      <div className="space-y-3">
        {jobs?.map((j) => {
          const approved = j.approvals.filter((a) => a.decision === "approved").length;
          return (
            <Link key={j.id} href={`/jobs/${j.id}`} className="card flex flex-wrap items-center justify-between gap-2 hover:border-indigo-300">
              <div>
                <p className="font-medium">{j.title}</p>
                <p className="text-xs text-slate-500">{j.department} · {j.level} · tuyển {j.headcount} người</p>
              </div>
              <div className="text-right text-sm">
                {j.bias_issues.length > 0 && <p className="text-red-600">⚠ {j.bias_issues.length} cảnh báo thiên vị</p>}
                <p className="text-slate-600">Đã có {approved} lượt duyệt</p>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth roles={["manager"]}>
      <Approvals />
    </RequireAuth>
  );
}
