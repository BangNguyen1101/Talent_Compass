"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { STAGE } from "@/lib/roles";
import type { Application } from "@/lib/types";
import { Badge, ErrorBox, RequireAuth } from "@/components/ui";

function Applications() {
  const [apps, setApps] = useState<Application[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<Application[]>("/me/applications").then(setApps).catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  async function withdraw(id: string) {
    if (!confirm("Rút đơn ứng tuyển này?")) return;
    try {
      await post(`/me/applications/${id}/withdraw`);
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Đơn ứng tuyển của tôi</h1>
        <p className="text-sm text-slate-600">Khi ứng tuyển, công ty nhận CV của bạn đã được che email, số điện thoại, ngày sinh, địa chỉ.</p>
      </div>
      <ErrorBox message={error} />
      {apps?.length === 0 && (
        <div className="card text-center text-slate-600">
          Bạn chưa ứng tuyển vị trí nào. <Link href="/jobs" className="text-indigo-700 underline">Tìm việc làm</Link>
        </div>
      )}
      <div className="space-y-3">
        {apps?.map((a) => (
          <div key={a.id} className="card flex flex-wrap items-center justify-between gap-3">
            <div>
              <Link href={`/jobs/${a.jd_id}`} className="font-medium hover:text-indigo-700">{a.title}</Link>
              <p className="text-sm text-indigo-700">{a.company}</p>
              <p className="text-xs text-slate-500">
                {a.level} · nộp ngày {new Date(a.applied_at).toLocaleDateString("vi-VN")}
                {a.match_score != null && ` · khớp CV ${a.match_score}%`}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge cls={STAGE[a.stage]?.cls}>{a.status}</Badge>
              {a.can_withdraw && <button className="btn-ghost px-3 py-1 text-red-600" onClick={() => withdraw(a.id)}>Rút đơn</button>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth roles={["student"]}>
      <Applications />
    </RequireAuth>
  );
}
