"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Survey } from "@/lib/types";
import { SurveyEditor, type SurveyInput } from "@/components/SurveyEditor";
import { Badge, ErrorBox, RequireAuth } from "@/components/ui";

const STATUS: Record<Survey["status"], { label: string; cls: string }> = {
  draft: { label: "Nháp", cls: "bg-slate-100 text-slate-700" },
  open: { label: "Đang mở", cls: "bg-emerald-100 text-emerald-800" },
  closed: { label: "Đã đóng", cls: "bg-slate-200 text-slate-600" },
};

function Surveys() {
  const { user } = useAuth();
  const router = useRouter();
  const isHr = user!.role === "hr";
  const isViewer = isHr || user!.role === "manager";
  const [list, setList] = useState<Survey[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Survey[]>("/surveys").then(setList).catch((e) => setError(e.message));
  }, []);

  async function create(s: SurveyInput) {
    setBusy(true);
    try {
      const created = await post<Survey>("/surveys", s);
      router.push(`/surveys/${created.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  const link = (s: Survey) =>
    isHr ? `/surveys/${s.id}` : user!.role === "manager" ? `/surveys/${s.id}/report` : `/surveys/${s.id}/respond`;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold">Khảo sát gắn kết</h1>
          <p className="text-sm text-slate-600">
            {isViewer ? "Thiết kế khảo sát, thu phản hồi ẩn danh và phân tích theo phòng ban." : "Câu trả lời của bạn được lưu ẩn danh: không ai, kể cả HR, biết bạn đã trả lời gì."}
          </p>
        </div>
        {isHr && !creating && <button className="btn" onClick={() => setCreating(true)}>+ Tạo khảo sát</button>}
      </div>
      <ErrorBox message={error} />
      {creating && (
        <SurveyEditor initial={{ title: "Khảo sát gắn kết", description: "Khảo sát ẩn danh, mất khoảng 5 phút.", period_label: "", questions: [] }} onSave={create} saving={busy} />
      )}
      {list?.length === 0 && <div className="card text-slate-600">{isViewer ? "Chưa có khảo sát." : "Hiện không có khảo sát nào đang mở."}</div>}
      <div className="space-y-3">
        {list?.map((s) => (
          <Link key={s.id} href={link(s)} className="card flex flex-wrap items-center justify-between gap-2 hover:border-indigo-300">
            <div>
              <p className="font-medium">{s.title}</p>
              <p className="text-xs text-slate-500">{s.period_label || new Date(s.created_at).toLocaleDateString("vi-VN")} · {s.questions.length} câu{s.responses != null && ` · ${s.responses} phản hồi`}</p>
            </div>
            <div className="flex items-center gap-2">
              {!isViewer && <Badge cls={s.answered ? "bg-emerald-100 text-emerald-800" : "bg-indigo-100 text-indigo-800"}>{s.answered ? "Đã trả lời" : "Trả lời ngay"}</Badge>}
              {isViewer && s.analyzed_at && <Badge cls="bg-indigo-100 text-indigo-800">Đã phân tích</Badge>}
              {isViewer && <Badge cls={STATUS[s.status].cls}>{STATUS[s.status].label}</Badge>}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <Surveys />
    </RequireAuth>
  );
}
