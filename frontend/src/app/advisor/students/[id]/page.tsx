"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { ROUND_TYPES } from "@/lib/roles";
import type { AdvisorNote, Assessment, InterviewTurn, Progress } from "@/lib/types";
import { ProgressView } from "@/components/ProgressView";
import { ErrorBox, RequireAuth } from "@/components/ui";

interface Detail {
  student: { id: string; full_name: string; email: string };
  progress: Progress;
  assessments: { id: string; jd: string; overall_score: number; ats_score: number; result: Assessment["result"]; created_at: string }[];
  interviews: { id: string; jd: string; round_type: string; status: string; average_score: number | null; turns: InterviewTurn[]; created_at: string }[];
  notes: AdvisorNote[];
}

function StudentDetail() {
  const { id } = useParams<{ id: string }>();
  const [d, setD] = useState<Detail | null>(null);
  const [note, setNote] = useState({ content: "", target: "general" });
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<Detail>(`/advisor/students/${id}`).then(setD).catch((e) => setError(e.message));
  }, [id]);
  useEffect(load, [load]);

  async function addNote(e: React.FormEvent) {
    e.preventDefault();
    const [target_type, target_id] = note.target === "general" ? ["general", null] : note.target.split(":");
    try {
      await post(`/advisor/students/${id}/notes`, { content: note.content, target_type, target_id });
      setNote({ content: "", target: "general" });
      load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (!d) return error ? <ErrorBox message={error} /> : <p className="text-slate-500">Đang tải...</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{d.student.full_name}</h1>
        <p className="text-sm text-slate-500">{d.student.email}</p>
      </div>
      <ProgressView p={d.progress} />

      <form onSubmit={addNote} className="card space-y-3">
        <h2 className="font-semibold">Nhận xét cho sinh viên</h2>
        <select className="input" value={note.target} onChange={(e) => setNote({ ...note, target: e.target.value })}>
          <option value="general">Nhận xét chung</option>
          {d.assessments.map((a) => <option key={a.id} value={`cv_assessment:${a.id}`}>Lượt chấm CV: {a.jd} ({new Date(a.created_at).toLocaleDateString("vi-VN")})</option>)}
          {d.interviews.map((i) => <option key={i.id} value={`interview:${i.id}`}>Phỏng vấn: {i.jd} ({new Date(i.created_at).toLocaleDateString("vi-VN")})</option>)}
        </select>
        <textarea className="input min-h-24" required placeholder="VD: Phần kinh nghiệm thực tập nên nêu rõ kết quả; luyện thêm câu hỏi về làm việc nhóm." value={note.content} onChange={(e) => setNote({ ...note, content: e.target.value })} />
        <button className="btn">Gửi nhận xét</button>
        {d.notes.length > 0 && (
          <div className="space-y-2 border-t border-slate-200 pt-3">
            {d.notes.map((n) => (
              <div key={n.id} className="text-sm">
                <p className="whitespace-pre-wrap">{n.content}</p>
                <p className="text-xs text-slate-500">{n.advisor} · {n.target_type} · {new Date(n.created_at).toLocaleString("vi-VN")}</p>
              </div>
            ))}
          </div>
        )}
      </form>
      <ErrorBox message={error} />

      <div className="card space-y-3">
        <h2 className="font-semibold">Báo cáo chấm CV ({d.assessments.length})</h2>
        {d.assessments.map((a) => (
          <details key={a.id} className="rounded-lg border border-slate-200 p-3">
            <summary className="cursor-pointer text-sm"><b>{a.jd}</b> · phù hợp {a.overall_score} · ATS {a.ats_score} · {new Date(a.created_at).toLocaleDateString("vi-VN")}</summary>
            <div className="mt-2 space-y-2 text-sm">
              <p>{a.result.overall_comment}</p>
              {a.result.competency_scores.map((s) => <p key={s.competency}>• {s.competency}: {s.score}/5 — {s.evidence}</p>)}
              {!!a.result.guardrail_flagged && <p className="text-amber-700">⚠ {a.result.guardrail_flagged} gợi ý bị guardrail gắn cờ (chi tiết không có trong CV)</p>}
            </div>
          </details>
        ))}
      </div>

      <div className="card space-y-3">
        <h2 className="font-semibold">Buổi phỏng vấn thử ({d.interviews.length})</h2>
        {d.interviews.map((i) => (
          <details key={i.id} className="rounded-lg border border-slate-200 p-3">
            <summary className="cursor-pointer text-sm"><b>{i.jd}</b> · {ROUND_TYPES[i.round_type] ?? i.round_type} · {i.average_score != null ? `${i.average_score}/5` : i.status} · {new Date(i.created_at).toLocaleDateString("vi-VN")}</summary>
            <div className="mt-2 space-y-2 text-sm">
              {i.turns.filter((t) => t.answer).map((t, k) => (
                <div key={k} className={t.parent !== null ? "ml-4 border-l-2 border-slate-200 pl-3" : ""}>
                  <p className="font-medium">{t.question}</p>
                  <p className="text-slate-600">{t.answer}</p>
                  <p className="text-xs text-indigo-700">AI chấm {t.score}/5: {t.feedback}</p>
                </div>
              ))}
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth roles={["advisor"]}>
      <StudentDetail />
    </RequireAuth>
  );
}
