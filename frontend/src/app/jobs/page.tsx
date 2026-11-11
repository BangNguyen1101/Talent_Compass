"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { BoardItem, CV } from "@/lib/types";
import { Badge, ErrorBox, Notice, RequireAuth, ScoreBar } from "@/components/ui";

interface Facets {
  companies: { id: string; name: string; jobs: number }[];
  levels: string[];
  job_families: string[];
  departments: string[];
}

const EMPTY = { q: "", company: "", level: "", job_family: "", department: "", competency: "" };

function JobBoard() {
  const { user } = useAuth();
  const isSeeker = user!.role === "student";
  const [facets, setFacets] = useState<Facets | null>(null);
  const [filters, setFilters] = useState(EMPTY);
  const [query, setQuery] = useState(EMPTY); // giá trị đã "chốt" sau khi ngừng gõ
  const [cvs, setCvs] = useState<CV[]>([]);
  const [cvId, setCvId] = useState("");
  const [sort, setSort] = useState<"newest" | "match">("newest");
  const [data, setData] = useState<{ total: number; items: BoardItem[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Facets>("/jobs/board/facets").then(setFacets).catch(() => {});
    if (isSeeker) api<CV[]>("/cvs").then((c) => { setCvs(c); if (c[0]) { setCvId(c[0].id); setSort("match"); } }).catch(() => {});
  }, [isSeeker]);

  // Chờ người dùng ngừng gõ 300ms rồi mới tìm
  useEffect(() => {
    const t = setTimeout(() => setQuery(filters), 300);
    return () => clearTimeout(t);
  }, [filters]);

  const qs = useMemo(() => {
    const p = new URLSearchParams();
    Object.entries(query).forEach(([k, v]) => v && p.set(k, v));
    if (cvId) p.set("cv_id", cvId);
    p.set("sort", cvId ? sort : "newest");
    return p.toString();
  }, [query, cvId, sort]);

  useEffect(() => {
    setLoading(true);
    api<{ total: number; items: BoardItem[] }>(`/jobs/board?${qs}`)
      .then((d) => { setData(d); setError(null); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [qs]);

  const set = (k: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setFilters({ ...filters, [k]: e.target.value });
  const active = Object.values(filters).some(Boolean);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Việc làm</h1>
        <p className="text-sm text-slate-600">JD đã ban hành của mọi công ty trên TalentCompass. Tìm, lọc và {isSeeker ? "xếp hạng theo mức khớp với CV của bạn." : "xem chi tiết."}</p>
      </div>

      <div className="card space-y-3">
        <input className="input" placeholder="Tìm theo vị trí, công ty, kỹ năng trong JD..." value={filters.q} onChange={set("q")} />
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          <select className="input" value={filters.company} onChange={set("company")}>
            <option value="">Tất cả công ty</option>
            {facets?.companies.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.jobs})</option>)}
          </select>
          <select className="input" value={filters.level} onChange={set("level")}>
            <option value="">Mọi cấp độ</option>
            {facets?.levels.map((l) => <option key={l}>{l}</option>)}
          </select>
          <select className="input" value={filters.job_family} onChange={set("job_family")}>
            <option value="">Mọi nhóm vị trí</option>
            {facets?.job_families.map((l) => <option key={l}>{l}</option>)}
          </select>
          <select className="input" value={filters.department} onChange={set("department")}>
            <option value="">Mọi phòng ban</option>
            {facets?.departments.map((l) => <option key={l}>{l}</option>)}
          </select>
          <input className="input" placeholder="Năng lực, vd. Python" value={filters.competency} onChange={set("competency")} />
        </div>
        {isSeeker && (
          <div className="flex flex-wrap items-end gap-2 border-t border-slate-100 pt-3">
            <div className="min-w-56 flex-1">
              <label className="label">So khớp với CV của tôi</label>
              <select className="input" value={cvId} onChange={(e) => setCvId(e.target.value)}>
                <option value="">Không dùng CV</option>
                {cvs.map((c) => <option key={c.id} value={c.id}>{c.filename} · {new Date(c.created_at).toLocaleDateString("vi-VN")}</option>)}
              </select>
            </div>
            {cvId && (
              <div>
                <label className="label">Sắp xếp</label>
                <select className="input" value={sort} onChange={(e) => setSort(e.target.value as "newest" | "match")}>
                  <option value="match">Phù hợp nhất</option>
                  <option value="newest">Mới nhất</option>
                </select>
              </div>
            )}
            {!cvs.length && <Link href="/cv" className="btn-ghost">Tải CV để xem mức phù hợp</Link>}
          </div>
        )}
        {active && <button className="text-sm text-indigo-700 hover:underline" onClick={() => setFilters(EMPTY)}>Xóa bộ lọc</button>}
      </div>

      <ErrorBox message={error} />
      {data && <p className="text-sm text-slate-500">{loading ? "Đang tìm..." : `${data.total} việc làm`}</p>}
      {data?.total === 0 && <Notice>Không có JD phù hợp bộ lọc. Thử bỏ bớt điều kiện.</Notice>}

      <div className="space-y-3">
        {data?.items.map((j) => (
          <Link key={j.id} href={`/jobs/${j.id}`} className="card block transition hover:border-indigo-300">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-semibold">{j.title}</p>
                  {j.applied && <Badge cls="bg-emerald-100 text-emerald-800">Đã ứng tuyển</Badge>}
                </div>
                <p className="text-sm font-medium text-indigo-700">{j.company}</p>
                <p className="text-xs text-slate-500">
                  {j.level}{j.department && ` · ${j.department}`}{j.job_family && ` · ${j.job_family}`} · tuyển {j.headcount} · đăng {new Date(j.created_at).toLocaleDateString("vi-VN")}
                </p>
              </div>
              {j.match && (
                <div className="w-40 shrink-0 text-right">
                  <p className="text-lg font-bold tabular-nums text-indigo-700">{j.match.score}%</p>
                  <ScoreBar value={j.match.score} max={100} />
                  <p className="mt-1 text-xs text-slate-500">mức khớp từ khóa với CV</p>
                </div>
              )}
            </div>
            <div className="mt-3 flex flex-wrap gap-1">
              {j.competencies.map((c) => <span key={c} className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700">{c}</span>)}
            </div>
            {j.match && (j.match.matched.length > 0 || j.match.missing.length > 0) && (
              <p className="mt-2 text-xs">
                {j.match.matched.length > 0 && <span className="text-emerald-700">Có: {j.match.matched.join(", ")}. </span>}
                {j.match.missing.length > 0 && <span className="text-amber-700">Thiếu: {j.match.missing.join(", ")}</span>}
              </p>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <JobBoard />
    </RequireAuth>
  );
}
