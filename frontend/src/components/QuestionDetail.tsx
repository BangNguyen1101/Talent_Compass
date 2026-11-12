"use client";

import { QUESTION_TYPE } from "@/lib/roles";
import type { ScoringGuide } from "@/lib/types";

/** Phần phụ của một câu hỏi phỏng vấn: câu hỏi đào sâu và hướng dẫn chấm yếu / đạt / xuất sắc. */
export function QuestionDetail({ followUps, guide }: { followUps?: string[]; guide?: ScoringGuide | null }) {
  if (!followUps?.length && !guide) return null;
  return (
    <div className="mt-2 space-y-2 text-xs">
      {!!followUps?.length && (
        <div>
          <p className="font-medium text-slate-700">Câu hỏi đào sâu</p>
          <ul className="list-disc pl-5 text-slate-600">{followUps.map((f) => <li key={f}>{f}</li>)}</ul>
        </div>
      )}
      {guide && (
        <div className="grid gap-2 sm:grid-cols-3">
          <p className="rounded bg-red-50 p-2 text-red-800"><b>Yếu (1-2):</b> {guide.weak}</p>
          <p className="rounded bg-amber-50 p-2 text-amber-900"><b>Đạt (3):</b> {guide.solid}</p>
          <p className="rounded bg-emerald-50 p-2 text-emerald-900"><b>Xuất sắc (4-5):</b> {guide.strong}</p>
        </div>
      )}
    </div>
  );
}

export function QuestionTypeTag({ type }: { type?: string }) {
  if (!type) return null;
  return <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium normal-case text-slate-600">{QUESTION_TYPE[type] ?? type}</span>;
}
