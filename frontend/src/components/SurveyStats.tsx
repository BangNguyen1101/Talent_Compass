"use client";

import type { GroupStats } from "@/lib/types";
import { ScoreBar, Stat } from "./ui";

export interface Comparison {
  engagement_index: { current: number | null; previous: number | null; delta: number | null };
  dimensions: Record<string, { current: number; previous: number | null; delta: number | null }>;
}

const SENT: Record<string, string> = { positive: "Tích cực", neutral: "Trung lập", negative: "Tiêu cực" };

export function OverallStats({ overall, comparison, minGroup }: { overall: GroupStats; comparison?: Comparison | null; minGroup?: number }) {
  if (overall.suppressed) return <p className="text-sm text-slate-500">Chưa đủ {minGroup ?? 5} phản hồi để hiển thị kết quả (bảo vệ ẩn danh).</p>;
  const d = comparison?.engagement_index.delta;
  const total = Object.values(overall.sentiment ?? {}).reduce((a, b) => a + b, 0) || 1;
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Chỉ số gắn kết" value={overall.engagement_index != null ? `${overall.engagement_index}/100` : "—"}
          hint={d != null ? `${d > 0 ? "+" : ""}${d} so với kỳ trước` : "Trung bình các câu thang 1-5"} tone={d != null ? (d >= 0 ? "ok" : "warn") : undefined} />
        <Stat label="Phản hồi tiêu cực" value={`${Math.round((overall.negative_ratio ?? 0) * 100)}%`} tone={(overall.negative_ratio ?? 0) >= 0.4 ? "warn" : undefined} hint="Trong các câu trả lời mở" />
        <Stat label="Tín hiệu rủi ro nghỉ việc" value={`${Math.round((overall.risk_ratio ?? 0) * 100)}%`} tone={(overall.risk_ratio ?? 0) >= 0.2 ? "warn" : undefined} hint="Chỉ thống kê theo nhóm, không theo cá nhân" />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="card space-y-2">
          <h3 className="font-semibold">Theo nhóm chủ đề (1-5)</h3>
          {Object.entries(overall.dimension_avgs ?? {}).map(([k, v]) => {
            const cmp = comparison?.dimensions[k];
            return (
              <div key={k} className="space-y-1">
                <div className="flex justify-between text-sm tabular-nums">
                  <span>{k}</span>
                  <span>{v}{cmp?.delta != null && <span className={cmp.delta >= 0 ? "text-emerald-700" : "text-red-600"}> ({cmp.delta > 0 ? "+" : ""}{cmp.delta})</span>}</span>
                </div>
                <ScoreBar value={v} required={3} />
              </div>
            );
          })}
        </div>
        <div className="card space-y-2">
          <h3 className="font-semibold">Cảm xúc trong câu trả lời mở</h3>
          {Object.entries(overall.sentiment ?? {}).map(([k, n]) => (
            <div key={k} className="space-y-1">
              <div className="flex justify-between text-sm tabular-nums"><span>{SENT[k] ?? k}</span><span>{n} ({Math.round((n / total) * 100)}%)</span></div>
              <div className="h-2 rounded-full bg-slate-100">
                <div className={`h-2 rounded-full ${k === "negative" ? "bg-red-400" : k === "positive" ? "bg-emerald-500" : "bg-slate-400"}`} style={{ width: `${(n / total) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function DepartmentTable({ departments, minGroup }: { departments: Record<string, GroupStats>; minGroup: number }) {
  return (
    <div className="card overflow-x-auto">
      <h3 className="mb-2 font-semibold">Theo phòng ban</h3>
      <table className="w-full text-sm">
        <thead><tr className="border-b text-left text-slate-500"><th className="py-2">Phòng ban</th><th>Phản hồi</th><th>Gắn kết</th><th>Tiêu cực</th><th>Rủi ro nghỉ việc</th><th>Chủ đề nổi bật</th></tr></thead>
        <tbody>
          {Object.entries(departments).map(([d, v]) => (
            <tr key={d} className="border-b border-slate-100 align-top tabular-nums">
              <td className="py-2 font-medium">{d}</td>
              <td>{v.n}</td>
              {v.suppressed ? (
                <td colSpan={4} className="text-slate-500">Ẩn do dưới {minGroup} phản hồi (bảo vệ ẩn danh)</td>
              ) : (
                <>
                  <td>{v.engagement_index ?? "—"}</td>
                  <td className={(v.negative_ratio ?? 0) >= 0.5 ? "font-semibold text-red-600" : ""}>{Math.round((v.negative_ratio ?? 0) * 100)}%</td>
                  <td className={(v.risk_ratio ?? 0) >= 0.2 ? "font-semibold text-red-600" : ""}>{Math.round((v.risk_ratio ?? 0) * 100)}%</td>
                  <td className="text-slate-600">{(v.top_topics ?? []).slice(0, 3).map(([t, n]) => `${t} (${n})`).join(", ")}</td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
