"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Progress } from "@/lib/types";
import { ProgressView } from "@/components/ProgressView";
import { ErrorBox, Notice, RequireAuth } from "@/components/ui";

function MyProgress() {
  const { user } = useAuth();
  const [p, setP] = useState<Progress | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Progress>("/me/progress").then(setP).catch((e) => setError(e.message));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Tiến bộ của bạn</h1>
        <p className="text-sm text-slate-600">So sánh lần đầu và lần gần nhất để thấy bạn đã cải thiện bao nhiêu.</p>
      </div>
      {!user!.org_id && (
        <Notice>
          Muốn cố vấn hướng nghiệp nhận xét báo cáo của bạn? Tham gia trường bằng mã ở <Link href="/settings" className="underline">Cài đặt</Link>.
        </Notice>
      )}
      <ErrorBox message={error} />
      {p && <ProgressView p={p} />}
      {p?.advisor_notes && p.advisor_notes.length > 0 && (
        <div className="card space-y-3">
          <h2 className="font-semibold">Nhận xét của cố vấn</h2>
          {p.advisor_notes.map((n) => (
            <div key={n.id} className="rounded-lg bg-indigo-50 p-3 text-sm">
              <p className="whitespace-pre-wrap">{n.content}</p>
              <p className="mt-1 text-xs text-slate-500">{n.advisor} · {new Date(n.created_at).toLocaleString("vi-VN")}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth roles={["student"]}>
      <MyProgress />
    </RequireAuth>
  );
}
