"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { ROUND_TYPES } from "@/lib/roles";
import type { Interview } from "@/lib/types";
import { AiNotice, Csat, ErrorBox, RequireAuth, ScoreBar } from "@/components/ui";
import { QuestionDetail, QuestionTypeTag } from "@/components/QuestionDetail";

function InterviewRoom() {
  const { id } = useParams<{ id: string }>();
  const [s, setS] = useState<Interview | null>(null);
  const [current, setCurrent] = useState(0);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Interview>(`/interviews/${id}`)
      .then((data) => {
        setS(data);
        const next = data.turns.findIndex((t) => !t.answer);
        setCurrent(next === -1 ? 0 : next);
      })
      .catch((e) => setError(e.message));
  }, [id]);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const updated = await post<Interview>(`/interviews/${id}/turns/${current}/answer`, { answer: draft });
      setS(updated);
      setDraft("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function finish() {
    setBusy(true);
    setError(null);
    try {
      setS(await post<Interview>(`/interviews/${id}/finish`));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!s) return error ? <ErrorBox message={error} /> : <p className="text-slate-500">Đang tải...</p>;
  const turn = s.turns[current];
  const done = s.status === "completed";
  const answered = s.turns.filter((t) => t.answer).length;
  const mainNo = (idx: number) => s.turns.slice(0, idx + 1).filter((t) => t.parent === null).length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Phỏng vấn thử</h1>
          <p className="text-sm text-slate-500">Vòng: {ROUND_TYPES[s.round_type] ?? s.round_type}</p>
        </div>
        <div className="flex flex-wrap items-center gap-1">
          {s.turns.map((t, i) => (
            <button
              key={i}
              onClick={() => setCurrent(i)}
              title={t.parent !== null ? "Câu hỏi đào sâu" : undefined}
              className={`rounded-full text-sm ${t.parent !== null ? "h-6 w-6 text-xs" : "h-8 w-8"} ${i === current ? "bg-indigo-600 text-white" : t.answer ? "bg-emerald-100 text-emerald-800" : "bg-slate-200 text-slate-600"}`}
            >
              {t.parent !== null ? "↳" : mainNo(i)}
            </button>
          ))}
        </div>
      </div>

      {done && s.summary && (
        <div className="card space-y-4 border-indigo-200">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Tổng kết buổi phỏng vấn</h2>
            {s.average_score != null && <span className="text-xl font-bold tabular-nums text-indigo-700">{s.average_score}/5</span>}
          </div>
          <p className="text-sm">{s.summary.overall}</p>
          {s.summary.per_competency.map((c) => (
            <div key={c.competency} className="space-y-1">
              <div className="flex justify-between text-sm"><span className="font-medium">{c.competency}</span><span>{c.average_score.toFixed(1)}/5</span></div>
              <ScoreBar value={c.average_score} />
              <p className="text-xs text-slate-600">{c.comment}</p>
            </div>
          ))}
          <div>
            <p className="text-sm font-medium">Bước tiếp theo</p>
            <ul className="list-disc pl-5 text-sm">{s.summary.next_steps.map((x) => <li key={x}>{x}</li>)}</ul>
          </div>
          <AiNotice extra="Đây là buổi luyện tập; AI không đảm bảo kết quả tuyển dụng thật." />
        </div>
      )}
      {done && <Csat targetType="interview" targetId={s.id} label="Buổi phỏng vấn thử này hữu ích với bạn đến mức nào?" />}

      <div className="card space-y-4">
        <div>
          <p className="text-xs font-semibold uppercase text-indigo-700">
            {turn.parent !== null ? "Câu hỏi đào sâu" : `Câu ${mainNo(current)}`} · {turn.competency}
            <QuestionTypeTag type={turn.type} />
          </p>
          <p className="mt-1 text-lg font-medium">{turn.question}</p>
        </div>

        {turn.answer ? (
          <div className="space-y-3">
            <div className="whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-sm">{turn.answer}</div>
            <div className="space-y-1">
              <p className="text-sm font-medium">Điểm: {turn.score}/5</p>
              <ScoreBar value={turn.score ?? 0} />
            </div>
            <p className="text-sm">{turn.feedback}</p>
            <p className="border-l-2 border-indigo-400 pl-2 text-sm text-slate-700"><b>Gợi ý:</b> {turn.better_answer_hint}</p>
            {turn.follow_up_question && current + 1 < s.turns.length && s.turns[current + 1].parent !== null && (
              <button className="btn-ghost" onClick={() => setCurrent(current + 1)}>Trả lời câu hỏi đào sâu →</button>
            )}
            <details className="text-sm text-slate-600">
              <summary className="cursor-pointer">Câu trả lời tốt cần có gì?</summary>
              <p className="mt-1">{turn.what_good_looks_like}</p>
              <QuestionDetail guide={turn.scoring_guide} />
            </details>
          </div>
        ) : done ? (
          <p className="text-sm text-slate-500">Bạn đã bỏ qua câu này.</p>
        ) : (
          <div className="space-y-3">
            <textarea className="input min-h-40" placeholder="Trả lời theo cấu trúc STAR: Tình huống → Nhiệm vụ → Hành động → Kết quả" value={draft} onChange={(e) => setDraft(e.target.value)} />
            <button className="btn" onClick={submit} disabled={busy || !draft.trim()}>{busy ? "AI đang nhận xét..." : "Gửi câu trả lời"}</button>
          </div>
        )}
      </div>

      <ErrorBox message={error} />
      <div className="flex flex-wrap gap-2">
        {current < s.turns.length - 1 && <button className="btn-ghost" onClick={() => setCurrent(current + 1)}>Câu tiếp theo →</button>}
        {!done && (
          <button className="btn" onClick={finish} disabled={busy || answered === 0}>Kết thúc & xem tổng kết ({answered}/{s.turns.length})</button>
        )}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <InterviewRoom />
    </RequireAuth>
  );
}
