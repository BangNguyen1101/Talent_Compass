"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import type { Assessment, CV, Job } from "@/lib/types";
import { AiNotice, ErrorBox, RequireAuth, ScoreBar } from "@/components/ui";

function AssessmentView({ a, job }: { a: Assessment; job?: Job }) {
  const req = (name: string) => job?.competencies.find((c) => c.name.toLowerCase() === name.toLowerCase())?.required_level;
  const r = a.result;
  return (
    <div className="space-y-4">
      <div className="card flex flex-wrap items-center gap-6">
        <div className="text-center">
          <p className="text-4xl font-bold text-indigo-700">{a.overall_score}</p>
          <p className="text-xs text-slate-500">mức phù hợp / 100</p>
        </div>
        <p className="flex-1 text-sm text-slate-700">{r.overall_comment}</p>
      </div>

      <div className="card space-y-4">
        <h3 className="font-semibold">Theo từng năng lực</h3>
        {r.competency_scores.map((s) => (
          <div key={s.competency} className="space-y-1">
            <div className="flex justify-between text-sm">
              <span className="font-medium">{s.competency}</span>
              <span className="text-slate-500">
                {s.score}/5 {req(s.competency) !== undefined && `(yêu cầu ${req(s.competency)})`}
              </span>
            </div>
            <ScoreBar value={s.score} required={req(s.competency)} />
            <p className="text-xs text-slate-600">
              <b>Bằng chứng:</b> {s.evidence}
            </p>
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
        {r.suggestions.map((s, i) => (
          <div key={i} className="rounded-lg bg-slate-50 p-3 text-sm">
            <p className="font-medium">{s.section}: {s.issue}</p>
            <p className="text-slate-600">{s.suggestion}</p>
            {s.example_rewrite && <p className="mt-1 border-l-2 border-indigo-400 pl-2 italic text-slate-700">{s.example_rewrite}</p>}
          </div>
        ))}
      </div>
      <AiNotice />
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
        <p className="text-sm text-slate-600">
          Thông tin liên hệ, ngày sinh, địa chỉ trong CV được tự động che trước khi gửi cho AI.
        </p>
      </div>

      <div className="card grid gap-4 sm:grid-cols-2">
        <div>
          <label className="label">1. CV của bạn</label>
          <select className="input" value={cvId} onChange={(e) => setCvId(e.target.value)}>
            {cvs.length === 0 && <option value="">Chưa có CV</option>}
            {cvs.map((c) => (
              <option key={c.id} value={c.id}>
                {c.filename} · {new Date(c.created_at).toLocaleDateString("vi-VN")}
              </option>
            ))}
          </select>
          <label className="btn-ghost mt-2 cursor-pointer">
            {busy === "upload" ? "Đang đọc CV..." : "Tải CV mới (PDF, DOCX, TXT)"}
            <input type="file" accept=".pdf,.docx,.txt" className="hidden" onChange={upload} disabled={!!busy} />
          </label>
        </div>
        <div>
          <label className="label">2. Vị trí ứng tuyển (JD)</label>
          <select className="input" value={jdId} onChange={(e) => setJdId(e.target.value)}>
            {jobs.length === 0 && <option value="">Chưa có JD, hãy tạo ở mục JD & năng lực</option>}
            {jobs.map((j) => (
              <option key={j.id} value={j.id}>
                {j.title} ({j.level})
              </option>
            ))}
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
