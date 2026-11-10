"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { COMPANY_ROLES, homeFor, ROLE_LABEL } from "@/lib/roles";
import type { Role, User } from "@/lib/types";
import { ErrorBox } from "@/components/ui";

const FEATURES = [
  ["JD & khung năng lực (BO-15)", "AI soạn JD theo thương hiệu, kiểm tra thiên vị, nhất quán, định biên; quản lý duyệt nhiều cấp."],
  ["Trợ lý nghề nghiệp (EDU-17)", "Chấm CV theo JD và ATS, chống bịa kinh nghiệm, phỏng vấn thử nhiều vòng, cố vấn theo dõi tiến bộ."],
  ["Trợ lý phỏng vấn (BO-17)", "Câu hỏi theo khung năng lực, scorecard độc lập, tổng hợp nhiều người chấm, hội đồng quyết định."],
  ["Khảo sát gắn kết (BO-16)", "Khảo sát ẩn danh, phân tích cảm xúc & chủ đề theo phòng ban, insight HR duyệt trước khi báo cáo."],
];

const REGISTER_ROLES: Role[] = ["student", "advisor", "hr", "manager", "hiring_lead", "interviewer", "employee"];
const CAN_CREATE_ORG: Role[] = ["hr", "advisor"];

export default function Home() {
  const { user, signIn } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [orgMode, setOrgMode] = useState<"create" | "join">("create");
  const [form, setForm] = useState({
    email: "", password: "", full_name: "", role: "student" as Role, organization_name: "", join_code: "", department: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user) router.replace(homeFor(user.role));
  }, [user, router]);

  const canCreate = CAN_CREATE_ORG.includes(form.role);
  const creating = canCreate && orgMode === "create";
  const isCompany = COMPANY_ROLES.includes(form.role);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body =
        mode === "login"
          ? { email: form.email, password: form.password }
          : {
              email: form.email,
              password: form.password,
              full_name: form.full_name,
              role: form.role,
              organization_name: creating ? form.organization_name : null,
              join_code: !creating && form.join_code ? form.join_code : null,
              department: isCompany && form.department ? form.department : null,
            };
      const res = await post<{ access_token: string; user: User }>(`/auth/${mode}`, body);
      signIn(res.access_token, res.user);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm({ ...form, [k]: e.target.value });

  return (
    <div className="grid gap-8 md:grid-cols-2">
      <section className="space-y-5">
        <h1 className="text-3xl font-bold leading-tight">
          Một khung năng lực,
          <br />
          <span className="text-indigo-700">từ JD, CV, phỏng vấn đến gắn kết.</span>
        </h1>
        <p className="text-slate-600">
          AI đề xuất, con người quyết định. Dữ liệu cá nhân được che và phân quyền theo vai trò.
        </p>
        <ul className="space-y-3">
          {FEATURES.map(([t, d]) => (
            <li key={t} className="card">
              <p className="font-semibold">{t}</p>
              <p className="text-sm text-slate-600">{d}</p>
            </li>
          ))}
        </ul>
      </section>

      <form onSubmit={submit} className="card h-fit space-y-4">
        <div className="flex gap-2">
          {(["login", "register"] as const).map((m) => (
            <button key={m} type="button" onClick={() => setMode(m)} className={mode === m ? "btn flex-1" : "btn-ghost flex-1"}>
              {m === "login" ? "Đăng nhập" : "Đăng ký"}
            </button>
          ))}
        </div>
        {mode === "register" && (
          <>
            <div>
              <label className="label">Họ tên</label>
              <input className="input" required value={form.full_name} onChange={set("full_name")} />
            </div>
            <div>
              <label className="label">Vai trò</label>
              <select className="input" value={form.role} onChange={set("role")}>
                {REGISTER_ROLES.map((r) => (
                  <option key={r} value={r}>{ROLE_LABEL[r]}</option>
                ))}
              </select>
            </div>
            {canCreate && (
              <div className="flex gap-2 text-sm">
                {(["create", "join"] as const).map((m) => (
                  <label key={m} className="flex items-center gap-1">
                    <input type="radio" checked={orgMode === m} onChange={() => setOrgMode(m)} />
                    {m === "create" ? `Tạo ${form.role === "hr" ? "công ty" : "trường"} mới` : "Tham gia bằng mã"}
                  </label>
                ))}
              </div>
            )}
            {creating ? (
              <div>
                <label className="label">Tên {form.role === "hr" ? "công ty" : "trường / khoa"}</label>
                <input className="input" required value={form.organization_name} onChange={set("organization_name")} />
              </div>
            ) : (
              <div>
                <label className="label">
                  Mã tổ chức {form.role === "student" ? "(không bắt buộc, để cố vấn theo dõi tiến bộ)" : ""}
                </label>
                <input className="input uppercase" required={form.role !== "student"} placeholder="VD: AB12CD34" value={form.join_code} onChange={set("join_code")} />
                <p className="mt-1 text-xs text-slate-500">Lấy mã từ HR (công ty) hoặc cố vấn (trường) của bạn.</p>
              </div>
            )}
            {isCompany && (
              <div>
                <label className="label">Phòng ban</label>
                <input className="input" placeholder="VD: Kinh doanh" value={form.department} onChange={set("department")} />
              </div>
            )}
          </>
        )}
        <div>
          <label className="label">Email</label>
          <input className="input" type="email" required value={form.email} onChange={set("email")} />
        </div>
        <div>
          <label className="label">Mật khẩu {mode === "register" && "(tối thiểu 8 ký tự)"}</label>
          <input className="input" type="password" required minLength={mode === "register" ? 8 : 1} value={form.password} onChange={set("password")} />
        </div>
        <ErrorBox message={error} />
        <button className="btn w-full" disabled={busy}>
          {busy ? "Đang xử lý..." : mode === "login" ? "Đăng nhập" : "Tạo tài khoản"}
        </button>
      </form>
    </div>
  );
}
