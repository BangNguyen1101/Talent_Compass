"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Role } from "@/lib/types";

export function RequireAuth({ children, roles }: { children: React.ReactNode; roles?: Role[] }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!loading && !user) router.replace("/");
  }, [loading, user, router]);
  if (loading || !user) return <p className="text-slate-500">Đang tải...</p>;
  if (roles && !roles.includes(user.role) && user.role !== "admin")
    return <ErrorBox message="Vai trò của bạn không truy cập được trang này." />;
  return <>{children}</>;
}

export function ErrorBox({ message }: { message: string | null }) {
  if (!message) return null;
  return <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{message}</div>;
}

export function Notice({ tone = "info", title, children }: { tone?: "info" | "warn" | "danger" | "ok"; title?: string; children: React.ReactNode }) {
  const cls = {
    info: "border-indigo-200 bg-indigo-50 text-indigo-900",
    warn: "border-amber-200 bg-amber-50 text-amber-900",
    danger: "border-red-200 bg-red-50 text-red-800",
    ok: "border-emerald-200 bg-emerald-50 text-emerald-900",
  }[tone];
  return (
    <div className={`rounded-lg border px-4 py-3 text-sm ${cls}`}>
      {title && <p className="mb-1 font-semibold">{title}</p>}
      {children}
    </div>
  );
}

export function Badge({ children, cls = "bg-slate-100 text-slate-700" }: { children: React.ReactNode; cls?: string }) {
  return <span className={`inline-block shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>{children}</span>;
}

export function ScoreBar({ value, max = 5, required }: { value: number; max?: number; required?: number | null }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const ok = required == null || value >= required;
  return (
    <div className="relative h-2 w-full rounded-full bg-slate-100">
      <div className={`h-2 rounded-full ${ok ? "bg-emerald-500" : "bg-amber-500"}`} style={{ width: `${pct}%` }} />
      {required != null && (
        <div className="absolute -top-1 h-4 w-0.5 bg-slate-600" style={{ left: `${(required / max) * 100}%` }} title={`Yêu cầu: ${required}`} />
      )}
    </div>
  );
}

export function Stat({ label, value, hint, tone }: { label: string; value: React.ReactNode; hint?: string; tone?: "ok" | "warn" }) {
  const color = tone === "ok" ? "text-emerald-700" : tone === "warn" ? "text-amber-700" : "text-slate-900";
  return (
    <div className="card">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold tabular-nums ${color}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

export function AiNotice({ extra }: { extra?: string }) {
  return (
    <p className="text-xs text-slate-500">
      Kết quả do AI đề xuất, chỉ mang tính tham khảo. Quyết định cuối cùng thuộc về con người.{extra ? ` ${extra}` : ""}
    </p>
  );
}

/** Thu CSAT 1-5 cho một kết quả AI. */
export function Csat({ targetType, targetId, label = "Kết quả này hữu ích với bạn đến mức nào?" }: { targetType: string; targetId: string; label?: string }) {
  const [rating, setRating] = useState<number | null>(null);
  const [comment, setComment] = useState("");
  const [sent, setSent] = useState(false);

  async function send(r: number, c = comment) {
    setRating(r);
    try {
      await post("/feedback", { target_type: targetType, target_id: targetId, rating: r, comment: c });
      setSent(true);
    } catch {
      setSent(false);
    }
  }

  return (
    <div className="card space-y-2">
      <p className="text-sm font-medium">{label}</p>
      <div className="flex items-center gap-1">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            onClick={() => send(n)}
            className={`h-9 w-9 rounded-lg border text-sm font-semibold ${rating && n <= rating ? "border-amber-400 bg-amber-100 text-amber-800" : "border-slate-300 bg-white text-slate-500 hover:bg-slate-50"}`}
            aria-label={`${n} sao`}
          >
            {n}★
          </button>
        ))}
        {sent && <span className="ml-2 text-xs text-emerald-700">Đã ghi nhận, cảm ơn bạn!</span>}
      </div>
      {rating !== null && rating <= 3 && (
        <div className="flex gap-2">
          <input className="input" placeholder="Điều gì chưa tốt? (không bắt buộc)" value={comment} onChange={(e) => setComment(e.target.value)} />
          <button className="btn-ghost" onClick={() => send(rating, comment)}>Gửi</button>
        </div>
      )}
    </div>
  );
}

export function BiasList({ issues }: { issues: { category: string; severity: string; excerpt: string; suggestion: string }[] }) {
  if (!issues.length) return null;
  return (
    <Notice tone={issues.some((i) => i.severity === "high") ? "danger" : "warn"} title={`Phát hiện ${issues.length} chỗ có thể gây thiên vị`}>
      <ul className="mt-1 space-y-2">
        {issues.map((i, k) => (
          <li key={k}>
            <Badge cls={i.severity === "high" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-800"}>{i.category}</Badge>{" "}
            <span className="italic">“{i.excerpt}”</span>
            <p className="text-xs opacity-80">→ {i.suggestion}</p>
          </li>
        ))}
      </ul>
    </Notice>
  );
}

export function Spinner({ text = "Đang xử lý..." }: { text?: string }) {
  return <p className="text-sm text-slate-500">{text}</p>;
}
