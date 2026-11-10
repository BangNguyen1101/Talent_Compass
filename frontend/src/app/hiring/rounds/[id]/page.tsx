"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, post, put } from "@/lib/api";
import { REC_LABEL } from "@/lib/roles";
import type { BiasIssue, Competency } from "@/lib/types";
import { BiasList, ErrorBox, Notice, RequireAuth } from "@/components/ui";

interface Question { question: string; competency: string; what_good_looks_like: string; red_flags?: string[] }
interface ScoreItem { competency: string; score: number | null; evidence: string }
interface QNote { index: number; asked: boolean; notes: string }
interface RoundView {
  id: string; name: string; status: string; focus_competencies: string[]; questions: Question[];
  candidate: { id: string; full_name: string }; jd: { title: string; level: string; competencies: Competency[] };
  probe_from_previous: string[];
  my_scorecard: { scores: ScoreItem[]; question_notes: QNote[]; raw_notes: string; recommendation: string; submitted: boolean; bias_flags: BiasIssue[] } | null;
}
interface Warnings { untested_competencies: string[]; unasked_questions: number[]; bias_flags: BiasIssue[] }

// Web Speech API (đọc chính tả trên trình duyệt, miễn phí)
interface SpeechResultEvent { resultIndex: number; results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }> }
interface Recognizer { lang: string; continuous: boolean; interimResults: boolean; start(): void; stop(): void; onresult: (e: SpeechResultEvent) => void; onend: () => void }
type RecognizerCtor = new () => Recognizer;

function useDictation(onText: (t: string) => void) {
  const [on, setOn] = useState(false);
  const rec = useRef<Recognizer | null>(null);
  const w = typeof window !== "undefined" ? (window as unknown as { SpeechRecognition?: RecognizerCtor; webkitSpeechRecognition?: RecognizerCtor }) : null;
  const Ctor = w?.SpeechRecognition ?? w?.webkitSpeechRecognition;

  function toggle() {
    if (!Ctor) return;
    if (on) {
      rec.current?.stop();
      return;
    }
    const r = new Ctor();
    r.lang = "vi-VN";
    r.continuous = true;
    r.interimResults = false;
    r.onresult = (e) => {
      for (let i = e.resultIndex; i < e.results.length; i++) if (e.results[i].isFinal) onText(e.results[i][0].transcript);
    };
    r.onend = () => setOn(false);
    rec.current = r;
    r.start();
    setOn(true);
  }
  return { supported: !!Ctor, on, toggle };
}

const RECS = ["strong_no_hire", "no_hire", "hire", "strong_hire"];

function Scorecard() {
  const { id } = useParams<{ id: string }>();
  const [r, setR] = useState<RoundView | null>(null);
  const [scores, setScores] = useState<ScoreItem[]>([]);
  const [notes, setNotes] = useState<QNote[]>([]);
  const [raw, setRaw] = useState("");
  const [recommendation, setRecommendation] = useState("");
  const [warnings, setWarnings] = useState<Warnings | null>(null);
  const [suggest, setSuggest] = useState<{ scores: { competency: string; suggested_score: number; evidence: string }[]; summary: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const dictation = useDictation((t) => setRaw((prev) => (prev ? `${prev} ${t}` : t)));

  const load = useCallback(() => {
    api<RoundView>(`/hiring/rounds/${id}`).then((v) => {
      setR(v);
      const sc = v.my_scorecard;
      setScores(v.focus_competencies.map((c) => sc?.scores.find((s) => s.competency === c) ?? { competency: c, score: null, evidence: "" }));
      setNotes(v.questions.map((_, i) => sc?.question_notes.find((n) => n.index === i) ?? { index: i, asked: false, notes: "" }));
      setRaw(sc?.raw_notes ?? "");
      setRecommendation(sc?.recommendation ?? "");
    }).catch((e) => setError(e.message));
  }, [id]);
  useEffect(load, [load]);

  async function save(submit: boolean) {
    if (submit && !confirm("Nộp scorecard? Sau khi nộp bạn không sửa được nữa.")) return;
    setBusy(submit ? "submit" : "save");
    setError(null);
    try {
      const res = await put<{ warnings: Warnings }>(`/hiring/rounds/${id}/scorecard`, {
        scores: scores.map((s) => ({ ...s, score: s.score || null })), question_notes: notes, raw_notes: raw, recommendation, submit,
      });
      setWarnings(res.warnings);
      setSavedAt(new Date().toLocaleTimeString("vi-VN"));
      if (submit) load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function structure() {
    setBusy("ai");
    setError(null);
    try {
      const res = await post<{ scores: { competency: string; suggested_score: number; evidence: string }[]; summary: string; bias_flags: BiasIssue[] }>(
        `/hiring/rounds/${id}/structure-notes`, { raw_notes: raw });
      setSuggest(res);
      if (res.bias_flags.length) setWarnings((w) => ({ untested_competencies: w?.untested_competencies ?? [], unasked_questions: w?.unasked_questions ?? [], bias_flags: res.bias_flags }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  function applySuggestions() {
    if (!suggest) return;
    setScores(scores.map((s) => {
      const g = suggest.scores.find((x) => x.competency.toLowerCase() === s.competency.toLowerCase());
      return g && g.suggested_score > 0 ? { ...s, score: s.score ?? g.suggested_score, evidence: s.evidence || g.evidence } : s;
    }));
    setSuggest(null);
  }

  if (!r) return error ? <ErrorBox message={error} /> : <p className="text-slate-500">Đang tải...</p>;
  const locked = !!r.my_scorecard?.submitted || r.status !== "open";
  const rubric = (name: string) => r.jd.competencies.find((c) => c.name.toLowerCase() === name.toLowerCase());

  return (
    <div className="space-y-6">
      <div>
        <Link href={`/hiring/candidates/${r.candidate.id}`} className="text-sm text-indigo-700 hover:underline">← {r.candidate.full_name}</Link>
        <h1 className="text-2xl font-bold">Scorecard · {r.name}</h1>
        <p className="text-sm text-slate-500">{r.jd.title} ({r.jd.level}) · Chấm độc lập, không trao đổi điểm với người khác trước khi nộp.</p>
      </div>
      {locked && <Notice tone="ok">{r.my_scorecard?.submitted ? "Bạn đã nộp scorecard này." : "Vòng phỏng vấn đã đóng."}</Notice>}
      {r.probe_from_previous.length > 0 && <Notice title="Điểm cần làm rõ từ vòng trước">{r.probe_from_previous.join("; ")}</Notice>}

      <div className="card space-y-4">
        <h2 className="font-semibold">Câu hỏi gợi ý</h2>
        {r.questions.map((q, i) => (
          <div key={i} className="space-y-2 rounded-lg border border-slate-200 p-3">
            <div className="flex items-start gap-2">
              <input type="checkbox" className="mt-1" disabled={locked} checked={notes[i]?.asked ?? false}
                onChange={(e) => setNotes(notes.map((n) => (n.index === i ? { ...n, asked: e.target.checked } : n)))} title="Đã hỏi" />
              <div>
                <p className="text-xs font-semibold uppercase text-indigo-700">{q.competency}</p>
                <p className="font-medium">{q.question}</p>
                <p className="text-xs text-emerald-700">Tốt: {q.what_good_looks_like}</p>
                {q.red_flags?.length ? <p className="text-xs text-red-600">Lưu ý: {q.red_flags.join("; ")}</p> : null}
              </div>
            </div>
            <textarea className="input min-h-16" disabled={locked} placeholder="Ghi chú câu trả lời của ứng viên" value={notes[i]?.notes ?? ""}
              onChange={(e) => setNotes(notes.map((n) => (n.index === i ? { ...n, notes: e.target.value, asked: true } : n)))} />
          </div>
        ))}
      </div>

      <div className="card space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold">Ghi chú tự do</h2>
          {!locked && (
            <div className="flex gap-2">
              {dictation.supported && <button type="button" className={dictation.on ? "btn" : "btn-ghost"} onClick={dictation.toggle}>{dictation.on ? "■ Dừng ghi âm" : "🎤 Đọc chính tả"}</button>}
              <button type="button" className="btn-ghost" disabled={!raw.trim() || !!busy} onClick={structure}>{busy === "ai" ? "AI đang xử lý..." : "AI chuyển ghi chú thành bằng chứng"}</button>
            </div>
          )}
        </div>
        {!dictation.supported && !locked && <p className="text-xs text-slate-500">Trình duyệt này chưa hỗ trợ đọc chính tả (dùng Chrome hoặc Edge).</p>}
        <textarea className="input min-h-28" disabled={locked} value={raw} onChange={(e) => setRaw(e.target.value)} placeholder="Ghi nhanh trong buổi phỏng vấn, hoặc bấm Đọc chính tả." />
        {suggest && (
          <Notice title="AI gợi ý điểm từ ghi chú (bạn quyết định điểm cuối)">
            <p className="mb-1">{suggest.summary}</p>
            {suggest.scores.map((s) => <p key={s.competency}>• {s.competency}: {s.suggested_score > 0 ? `${s.suggested_score}/5 — ${s.evidence}` : "chưa có bằng chứng trong ghi chú"}</p>)}
            <button className="btn-ghost mt-2" onClick={applySuggestions}>Điền vào các ô còn trống</button>
          </Notice>
        )}
      </div>

      <div className="card space-y-4">
        <h2 className="font-semibold">Chấm theo khung năng lực</h2>
        {scores.map((s, i) => {
          const comp = rubric(s.competency);
          return (
            <div key={s.competency} className="space-y-2 border-b border-slate-100 pb-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-medium">{s.competency} <span className="text-xs text-slate-500">(yêu cầu mức {comp?.required_level})</span></p>
                <div className="flex gap-1">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <button key={n} disabled={locked} title={comp?.rubric.find((x) => x.level === n)?.descriptor}
                      onClick={() => setScores(scores.map((x, j) => (j === i ? { ...x, score: x.score === n ? null : n } : x)))}
                      className={`h-8 w-8 rounded-lg border text-sm font-semibold ${s.score === n ? "border-indigo-600 bg-indigo-600 text-white" : "border-slate-300 bg-white text-slate-600"}`}>{n}</button>
                  ))}
                </div>
              </div>
              {s.score && <p className="text-xs text-slate-500">Mức {s.score}: {comp?.rubric.find((x) => x.level === s.score)?.descriptor}</p>}
              <input className="input" disabled={locked} placeholder="Bằng chứng cụ thể từ câu trả lời" value={s.evidence}
                onChange={(e) => setScores(scores.map((x, j) => (j === i ? { ...x, evidence: e.target.value } : x)))} />
            </div>
          );
        })}
        <div>
          <p className="label">Khuyến nghị của bạn</p>
          <div className="flex flex-wrap gap-2">
            {RECS.map((k) => (
              <label key={k} className={`cursor-pointer rounded-lg border px-3 py-1 text-sm ${recommendation === k ? "border-indigo-500 bg-indigo-50" : "border-slate-300"}`}>
                <input type="radio" className="mr-1" disabled={locked} checked={recommendation === k} onChange={() => setRecommendation(k)} />{REC_LABEL[k]}
              </label>
            ))}
          </div>
        </div>
      </div>

      {warnings && (
        <div className="space-y-2">
          {warnings.untested_competencies.length > 0 && <Notice tone="warn" title="Tiêu chí chưa chấm">{warnings.untested_competencies.join(", ")}</Notice>}
          {warnings.unasked_questions.length > 0 && <Notice tone="warn" title="Câu hỏi chưa hỏi / chưa ghi chú">Câu {warnings.unasked_questions.map((i) => i + 1).join(", ")}</Notice>}
          <BiasList issues={warnings.bias_flags} />
        </div>
      )}
      <ErrorBox message={error} />
      {!locked && (
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn-ghost" disabled={!!busy} onClick={() => save(false)}>{busy === "save" ? "Đang lưu..." : "Lưu nháp & kiểm tra"}</button>
          <button className="btn" disabled={!!busy || !recommendation} onClick={() => save(true)}>Nộp scorecard</button>
          {savedAt && <span className="text-xs text-slate-500">Đã lưu lúc {savedAt}</span>}
        </div>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth roles={["hr", "hiring_lead", "interviewer", "manager"]}>
      <Scorecard />
    </RequireAuth>
  );
}
