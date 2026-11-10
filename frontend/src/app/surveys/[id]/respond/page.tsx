"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import type { Survey } from "@/lib/types";
import { ErrorBox, Notice, RequireAuth } from "@/components/ui";

const LIKERT = ["Rất không đồng ý", "Không đồng ý", "Trung lập", "Đồng ý", "Rất đồng ý"];

function Respond() {
  const { id } = useParams<{ id: string }>();
  const [s, setS] = useState<Survey | null>(null);
  const [answers, setAnswers] = useState<Record<string, number | string>>({});
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Survey>(`/surveys/${id}`).then(setS).catch((e) => setError(e.message));
  }, [id]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await post<{ message: string }>(`/surveys/${id}/respond`, { answers });
      setDone(r.message);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!s) return error ? <ErrorBox message={error} /> : <p className="text-slate-500">Đang tải...</p>;
  if (done || s.answered) return <Notice tone="ok" title="Cảm ơn bạn!">{done ?? "Bạn đã trả lời khảo sát này."}</Notice>;

  return (
    <form onSubmit={submit} className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{s.title}</h1>
        {s.description && <p className="text-slate-600">{s.description}</p>}
      </div>
      <Notice>
        <b>Ẩn danh:</b> hệ thống chỉ ghi nhận bạn đã tham gia, không liên kết với nội dung trả lời. Kết quả chỉ hiển thị theo nhóm từ 5 người trở lên.
        Tránh viết tên người hoặc thông tin nhận diện bản thân trong câu trả lời mở.
      </Notice>
      {s.questions.map((q, i) => (
        <div key={q.id} className="card space-y-2">
          <p className="font-medium">{i + 1}. {q.text}</p>
          {q.type === "likert" ? (
            <div className="grid gap-2 sm:grid-cols-5">
              {LIKERT.map((label, k) => (
                <label key={k} className={`cursor-pointer rounded-lg border p-2 text-center text-sm ${answers[q.id] === k + 1 ? "border-indigo-500 bg-indigo-50 font-medium" : "border-slate-300"}`}>
                  <input type="radio" className="sr-only" name={q.id} checked={answers[q.id] === k + 1} onChange={() => setAnswers({ ...answers, [q.id]: k + 1 })} />
                  <span className="block text-lg">{k + 1}</span>{label}
                </label>
              ))}
            </div>
          ) : (
            <textarea className="input min-h-24" value={(answers[q.id] as string) ?? ""} onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })} />
          )}
        </div>
      ))}
      <ErrorBox message={error} />
      <button className="btn" disabled={busy || Object.keys(answers).length === 0}>{busy ? "Đang gửi..." : "Gửi câu trả lời"}</button>
    </form>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <Respond />
    </RequireAuth>
  );
}
