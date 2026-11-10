"use client";

import type { FirstLast, Progress } from "@/lib/types";
import { ROUND_TYPES } from "@/lib/roles";
import { Stat } from "./ui";

function delta(fl: FirstLast, unit: string) {
  if (fl.count === 0) return { value: "—", hint: "Chưa có dữ liệu" };
  if (fl.delta === null) return { value: `${fl.latest}${unit}`, hint: "Cần ít nhất 2 lần để so sánh trước/sau" };
  const sign = fl.delta > 0 ? "+" : "";
  return { value: `${sign}${fl.delta}${unit}`, hint: `Lần đầu ${fl.first}${unit} → gần nhất ${fl.latest}${unit} (${fl.count} lần)` };
}

export function ProgressView({ p }: { p: Progress }) {
  const iv = delta(p.interview, "/5");
  const cv = delta(p.cv, "");
  const ats = delta(p.ats, "");
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Điểm phỏng vấn trước → sau" value={iv.value} hint={iv.hint} tone={(p.interview.delta ?? 0) > 0 ? "ok" : undefined} />
        <Stat label="Mức phù hợp CV trước → sau" value={cv.value} hint={cv.hint} tone={(p.cv.delta ?? 0) > 0 ? "ok" : undefined} />
        <Stat label="Điểm ATS trước → sau" value={ats.value} hint={ats.hint} tone={(p.ats.delta ?? 0) > 0 ? "ok" : undefined} />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="card">
          <h3 className="mb-2 font-semibold">Lịch sử phỏng vấn thử</h3>
          {p.interview_history.length === 0 ? <p className="text-sm text-slate-500">Chưa có buổi nào hoàn thành.</p> : (
            <ul className="space-y-1 text-sm tabular-nums">
              {p.interview_history.map((h) => (
                <li key={h.id} className="flex justify-between">
                  <span>{new Date(h.date).toLocaleDateString("vi-VN")} · {ROUND_TYPES[h.round_type] ?? h.round_type}</span>
                  <b>{h.average_score}/5</b>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="card">
          <h3 className="mb-2 font-semibold">Lịch sử chấm CV</h3>
          {p.cv_history.length === 0 ? <p className="text-sm text-slate-500">Chưa chấm CV lần nào.</p> : (
            <ul className="space-y-1 text-sm tabular-nums">
              {p.cv_history.map((h) => (
                <li key={h.id} className="flex justify-between gap-2">
                  <span className="truncate">{new Date(h.date).toLocaleDateString("vi-VN")} · {h.jd}</span>
                  <b className="shrink-0">{h.score} · ATS {h.ats}</b>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
