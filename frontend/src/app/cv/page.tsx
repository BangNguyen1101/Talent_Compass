"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import type { ATSResult, Assessment, CV, Job } from "@/lib/types";
import { AiNotice, Csat, ErrorBox, Notice, RequireAuth, ScoreBar } from "@/components/ui";

function ATSPanel({ ats }: { ats: ATSResult }) {
  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Tương thích ATS (lọc CV tự động)</h3>
        <span className="text-xl font-bold tabular-nums text-indigo-700">{ats.score}/100</span>
      </div>
      <div className="grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <p className="font-medium text-emerald-700">Từ khóa JD có trong CV</p>
          <p className="text-slate-600">{ats.matched_keywords.join(", ") || "—"}</p>
        </div>
        <div>
          <p className="font-medium text-amber-700">Từ khóa JD chưa có</p>
          <p className="text-slate-600">{ats.missing_keywords.join(", ") || "—"}</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 text-xs">
        {Object.entries(ats.sections).map(([k, ok]) => (
          <span key={k} className={`rounded px-2 py-0.5 ${ok ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>{ok ? "✓" : "✗"} {k}</span>
        ))}
      </div>
      {ats.tips.length > 0 && <ul className="list-disc pl-5 text-sm text-slate-700">{ats.tips.map((t) => <li key={t}>{t}</li>)}</ul>}
    </div>
  );
}

function AssessmentView({ a, job }: { a: Assessment; job?: Job }) {
  const req = (name: string) => job?.competencies.find((c) => c.name.toLowerCase() === name.toLowerCase())?.required_level;
  const r = a.result;
  return (
    <div className="space-y-4">
      <div className="card flex flex-wrap items-center gap-6">
        <div className="text-center">
          <p className="text-4xl font-bold tabular-nums text-indigo-700">{a.overall_score}</p>
          <p className="text-xs text-slate-500">mức phù hợp năng lực / 100</p>
        </div>
        <p className="flex-1 text-sm text-slate-700">{r.overall_comment}</p>
      </div>
      {r.disclaimer && <Notice>{r.disclaimer}</Notice>}
      <ATSPanel ats={a.ats} />

      <div className="card space-y-4">
        <h3 className="font-semibold">Theo từng năng lực</h3>
        {r.competency_scores.map((s) => (
          <div key={s.competency} className="space-y-1">
            <div className="flex justify-between text-sm">
              <span className="font-medium">{s.competency}</span>
              <span className="text-slate-500">{s.score}/5 {req(s.competency) !== undefined && `(yêu cầu ${req(s.competency)})`}</span>
            </div>
            <ScoreBar value={s.score} required={req(s.competency)} />
            <p className="text-xs text-slate-600"><b>Bằng chứng:</b> {s.evidence}</p>
            {s.gap && <p className="text-xs text-amber-700"><b>Còn thiếu:</b> {s.gap}</p>}
          </div>
        ))}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="card">
          <h3 className="mb-2 font-semibold text-emerald-700">Điểm mạnh</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm">{r.strengths.map((x) => <li key={x}>{x}</li>)}</ul>
        </div>
        <div className="card">
          <h3 className="mb-2 font-semibold text-amber-700">Cần cải thiện</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm">{r.gaps.map((x) => <li key={x}>{x}</li>)}</ul>
        </div>
      </div>

      <div className="card space-y-3">
        <h3 className="font-semibold">Gợi ý sửa CV</h3>
        {!!r.guardrail_flagged && (
          <Notice tone="warn" title="Kiểm tra liêm chính">
            {r.guardrail_flagged} gợi ý có chi tiết không tìm thấy trong CV của bạn. Số liệu đã được thay bằng chỗ trống; chỉ ghi vào CV những gì là sự thật.
          </Notice>
        )}
        {r.suggestions.map((s, i) => (
          <div key={i} className="rounded-lg bg-slate-50 p-3 text-sm">
            <p className="font-medium">{s.section}: {s.issue}</p>
            <p className="text-slate-600">{s.suggestion}</p>
            {s.example_rewrite && <p className="mt-1 border-l-2 border-indigo-400 pl-2 italic text-slate-700">{s.example_rewrite}</p>}
            {s.guardrail_note && <p className="mt-1 text-xs text-amber-700">⚠ {s.guardrail_note}</p>}
          </div>
        ))}
      </div>
      <Csat targetType="cv_assessment" targetId={a.id} />
      <AiNotice />
    </div>
  );
}

interface CompareRow extends ATSResult { jd_id: string; title: string; level: string }

function Compare({ cvId, jobs }: { cvId: string; jobs: Job[] }) {
  const [selected, setSelected] = useState<string[]>([]);
  const [data, setData] = useState<{ results: CompareRow[]; common_gaps: { keyword: string; positions: number }[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setError(null);
    try {
      setData(await post(`/cvs/${cvId}/ats-compare`, { jd_ids: selected }));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="card space-y-3">
      <h2 className="font-semibold">So sánh CV với nhiều vị trí (ATS)</h2>
      <p className="text-sm text-slate-600">Chọn tối đa 10 JD để xem CV hợp vị trí nào nhất và kỹ năng nào thiếu ở nhiều vị trí. Không tốn lượt AI.</p>
      <div className="flex flex-wrap gap-2">
        {jobs.map((j) => (
          <label key={j.id} className={`cursor-pointer rounded-lg border px-3 py-1 text-sm ${selected.includes(j.id) ? "border-indigo-500 bg-indigo-50" : "border-slate-300"}`}>
            <input type="checkbox" className="mr-1" checked={selected.includes(j.id)}
              onChange={(e) => setSelected(e.target.checked ? [...selected, j.id].slice(0, 10) : selected.filter((x) => x !== j.id))} />
            {j.title}
          </label>
        ))}
      </div>
      <button className="btn-ghost" disabled={!selected.length} onClick={run}>So sánh</button>
      <ErrorBox message={error} />
      {data && (
        <div className="space-y-3">
          {data.results.map((r) => (
            <div key={r.jd_id} className="space-y-1">
              <div className="flex justify-between text-sm"><span className="font-medium">{r.title} ({r.level})</span><span className="tabular-nums">{r.score}/100</span></div>
              <ScoreBar value={r.score} max={100} />
              {r.missing_keywords.length > 0 && <p className="text-xs text-slate-500">Thiếu: {r.missing_keywords.slice(0, 8).join(", ")}</p>}
            </div>
          ))}
          {data.common_gaps.length > 0 && (
            <Notice title="Kỹ năng nên ưu tiên học (thiếu ở nhiều vị trí)">
              {data.common_gaps.map((g) => `${g.keyword} (${g.positions})`).join(", ")}
            </Notice>
          )}
        </div>
      )}
    </div>
  );
}

function CVPage() {
  const params = useSearchParams();
  const [cvs, setCvs] = useState<CV[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [cvId, setCvId] = useState("");
  const [jdId, setJdId] = useState(params.get("jd") ?? "");
  const [result, setResult] = useState<Assessment | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api<CV[]>("/cvs"), api<Job[]>("/jobs")])
      .then(([c, j]) => {
        setCvs(c);
        setJobs(j);
        if (c[0]) setCvId(c[0].id);
        setJdId((cur) => cur || j[0]?.id || "");
      })
      .catch((e) => setError(e.message));
  }, []);

  async function upload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy("upload");
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const cv = await api<CV>("/cvs", { method: "POST", body: fd });
      setCvs([cv, ...cvs]);
      setCvId(cv.id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
      e.target.value = "";
    }
  }

  async function assess() {
    setBusy("assess");
    setError(null);
    setResult(null);
    try {
      setResult(await post<Assessment>(`/cvs/${cvId}/assess`, { jd_id: jdId }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Chấm CV theo JD</h1>
        <p className="text-sm text-slate-600">Email, số điện thoại, ngày sinh, địa chỉ trong CV được tự động che trước khi gửi cho AI. Chỉ bạn (và cố vấn nếu bạn đồng ý) xem được kết quả.</p>
      </div>

      <div className="card grid gap-4 sm:grid-cols-2">
        <div>
          <label className="label">1. CV của bạn</label>
          <select className="input" value={cvId} onChange={(e) => setCvId(e.target.value)}>
            {cvs.length === 0 && <option value="">Chưa có CV</option>}
            {cvs.map((c) => <option key={c.id} value={c.id}>{c.filename} · {new Date(c.created_at).toLocaleDateString("vi-VN")}</option>)}
          </select>
          <label className="btn-ghost mt-2 cursor-pointer">
            {busy === "upload" ? "Đang đọc CV..." : "Tải CV mới (PDF, DOCX, TXT)"}
            <input type="file" accept=".pdf,.docx,.txt" className="hidden" onChange={upload} disabled={!!busy} />
          </label>
        </div>
        <div>
          <label className="label">2. Vị trí ứng tuyển (JD)</label>
          <select className="input" value={jdId} onChange={(e) => setJdId(e.target.value)}>
            {jobs.length === 0 && <option value="">Chưa có việc làm nào được đăng</option>}
            {jobs.map((j) => <option key={j.id} value={j.id}>{j.title} ({j.level}){j.company ? ` · ${j.company}` : ""}</option>)}
          </select>
        </div>
        <div className="sm:col-span-2">
          <button className="btn" onClick={assess} disabled={!cvId || !jdId || !!busy}>
            {busy === "assess" ? "AI đang chấm (khoảng 20-40 giây)..." : "3. Chấm CV"}
          </button>
        </div>
      </div>

      <ErrorBox message={error} />
      {result && <AssessmentView a={result} job={jobs.find((j) => j.id === result.jd_id)} />}
      {cvId && jobs.length > 1 && <Compare cvId={cvId} jobs={jobs} />}
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <Suspense>
        <CVPage />
      </Suspense>
    </RequireAuth>
  );
}
