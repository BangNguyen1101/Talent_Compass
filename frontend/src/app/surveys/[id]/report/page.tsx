"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { GroupStats, Insight } from "@/lib/types";
import { DepartmentTable, OverallStats, type Comparison } from "@/components/SurveyStats";
import { ErrorBox, Notice, RequireAuth } from "@/components/ui";

interface Report {
  title: string; period_label: string; analyzed_at: string | null;
  overall: GroupStats; departments: Record<string, GroupStats>; comparison: Comparison | null;
  persistent_topics: string[]; insights: Insight[]; warnings: string[];
}

function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const [r, setR] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Report>(`/surveys/${id}/report`).then(setR).catch((e) => setError(e.message));
  }, [id]);

  if (!r) return error ? <ErrorBox message={error} /> : <p className="text-slate-500">Đang tải...</p>;
  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-medium uppercase tracking-wide text-indigo-700">Báo cáo lãnh đạo</p>
        <h1 className="text-2xl font-bold">{r.title}</h1>
        <p className="text-sm text-slate-500">{r.period_label}{r.analyzed_at && ` · phân tích ngày ${new Date(r.analyzed_at).toLocaleDateString("vi-VN")}`}</p>
      </div>
      <Notice>Báo cáo chỉ gồm số liệu tổng hợp đã ẩn danh và các insight đã được HR xem xét, duyệt.</Notice>
      {r.warnings.length > 0 && <Notice tone="warn" title="Giới hạn của dữ liệu">{r.warnings.map((w) => <p key={w}>• {w}</p>)}</Notice>}
      <OverallStats overall={r.overall} comparison={r.comparison} />
      <DepartmentTable departments={r.departments} minGroup={5} />
      {r.persistent_topics.length > 0 && <Notice tone="danger" title="Vấn đề tồn đọng qua nhiều kỳ">{r.persistent_topics.join(", ")}</Notice>}
      <div className="space-y-3">
        <h2 className="text-lg font-semibold">Insight đã duyệt & kế hoạch hành động</h2>
        {r.insights.length === 0 && <p className="text-sm text-slate-500">HR chưa duyệt insight nào cho kỳ này.</p>}
        {r.insights.map((i) => (
          <div key={i.id} className="card space-y-1">
            <p className="font-semibold">{i.title}</p>
            <p className="text-sm text-slate-700">{i.detail}</p>
            {i.departments.length > 0 && <p className="text-xs text-slate-500">Phòng ban: {i.departments.join(", ")}</p>}
            <ul className="list-disc pl-5 text-sm">{i.selected_actions.map((a) => <li key={a}>{a}</li>)}</ul>
            {i.hr_note && <p className="text-xs text-slate-500">Ghi chú HR: {i.hr_note}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth roles={["hr", "manager"]}>
      <ReportPage />
    </RequireAuth>
  );
}
