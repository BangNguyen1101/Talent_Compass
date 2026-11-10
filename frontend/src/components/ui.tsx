"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!loading && !user) router.replace("/");
  }, [loading, user, router]);
  if (loading || !user) return <p className="text-slate-500">Đang tải...</p>;
  return <>{children}</>;
}

export function ErrorBox({ message }: { message: string | null }) {
  if (!message) return null;
  return <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{message}</div>;
}

export function ScoreBar({ value, max = 5, required }: { value: number; max?: number; required?: number }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const ok = required === undefined || value >= required;
  return (
    <div className="relative h-2 w-full rounded-full bg-slate-100">
      <div className={`h-2 rounded-full ${ok ? "bg-emerald-500" : "bg-amber-500"}`} style={{ width: `${pct}%` }} />
      {required !== undefined && (
        <div className="absolute -top-1 h-4 w-0.5 bg-slate-500" style={{ left: `${(required / max) * 100}%` }} title={`Yêu cầu: ${required}`} />
      )}
    </div>
  );
}

export function AiNotice() {
  return (
    <p className="text-xs text-slate-500">
      Kết quả do AI đề xuất, chỉ mang tính tham khảo. Quyết định cuối cùng thuộc về con người.
    </p>
  );
}
