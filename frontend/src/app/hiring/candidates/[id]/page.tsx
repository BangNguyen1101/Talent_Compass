"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { REC_LABEL } from "@/lib/roles";
import type { Competency, Member } from "@/lib/types";
import { AiNotice, Badge, Csat, ErrorBox, Notice, RequireAuth, ScoreBar } from "@/components/ui";

interface CompAgg {
  competency: string; required_level: number | null; n: number; mean: number | null; min: number | null; max: number | null;
  disagreement: boolean; meets_requirement: boolean | null; entries: { interviewer: string; score: number; evidence: string }[];
}
interface Round {
  id: string; round_no: number; name: string; focus_competencies: string[]; status: string;
  interviewers: { id: string; name: string; submitted: boolean }[];
  aggregate?: { competencies: CompAgg[]; untested: string[]; disagreements: string[]; fit_score: number | null;
    recommendation_counts: Record<string, number>; recommendation_split: boolean; missing_scorecards: string[]; scorecards_submitted: number } | null;
  recommendation?: { recommendation: string; confidence: string; rationale: string; strengths: string[]; concerns: string[]; probe_next_round: string[] } | null;
  my_scorecard: { submitted: boolean } | null;
}
interface Candidate {
  id: string; full_name: string; stage: string; is_lead: boolean; email?: string; cv_text?: string;
  jd: { id: string; title: string; level: string; competencies: Competency[] };
  rounds: Round[];
  profile_memory?: { round_no: number; name: string; fit_score: number | null; summary: string; probe_next_round: string[] }[];
  decisions?: { decision: string; rationale: string; committee: string[]; followed_ai: boolean | null; by: string; at: string }[];
}

const DECISION: Record<string, string> = { hire: "Tuyển", reject: "Không tuyển", hold: "Tạm hoãn / thêm vòng" };

function RoundResult({ r }: { r: Round }) {
  const a = r.aggregate!;
  const rec = r.recommendation;
  return (
    <div className="space-y-3">
      {a.missing_scorecards.length > 0 && <Notice tone="warn">Chưa nộp scorecard: {a.missing_scorecards.join(", ")}</Notice>}
      {a.untested.length > 0 && <Notice tone="warn" title="Tiêu chí chưa được đánh giá">{a.untested.join(", ")}</Notice>}
      {a.disagreements.length > 0 && <Notice tone="danger" title="Bất đồng giữa người phỏng vấn (chênh ≥2 điểm)">{a.disagreements.join(", ")}. Nên thảo luận trước khi quyết định.</Notice>}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b text-left text-slate-500"><th className="py-2">Năng lực</th><th>Yêu cầu</th><th>TB</th><th className="w-40">Phân bố</th><th>Từng người chấm</th></tr></thead>
          <tbody>
            {a.competencies.map((c) => (
              <tr key={c.competency} className={`border-b border-slate-100 align-top tabular-nums ${c.disagreement ? "bg-red-50" : ""}`}>
                <td className="py-2 font-medium">{c.competency}</td>
                <td>{c.required_level ?? "—"}</td>
                <td>{c.mean ?? "—"}</td>
                <td className="pr-3 pt-3">{c.mean != null && <ScoreBar value={c.mean} required={c.required_level} />}</td>
                <td className="space-y-1 py-2">
                  {c.entries.map((e, i) => <p key={i}><b>{e.interviewer}</b>: {e.score} <span className="text-slate-500">— {e.evidence || "(không ghi bằng chứng)"}</span></p>)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-sm">
        Khuyến nghị từng người:{" "}
        {Object.entries(a.recommendation_counts).filter(([, n]) => n).map(([k, n]) => `${REC_LABEL[k]} (${n})`).join(", ")}
        {a.fit_score != null && <> · Mức phù hợp tổng hợp: <b>{a.fit_score}/100</b></>}
      </p>
      {rec && (
        <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-4 text-sm">
          <p className="font-semibold">AI đề xuất: {REC_LABEL[rec.recommendation] ?? rec.recommendation} <span className="font-normal text-slate-600">(tin cậy: {rec.confidence})</span></p>
          <p className="mt-1">{rec.rationale}</p>
          {rec.strengths.length > 0 && <p className="mt-1 text-emerald-700">Điểm mạnh: {rec.strengths.join("; ")}</p>}
          {rec.concerns.length > 0 && <p className="text-amber-700">Điểm đáng lo: {rec.concerns.join("; ")}</p>}
          {rec.probe_next_round.length > 0 && <p className="text-slate-700">Cần làm rõ ở vòng sau: {rec.probe_next_round.join("; ")}</p>}
          <div className="mt-2"><AiNotice extra="Hội đồng tuyển dụng ra quyết định cuối." /></div>
        </div>
      )}
      {rec && <Csat targetType="hiring_recommendation" targetId={r.id} label="Bản tổng hợp này giúp hội đồng ra quyết định tốt hơn không?" />}
    </div>
  );
}

function NewRound({ c, onDone }: { c: Candidate; onDone: () => void }) {
  const [members, setMembers] = useState<Member[]>([]);
  const [form, setForm] = useState({ name: `Vòng ${c.rounds.length + 1}`, focus: c.jd.competencies.map((x) => x.name), interviewers: [] as string[], count: 6 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Member[]>("/org/members").then((m) => setMembers(m.filter((x) => x.is_active && ["interviewer", "hiring_lead", "hr", "manager"].includes(x.role)))).catch(() => {});
  }, []);

  const toggle = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await post(`/hiring/candidates/${c.id}/rounds`, { name: form.name, focus_competencies: form.focus, interviewer_ids: form.interviewers, question_count: form.count });
      onDone();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const probe = c.profile_memory?.at(-1)?.probe_next_round ?? [];
  return (
    <form onSubmit={create} className="card space-y-3">
      <h2 className="font-semibold">Tạo vòng phỏng vấn mới</h2>
      {probe.length > 0 && <Notice title="Từ vòng trước, cần làm rõ">{probe.join("; ")}</Notice>}
      <div className="grid gap-3 sm:grid-cols-3">
        <input className="input sm:col-span-2" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <input className="input" type="number" min={1} max={12} value={form.count} onChange={(e) => setForm({ ...form, count: Number(e.target.value) })} title="Số câu hỏi" />
      </div>
      <div>
        <p className="label">Năng lực cần đánh giá ở vòng này</p>
        <div className="flex flex-wrap gap-2">
          {c.jd.competencies.map((x) => (
            <label key={x.name} className={`cursor-pointer rounded-lg border px-3 py-1 text-sm ${form.focus.includes(x.name) ? "border-indigo-500 bg-indigo-50" : "border-slate-300"}`}>
              <input type="checkbox" className="mr-1" checked={form.focus.includes(x.name)} onChange={() => setForm({ ...form, focus: toggle(form.focus, x.name) })} />{x.name}
            </label>
          ))}
        </div>
      </div>
      <div>
        <p className="label">Người phỏng vấn (nên ≥2 người để giảm thiên vị cá nhân)</p>
        <div className="flex flex-wrap gap-2">
          {members.map((m) => (
            <label key={m.id} className={`cursor-pointer rounded-lg border px-3 py-1 text-sm ${form.interviewers.includes(m.id) ? "border-indigo-500 bg-indigo-50" : "border-slate-300"}`}>
              <input type="checkbox" className="mr-1" checked={form.interviewers.includes(m.id)} onChange={() => setForm({ ...form, interviewers: toggle(form.interviewers, m.id) })} />{m.full_name}
            </label>
          ))}
        </div>
      </div>
      <ErrorBox message={error} />
      <button className="btn" disabled={busy || !form.interviewers.length || !form.focus.length}>{busy ? "Đang chuẩn bị câu hỏi..." : "Tạo vòng"}</button>
    </form>
  );
}

function CandidatePage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [c, setC] = useState<Candidate | null>(null);
  const [decision, setDecision] = useState({ decision: "hire", rationale: "", committee: "" });
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<Candidate>(`/hiring/candidates/${id}`).then(setC).catch((e) => setError(e.message));
  }, [id]);
  useEffect(load, [load]);

  async function act(name: string, fn: () => Promise<unknown>) {
    setBusy(name);
    setError(null);
    try {
      await fn();
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (!c) return error ? <ErrorBox message={error} /> : <p className="text-slate-500">Đang tải...</p>;
  const hasClosed = c.rounds.some((r) => r.status === "closed");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{c.full_name}</h1>
        <p className="text-sm text-slate-500">{c.jd.title} ({c.jd.level}){c.email && ` · ${c.email}`}</p>
      </div>
      <ErrorBox message={error} />

      {c.is_lead && c.cv_text && (
        <details className="card text-sm"><summary className="cursor-pointer font-medium">CV ứng viên (đã che thông tin liên hệ)</summary><p className="mt-2 whitespace-pre-wrap text-slate-700">{c.cv_text}</p></details>
      )}

      {c.rounds.map((r) => (
        <div key={r.id} className="card space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-semibold">{r.name}</h2>
            <div className="flex flex-wrap items-center gap-2">
              <Badge cls={r.status === "open" ? "bg-indigo-100 text-indigo-800" : "bg-slate-200 text-slate-700"}>{r.status === "open" ? "Đang mở" : "Đã đóng"}</Badge>
              {r.status === "open" && r.my_scorecard?.submitted !== true && r.interviewers.some((i) => i.id === user!.id) && (
                <Link href={`/hiring/rounds/${r.id}`} className="btn px-3 py-1">Mở scorecard của tôi</Link>
              )}
              {c.is_lead && r.status === "open" && (
                <button className="btn-ghost px-3 py-1" disabled={!!busy} onClick={() => act(r.id, () => post(`/hiring/rounds/${r.id}/close`))}>
                  {busy === r.id ? "Đang tổng hợp..." : "Đóng vòng & tổng hợp"}
                </button>
              )}
            </div>
          </div>
          <p className="text-sm text-slate-600">Năng lực: {r.focus_competencies.join(", ")}</p>
          <p className="text-sm">
            Người phỏng vấn:{" "}
            {r.interviewers.map((i) => <span key={i.id} className="mr-2">{i.name} {i.submitted ? "✓" : "…"}</span>)}
          </p>
          {c.is_lead && r.aggregate && <RoundResult r={r} />}
        </div>
      ))}

      {c.is_lead && !["hired", "rejected"].includes(c.stage) && <NewRound c={c} onDone={load} />}

      {c.is_lead && (
        <div className="card space-y-3">
          <h2 className="font-semibold">Quyết định của hội đồng tuyển dụng</h2>
          {!hasClosed ? (
            <p className="text-sm text-slate-500">Cần đóng ít nhất một vòng phỏng vấn trước khi quyết định.</p>
          ) : (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
                {Object.entries(DECISION).map(([k, v]) => (
                  <label key={k} className={`cursor-pointer rounded-lg border px-3 py-1 text-sm ${decision.decision === k ? "border-indigo-500 bg-indigo-50" : "border-slate-300"}`}>
                    <input type="radio" className="mr-1" checked={decision.decision === k} onChange={() => setDecision({ ...decision, decision: k })} />{v}
                  </label>
                ))}
              </div>
              <textarea className="input min-h-20" placeholder="Lý do quyết định, dựa trên bằng chứng liên quan công việc (bắt buộc)" value={decision.rationale} onChange={(e) => setDecision({ ...decision, rationale: e.target.value })} />
              <input className="input" placeholder="Thành viên hội đồng (cách nhau bằng dấu phẩy)" value={decision.committee} onChange={(e) => setDecision({ ...decision, committee: e.target.value })} />
              <button className="btn" disabled={!!busy || decision.rationale.trim().length < 10}
                onClick={() => act("decide", () => post(`/hiring/candidates/${c.id}/decision`, {
                  decision: decision.decision, rationale: decision.rationale,
                  committee: decision.committee.split(",").map((x) => x.trim()).filter(Boolean),
                }))}>
                Ghi nhận quyết định
              </button>
            </div>
          )}
          {c.decisions?.map((d, i) => (
            <div key={i} className="rounded-lg bg-slate-50 p-3 text-sm">
              <p><b>{DECISION[d.decision]}</b> · {d.by} · {new Date(d.at).toLocaleString("vi-VN")}
                {d.followed_ai !== null && <span className="text-slate-500"> · {d.followed_ai ? "trùng" : "khác"} đề xuất của AI</span>}</p>
              <p className="text-slate-700">{d.rationale}</p>
              {d.committee.length > 0 && <p className="text-xs text-slate-500">Hội đồng: {d.committee.join(", ")}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth roles={["hr", "hiring_lead", "interviewer"]}>
      <CandidatePage />
    </RequireAuth>
  );
}
