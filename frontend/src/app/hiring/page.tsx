"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { STAGE } from "@/lib/roles";
import type { Job } from "@/lib/types";
import { Badge, ErrorBox, RequireAuth } from "@/components/ui";

interface Row { id: string; full_name: string; jd_title: string; stage: string; rounds: number; my_pending_rounds: string[]; created_at: string }

function Hiring() {
  const { user } = useAuth();
  const isLead = user!.role === "hiring_lead" || user!.role === "hr";
  const [rows, setRows] = useState<Row[] | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [form, setForm] = useState({ full_name: "", email: "", jd_id: "", cv_text: "" });
  const [error, setError] = useState<string | null>(null);

  const load = () => api<Row[]>("/hiring/candidates").then(setRows).catch((e) => setError(e.message));
  useEffect(() => {
    load();
    if (isLead) api<Job[]>("/jobs?scope=org").then((j) => setJobs(j.filter((x) => x.status === "published"))).catch(() => {});
  }, [isLead]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await post("/hiring/candidates", form);
      setForm({ full_name: "", email: "", jd_id: form.jd_id, cv_text: "" });
      load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{isLead ? "Tuyển dụng" : "Lịch phỏng vấn của tôi"}</h1>
        <p className="text-sm text-slate-600">
          {isLead
            ? "Tạo ứng viên, lập vòng phỏng vấn theo khung năng lực, tổng hợp đánh giá nhiều người và ra quyết định."
            : "Ứng viên bạn được phân công. Chấm độc lập: bạn không thấy điểm của người phỏng vấn khác."}
        </p>
      </div>

      {isLead && (
        <form onSubmit={create} className="card grid gap-3 sm:grid-cols-2">
          <h2 className="font-semibold sm:col-span-2">Thêm ứng viên</h2>
          <input className="input" required placeholder="Họ tên ứng viên" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          <input className="input" type="email" placeholder="Email (không bắt buộc)" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <select className="input sm:col-span-2" required value={form.jd_id} onChange={(e) => setForm({ ...form, jd_id: e.target.value })}>
            <option value="">Chọn vị trí (JD đã ban hành)</option>
            {jobs.map((j) => <option key={j.id} value={j.id}>{j.title} ({j.level})</option>)}
          </select>
          <textarea className="input min-h-20 sm:col-span-2" placeholder="Dán nội dung CV (không bắt buộc; thông tin liên hệ sẽ được che)" value={form.cv_text} onChange={(e) => setForm({ ...form, cv_text: e.target.value })} />
          <button className="btn w-fit">Thêm ứng viên</button>
        </form>
      )}
      <ErrorBox message={error} />

      {rows?.length === 0 && <div className="card text-slate-600">{isLead ? "Chưa có ứng viên." : "Bạn chưa được phân công phỏng vấn ai."}</div>}
      <div className="space-y-3">
        {rows?.map((r) => (
          <Link key={r.id} href={`/hiring/candidates/${r.id}`} className="card flex flex-wrap items-center justify-between gap-2 hover:border-indigo-300">
            <div>
              <p className="font-medium">{r.full_name}</p>
              <p className="text-xs text-slate-500">{r.jd_title} · {r.rounds} vòng</p>
            </div>
            <div className="flex items-center gap-2">
              {r.my_pending_rounds.length > 0 && <Badge cls="bg-red-100 text-red-700">Bạn cần chấm {r.my_pending_rounds.length} vòng</Badge>}
              <Badge cls={STAGE[r.stage]?.cls}>{STAGE[r.stage]?.label ?? r.stage}</Badge>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth roles={["hr", "hiring_lead", "interviewer"]}>
      <Hiring />
    </RequireAuth>
  );
}
