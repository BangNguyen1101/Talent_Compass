"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, patch, post, put } from "@/lib/api";
import type { GroupStats, Insight, Survey } from "@/lib/types";
import { SurveyEditor, type SurveyInput } from "@/components/SurveyEditor";
import { DepartmentTable, OverallStats, type Comparison } from "@/components/SurveyStats";
import { AiNotice, Badge, Csat, ErrorBox, Notice, RequireAuth, Stat } from "@/components/ui";

interface Dashboard extends Survey {
  participation: { responses: number; members: number; rate: number };
  analysis: {
    stats: { min_group_size: number; total_responses: number; overall: GroupStats; departments: Record<string, GroupStats> };
    topics: [string, number][]; persistent_topics: string[]; comparison: Comparison | null; previous_survey: string | null;
    practices: string[]; warnings: string[];
  } | null;
  insights: Insight[];
  topic_memory: { id: number; topic: string; occurrences: number; status: string; history: { period: string; count: number; negative: number }[] }[];
}

const KIND: Record<Insight["kind"], { label: string; cls: string }> = {
  risk: { label: "Rủi ro", cls: "bg-red-100 text-red-700" },
  theme: { label: "Chủ đề", cls: "bg-indigo-100 text-indigo-800" },
  strength: { label: "Điểm mạnh", cls: "bg-emerald-100 text-emerald-800" },
};
const PRIORITY: Record<string, string> = { high: "Ưu tiên cao", medium: "Trung bình", low: "Thấp" };

function InsightCard({ sid, ins, onChange }: { sid: string; ins: Insight; onChange: () => void }) {
  const [selected, setSelected] = useState<string[]>(ins.selected_actions.length ? ins.selected_actions : []);
  const [note, setNote] = useState(ins.hr_note);
  const [error, setError] = useState<string | null>(null);

  async function review(status: "approved" | "rejected") {
    setError(null);
    try {
      await patch(`/surveys/${sid}/insights/${ins.id}`, { status, selected_actions: selected, hr_note: note });
      onChange();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className={`card space-y-2 ${ins.status === "approved" ? "border-emerald-300" : ins.status === "rejected" ? "opacity-60" : ""}`}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge cls={KIND[ins.kind]?.cls}>{KIND[ins.kind]?.label ?? ins.kind}</Badge>
        <Badge>{PRIORITY[ins.priority] ?? ins.priority}</Badge>
        {ins.status !== "pending" && <Badge cls={ins.status === "approved" ? "bg-emerald-100 text-emerald-800" : "bg-slate-200"}>{ins.status === "approved" ? "Đã duyệt" : "Đã loại"}</Badge>}
      </div>
      <p className="font-semibold">{ins.title}</p>
      <p className="text-sm text-slate-700">{ins.detail}</p>
      {ins.departments.length > 0 && <p className="text-xs text-slate-500">Phòng ban: {ins.departments.join(", ")}</p>}
      <div className="space-y-1">
        <p className="text-sm font-medium">Hành động đề xuất {ins.status === "pending" && "(chọn để đưa vào kế hoạch)"}</p>
        {ins.suggested_actions.map((a) => (
          <label key={a} className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-1" disabled={ins.status !== "pending"} checked={selected.includes(a)}
              onChange={(e) => setSelected(e.target.checked ? [...selected, a] : selected.filter((x) => x !== a))} />
            {a}
          </label>
        ))}
      </div>
      {ins.status === "pending" ? (
        <>
          <input className="input" placeholder="Ghi chú của HR (không bắt buộc)" value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="flex gap-2">
            <button className="btn" onClick={() => review("approved")}>Duyệt vào báo cáo</button>
            <button className="btn-ghost" onClick={() => review("rejected")}>Loại (suy diễn quá mức / không chính xác)</button>
          </div>
        </>
      ) : ins.hr_note && <p className="text-xs text-slate-500">Ghi chú HR: {ins.hr_note}</p>}
      <ErrorBox message={error} />
    </div>
  );
}

function SurveyAdmin() {
  const { id } = useParams<{ id: string }>();
  const [d, setD] = useState<Dashboard | null>(null);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<Dashboard>(`/surveys/${id}/dashboard`).then(setD).catch((e) => setError(e.message));
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

  if (!d) return error ? <ErrorBox message={error} /> : <p className="text-slate-500">Đang tải...</p>;
  if (editing) {
    return <SurveyEditor initial={d as SurveyInput} saving={busy === "save"} onSave={(s) => act("save", async () => { await put(`/surveys/${id}`, s); setEditing(false); })} />;
  }
  const a = d.analysis;
  const pending = d.insights.filter((i) => i.status === "pending").length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{d.title}</h1>
          <p className="text-sm text-slate-500">{d.period_label} · {d.questions.length} câu hỏi</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {d.status === "draft" && <button className="btn-ghost" onClick={() => setEditing(true)}>Sửa câu hỏi</button>}
          {d.status !== "open" && <button className="btn-ghost" disabled={!!busy} onClick={() => act("open", () => post(`/surveys/${id}/status/open`))}>Mở khảo sát</button>}
          {d.status === "open" && <button className="btn-ghost" disabled={!!busy} onClick={() => act("close", () => post(`/surveys/${id}/status/closed`))}>Đóng khảo sát</button>}
          <button className="btn" disabled={!!busy || d.participation.responses === 0} onClick={() => act("analyze", () => post(`/surveys/${id}/analyze`))}>
            {busy === "analyze" ? "AI đang phân tích..." : a ? "Phân tích lại" : "Phân tích"}
          </button>
          {a && <Link className="btn-ghost" href={`/surveys/${id}/report`}>Báo cáo lãnh đạo</Link>}
        </div>
      </div>
      <ErrorBox message={error} />

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Tỷ lệ tham gia" value={`${Math.round(d.participation.rate * 100)}%`} hint={`${d.participation.responses}/${d.participation.members} thành viên`} />
        <Stat label="Trạng thái" value={d.status === "open" ? "Đang mở" : d.status === "draft" ? "Nháp" : "Đã đóng"} />
        <Stat label="Insight chờ duyệt" value={pending} tone={pending ? "warn" : undefined} hint="Chỉ insight đã duyệt mới vào báo cáo" />
      </div>

      {!a ? (
        <Notice>Chưa phân tích. Khi có đủ phản hồi, bấm “Phân tích”: AI gán cảm xúc và chủ đề cho câu trả lời mở; số liệu được tính bằng code và ẩn nhóm nhỏ.</Notice>
      ) : (
        <>
          {a.warnings.length > 0 && <Notice tone="warn" title="Giới hạn của dữ liệu">{a.warnings.map((w) => <p key={w}>• {w}</p>)}</Notice>}
          <OverallStats overall={a.stats.overall} comparison={a.comparison} minGroup={a.stats.min_group_size} />
          {a.previous_survey && <p className="text-xs text-slate-500">So sánh với kỳ trước: {a.previous_survey}</p>}
          <DepartmentTable departments={a.stats.departments} minGroup={a.stats.min_group_size} />

          <div className="grid gap-4 md:grid-cols-2">
            <div className="card">
              <h3 className="mb-2 font-semibold">Chủ đề trong phản hồi mở</h3>
              <ul className="space-y-1 text-sm tabular-nums">{a.topics.map(([t, n]) => <li key={t} className="flex justify-between"><span>{t}{a.persistent_topics.includes(t) && <Badge cls="ml-2 bg-red-100 text-red-700">Tồn đọng</Badge>}</span><b>{n}</b></li>)}</ul>
            </div>
            <div className="card">
              <h3 className="mb-2 font-semibold">Bộ nhớ chủ đề qua các kỳ</h3>
              <ul className="space-y-2 text-sm">
                {d.topic_memory.map((m) => (
                  <li key={m.id} className="flex flex-wrap items-center justify-between gap-2">
                    <span>{m.topic} · {m.occurrences} kỳ <span className="text-xs text-slate-500">({m.history.map((h) => `${h.period}: ${h.count}`).join(", ")})</span></span>
                    {m.status === "open" ? (
                      <button className="text-xs text-indigo-700 hover:underline" onClick={() => act("resolve", () => patch(`/surveys/topic-memory/${m.id}/resolve`))}>Đánh dấu đã xử lý</button>
                    ) : <Badge cls="bg-emerald-100 text-emerald-800">Đã xử lý</Badge>}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="space-y-3">
            <div>
              <h2 className="text-lg font-semibold">Insight & hành động đề xuất</h2>
              <AiNotice extra="HR xem xét, chọn hành động và duyệt trước khi báo cáo lãnh đạo." />
            </div>
            {d.insights.map((ins) => <InsightCard key={ins.id} sid={d.id} ins={ins} onChange={load} />)}
            {d.insights.length > 0 && <Csat targetType="survey_insights" targetId={d.id} label="Phân tích này có giúp ích cho HR không?" />}
          </div>
        </>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth roles={["hr"]}>
      <SurveyAdmin />
    </RequireAuth>
  );
}
