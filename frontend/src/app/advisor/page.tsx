"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import type { FirstLast } from "@/lib/types";
import { ErrorBox, Notice, RequireAuth, Stat } from "@/components/ui";

interface Dashboard {
  students_total: number; students_active: number; usage_rate: number; usage_target: number; usage_met: boolean;
  csat: number | null; csat_responses: number; csat_target: number; csat_met: boolean;
  interview_improvement_avg: number | null; students_with_improvement_data: number;
}
interface StudentRow { id: string; full_name: string; email: string; shared: boolean; interview?: FirstLast; cv?: FirstLast; last_activity?: string | null }
interface EvalSummary { count: number; overall: number | null; dimensions: Record<string, number>; recent_issues: string[] }

const DIM_LABEL: Record<string, string> = { specificity: "Cụ thể", grounding: "Không bịa", actionability: "Hành động được", fairness: "Công bằng", tone: "Giọng văn" };

function AdvisorDashboard() {
  const [d, setD] = useState<Dashboard | null>(null);
  const [students, setStudents] = useState<StudentRow[]>([]);
  const [evals, setEvals] = useState<EvalSummary | null>(null);
  const [code, setCode] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([api<Dashboard>("/advisor/dashboard"), api<StudentRow[]>("/advisor/students"), api<EvalSummary>("/evals/summary"),
      api<{ join_code: string }>("/org")])
      .then(([a, b, c, o]) => { setD(a); setStudents(b); setEvals(c); setCode(o.join_code); })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  async function runEvals() {
    setBusy(true);
    try {
      await post("/evals/run");
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold">Bảng cố vấn hướng nghiệp</h1>
          <p className="text-sm text-slate-600">Theo dõi KPI và tiến bộ của sinh viên; nhận xét báo cáo do AI tạo.</p>
        </div>
        {code && <p className="text-sm">Mã cho sinh viên tham gia: <code className="rounded bg-slate-100 px-2 py-1 font-mono font-semibold">{code}</code></p>}
      </div>
      <ErrorBox message={error} />
      {d && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Tỷ lệ sinh viên sử dụng" value={`${Math.round(d.usage_rate * 100)}%`} tone={d.usage_met ? "ok" : "warn"}
            hint={`${d.students_active}/${d.students_total} SV · mục tiêu ≥${d.usage_target * 100}%`} />
          <Stat label="CSAT trung bình" value={d.csat != null ? `${d.csat}/5` : "—"} tone={d.csat == null ? undefined : d.csat_met ? "ok" : "warn"}
            hint={`${d.csat_responses} lượt đánh giá · mục tiêu ≥${d.csat_target}`} />
          <Stat label="Cải thiện điểm phỏng vấn" value={d.interview_improvement_avg != null ? `${d.interview_improvement_avg > 0 ? "+" : ""}${d.interview_improvement_avg}` : "—"}
            hint={`Trung bình lần đầu → gần nhất · ${d.students_with_improvement_data} SV có đủ dữ liệu`} tone={(d.interview_improvement_avg ?? 0) > 0 ? "ok" : undefined} />
          <Stat label="Chất lượng phản hồi AI" value={evals?.overall != null ? `${evals.overall}/5` : "—"} hint={`LLM-as-Judge · ${evals?.count ?? 0} mẫu đã chấm`} />
        </div>
      )}

      <div className="card overflow-x-auto">
        <h2 className="mb-3 font-semibold">Sinh viên ({students.length})</h2>
        {students.length === 0 ? <p className="text-sm text-slate-500">Chưa có sinh viên. Gửi mã tham gia ở trên cho sinh viên.</p> : (
          <table className="w-full text-sm">
            <thead><tr className="border-b text-left text-slate-500"><th className="py-2">Sinh viên</th><th>Phỏng vấn (đầu → gần nhất)</th><th>CV (đầu → gần nhất)</th><th>Hoạt động gần nhất</th><th /></tr></thead>
            <tbody>
              {students.map((s) => (
                <tr key={s.id} className="border-b border-slate-100 tabular-nums">
                  <td className="py-2">{s.full_name}<span className="block text-xs text-slate-500">{s.email}</span></td>
                  {s.shared ? (
                    <>
                      <td>{s.interview?.count ? `${s.interview.first} → ${s.interview.latest}` : "—"}</td>
                      <td>{s.cv?.count ? `${s.cv.first} → ${s.cv.latest}` : "—"}</td>
                      <td>{s.last_activity ? new Date(s.last_activity).toLocaleDateString("vi-VN") : "—"}</td>
                      <td><Link className="text-indigo-700 hover:underline" href={`/advisor/students/${s.id}`}>Xem & nhận xét</Link></td>
                    </>
                  ) : (
                    <td colSpan={4} className="text-slate-500">Sinh viên chưa đồng ý chia sẻ báo cáo</td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold">Đánh giá chất lượng phản hồi AI (LLM-as-Judge)</h2>
          <button className="btn-ghost" onClick={runEvals} disabled={busy}>{busy ? "Đang chấm..." : "Chấm các lượt chấm CV mới"}</button>
        </div>
        <p className="text-sm text-slate-600">Một model khác chấm lại phản hồi của AI theo 5 tiêu chí, đặc biệt là có bịa chi tiết không có trong CV hay không.</p>
        {evals && evals.count > 0 && (
          <>
            <div className="grid gap-2 sm:grid-cols-5">
              {Object.entries(evals.dimensions).map(([k, v]) => (
                <div key={k} className="rounded-lg bg-slate-50 p-2 text-center"><p className="text-xs text-slate-500">{DIM_LABEL[k] ?? k}</p><p className="font-bold tabular-nums">{v}</p></div>
              ))}
            </div>
            {evals.recent_issues.length > 0 && <Notice tone="warn" title="Vấn đề phát hiện gần đây">{evals.recent_issues.map((i, k) => <p key={k}>• {i}</p>)}</Notice>}
          </>
        )}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth roles={["advisor"]}>
      <AdvisorDashboard />
    </RequireAuth>
  );
}
