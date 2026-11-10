"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Role, User } from "@/lib/types";
import { ErrorBox } from "@/components/ui";

const FEATURES = [
  ["Khung năng lực từ JD", "AI soạn JD và khung năng lực có rubric 5 mức, bạn duyệt và chỉnh sửa."],
  ["Chấm CV theo JD", "So CV với từng năng lực, chỉ ra điểm thiếu và gợi ý viết lại cụ thể."],
  ["Phỏng vấn thử", "Câu hỏi bám đúng năng lực của vị trí, AI nhận xét từng câu trả lời."],
];

export default function Home() {
  const { user, signIn } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [form, setForm] = useState({ email: "", password: "", full_name: "", role: "student" as Role, organization_name: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user) router.replace("/jobs");
  }, [user, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body =
        mode === "login"
          ? { email: form.email, password: form.password }
          : { ...form, organization_name: form.role === "hr" ? form.organization_name : null };
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
          <span className="text-indigo-700">từ CV đến phỏng vấn.</span>
        </h1>
        <p className="text-slate-600">
          TalentCompass giúp sinh viên chuẩn bị CV và phỏng vấn đúng yêu cầu vị trí, và giúp HR xây JD cùng bộ tiêu chí đánh giá nhất quán.
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
              <label className="label">Bạn là</label>
              <select className="input" value={form.role} onChange={set("role")}>
                <option value="student">Sinh viên / ứng viên</option>
                <option value="hr">Nhà tuyển dụng (HR)</option>
              </select>
            </div>
            {form.role === "hr" && (
              <div>
                <label className="label">Tên công ty</label>
                <input className="input" required value={form.organization_name} onChange={set("organization_name")} />
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
