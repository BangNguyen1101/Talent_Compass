"use client";

import { useEffect, useState } from "react";
import { api, del, patch, post, put } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { COMPANY_ROLES, ROLE_LABEL, SCHOOL_ROLES } from "@/lib/roles";
import type { Member, Org, Role, User } from "@/lib/types";
import { ErrorBox, Notice, RequireAuth } from "@/components/ui";

interface Plan { id: number; department: string; job_family: string; approved: number; filled: number }
interface Usage {
  my_calls_today: number;
  daily_quota: number;
  org?: { days: number; total_cost_usd: number; total_calls: number;
    by_feature: { feature: string; model: string; calls: number; input_tokens: number; output_tokens: number; cost_usd: number }[] };
}

function Profile() {
  const { user, setUser } = useAuth();
  const [form, setForm] = useState({ full_name: user!.full_name, department: user!.department ?? "" });
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function save(extra: Partial<User> = {}) {
    setError(null);
    try {
      setUser(await patch<User>("/auth/me", { ...form, ...extra }));
      setMsg("Đã lưu");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function join() {
    try {
      setUser(await post<User>(`/auth/join?join_code=${encodeURIComponent(code)}`));
      setMsg("Đã tham gia tổ chức");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section className="card space-y-4">
      <h2 className="font-semibold">Hồ sơ của bạn</h2>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="label">Họ tên</label>
          <input className="input" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
        </div>
        {COMPANY_ROLES.includes(user!.role) && (
          <div>
            <label className="label">Phòng ban (dùng để tổng hợp khảo sát ẩn danh)</label>
            <input className="input" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} />
          </div>
        )}
      </div>
      <button className="btn" onClick={() => save()}>Lưu</button>

      {user!.role === "student" && (
        <div className="space-y-3 border-t border-slate-200 pt-4">
          {user!.org_id ? (
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={user!.share_with_advisor}
                onChange={(e) => save({ share_with_advisor: e.target.checked })}
              />
              <span>
                Cho phép cố vấn hướng nghiệp của trường xem báo cáo CV và phỏng vấn thử của tôi để nhận xét.
                <span className="block text-xs text-slate-500">Bạn có thể tắt bất kỳ lúc nào.</span>
              </span>
            </label>
          ) : (
            <div className="flex flex-wrap items-end gap-2">
              <div>
                <label className="label">Tham gia trường bằng mã của cố vấn</label>
                <input className="input uppercase" value={code} onChange={(e) => setCode(e.target.value)} />
              </div>
              <button className="btn-ghost" onClick={join} disabled={!code}>Tham gia</button>
            </div>
          )}
        </div>
      )}
      {msg && <p className="text-sm text-emerald-700">{msg}</p>}
      <ErrorBox message={error} />
    </section>
  );
}

function OrgSettings() {
  const { user } = useAuth();
  const [org, setOrg] = useState<Org | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const isAdmin = user!.role === "hr" || user!.role === "advisor";
  const canSeeMembers = ["hr", "advisor", "manager", "hiring_lead"].includes(user!.role);

  useEffect(() => {
    api<Org>("/org").then(setOrg).catch((e) => setError(e.message));
    if (canSeeMembers) api<Member[]>("/org/members").then(setMembers).catch(() => {});
  }, [canSeeMembers]);

  if (!org) return <ErrorBox message={error} />;
  const roles: Role[] = org.kind === "company" ? COMPANY_ROLES : SCHOOL_ROLES;

  async function saveOrg() {
    try {
      setOrg(await patch<Org>("/org", { name: org!.name, brand_voice: org!.brand_voice, jd_approval_levels: org!.jd_approval_levels }));
      setSaved(true);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function updateMember(id: string, body: Partial<Member>) {
    try {
      const m = await patch<Member>(`/org/members/${id}`, body);
      setMembers(members.map((x) => (x.id === id ? m : x)));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section className="card space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">{org.kind === "company" ? "Công ty" : "Trường"}: {org.name}</h2>
        {org.join_code && (
          <p className="text-sm">
            Mã mời thành viên: <code className="rounded bg-slate-100 px-2 py-1 font-mono font-semibold">{org.join_code}</code>
          </p>
        )}
      </div>
      {isAdmin && (
        <div className="space-y-3">
          {org.kind === "company" && (
            <>
              <div>
                <label className="label">Phong cách thương hiệu (AI dùng mỗi khi soạn JD)</label>
                <textarea
                  className="input min-h-24"
                  placeholder="VD: Giọng văn thân thiện, xưng 'bạn'; nhấn mạnh giá trị: Tận tâm - Đổi mới - Hợp tác; không dùng từ lóng."
                  value={org.brand_voice}
                  onChange={(e) => setOrg({ ...org, brand_voice: e.target.value })}
                />
              </div>
              <div className="max-w-xs">
                <label className="label">Số cấp phê duyệt JD</label>
                <select className="input" value={org.jd_approval_levels} onChange={(e) => setOrg({ ...org, jd_approval_levels: Number(e.target.value) })}>
                  {[1, 2, 3].map((n) => <option key={n} value={n}>{n} cấp</option>)}
                </select>
              </div>
            </>
          )}
          <button className="btn" onClick={saveOrg}>Lưu cài đặt</button>
          {saved && <span className="ml-2 text-sm text-emerald-700">Đã lưu</span>}
        </div>
      )}

      {canSeeMembers && (
        <div className="overflow-x-auto">
          <h3 className="mb-2 font-medium">Thành viên ({members.length})</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-slate-500">
                <th className="py-2">Tên</th><th>Email</th><th>Vai trò</th><th>Phòng ban</th><th>Hoạt động</th>
              </tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.id} className="border-b border-slate-100">
                  <td className="py-2">{m.full_name}</td>
                  <td className="text-slate-500">{m.email}</td>
                  <td>
                    {isAdmin && m.id !== user!.id ? (
                      <select className="input py-1" value={m.role} onChange={(e) => updateMember(m.id, { role: e.target.value as Role })}>
                        {roles.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
                      </select>
                    ) : ROLE_LABEL[m.role]}
                  </td>
                  <td>
                    {isAdmin && org.kind === "company" ? (
                      <input className="input py-1" defaultValue={m.department ?? ""} onBlur={(e) => e.target.value !== (m.department ?? "") && updateMember(m.id, { department: e.target.value })} />
                    ) : m.department ?? "—"}
                  </td>
                  <td>
                    {isAdmin && m.id !== user!.id ? (
                      <input type="checkbox" checked={m.is_active} onChange={(e) => updateMember(m.id, { is_active: e.target.checked })} />
                    ) : m.is_active ? "✓" : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <ErrorBox message={error} />
    </section>
  );
}

function Headcount() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [form, setForm] = useState({ department: "", job_family: "", approved: 1, filled: 0 });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Plan[]>("/org/headcount").then(setPlans).catch((e) => setError(e.message));
  }, []);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    try {
      setPlans([...plans, await post<Plan>("/org/headcount", form)]);
      setForm({ department: "", job_family: "", approved: 1, filled: 0 });
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function update(p: Plan) {
    try {
      await put(`/org/headcount/${p.id}`, p);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section className="card space-y-3">
      <h2 className="font-semibold">Định biên được duyệt (thông tin nội bộ)</h2>
      <p className="text-sm text-slate-600">Hệ thống cảnh báo khi JD xin tuyển vượt số định biên còn trống của phòng ban / nhóm vị trí.</p>
      <table className="w-full text-sm">
        <thead><tr className="border-b text-left text-slate-500"><th className="py-2">Phòng ban</th><th>Nhóm vị trí</th><th>Được duyệt</th><th>Đã có</th><th /></tr></thead>
        <tbody>
          {plans.map((p, i) => (
            <tr key={p.id} className="border-b border-slate-100">
              <td className="py-2">{p.department}</td>
              <td>{p.job_family}</td>
              {(["approved", "filled"] as const).map((k) => (
                <td key={k}>
                  <input className="input w-20 py-1" type="number" min={0} value={p[k]}
                    onChange={(e) => setPlans(plans.map((x, j) => (j === i ? { ...x, [k]: Number(e.target.value) } : x)))}
                    onBlur={() => update(plans[i])} />
                </td>
              ))}
              <td><button className="text-red-600 hover:underline" onClick={async () => { await del(`/org/headcount/${p.id}`); setPlans(plans.filter((x) => x.id !== p.id)); }}>Xóa</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <form onSubmit={add} className="flex flex-wrap items-end gap-2">
        <input className="input w-40" required placeholder="Phòng ban" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} />
        <input className="input w-40" required placeholder="Nhóm vị trí (vd. Backend)" value={form.job_family} onChange={(e) => setForm({ ...form, job_family: e.target.value })} />
        <input className="input w-24" type="number" min={0} value={form.approved} onChange={(e) => setForm({ ...form, approved: Number(e.target.value) })} title="Được duyệt" />
        <input className="input w-24" type="number" min={0} value={form.filled} onChange={(e) => setForm({ ...form, filled: Number(e.target.value) })} title="Đã có" />
        <button className="btn-ghost">+ Thêm</button>
      </form>
      <ErrorBox message={error} />
    </section>
  );
}

function UsagePanel() {
  const [u, setU] = useState<Usage | null>(null);
  useEffect(() => {
    api<Usage>("/usage").then(setU).catch(() => {});
  }, []);
  if (!u) return null;
  return (
    <section className="card space-y-3">
      <h2 className="font-semibold">Chi phí & hạn mức AI</h2>
      <p className="text-sm">Hôm nay bạn đã dùng <b>{u.my_calls_today}</b>/{u.daily_quota} lượt AI.</p>
      {u.org && (
        <>
          <p className="text-sm">
            Tổ chức ({u.org.days} ngày gần nhất): <b>{u.org.total_calls}</b> lượt, chi phí ước tính{" "}
            <b>${u.org.total_cost_usd.toFixed(4)}</b>
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b text-left text-slate-500"><th className="py-2">Chức năng</th><th>Model</th><th className="text-right">Lượt</th><th className="text-right">Token vào/ra</th><th className="text-right">USD</th></tr></thead>
              <tbody>
                {u.org.by_feature.map((r) => (
                  <tr key={r.feature + r.model} className="border-b border-slate-100 tabular-nums">
                    <td className="py-1.5">{r.feature}</td><td>{r.model}</td><td className="text-right">{r.calls}</td>
                    <td className="text-right">{r.input_tokens.toLocaleString()} / {r.output_tokens.toLocaleString()}</td>
                    <td className="text-right">{r.cost_usd.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

function SettingsPage() {
  const { user } = useAuth();
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Cài đặt</h1>
      <Profile />
      {user!.org_id ? <OrgSettings /> : user!.role !== "student" && <Notice tone="warn">Bạn chưa thuộc tổ chức nào.</Notice>}
      {(user!.role === "hr" || user!.role === "manager") && <Headcount />}
      <UsagePanel />
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <SettingsPage />
    </RequireAuth>
  );
}
