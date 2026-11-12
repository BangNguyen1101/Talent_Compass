"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, del, post, put } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { JOB_STATUS, ROUND_TYPES } from "@/lib/roles";
import type { CV, Interview, Job, JobChecks, JobInput } from "@/lib/types";
import { JobEditor } from "@/components/JobEditor";
import { QuestionDetail, QuestionTypeTag } from "@/components/QuestionDetail";
import { Badge, BiasList, Csat, ErrorBox, Notice, RequireAuth } from "@/components/ui";

const ORG_STAFF = ["hr", "manager", "hiring_lead", "interviewer"];

function ApplyBox({ job, onApplied }: { job: Job; onApplied: () => void }) {
  const [cvs, setCvs] = useState<CV[]>([]);
  const [cvId, setCvId] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<CV[]>("/cvs").then((c) => { setCvs(c); if (c[0]) setCvId(c[0].id); }).catch(() => {});
  }, []);

  if (job.my_application && job.my_application !== "withdrawn") {
    return (
      <Notice tone="ok" title="Bạn đã ứng tuyển vị trí này">
        Theo dõi trạng thái ở <Link href="/applications" className="underline">Đơn ứng tuyển</Link>.
      </Notice>
    );
  }

  async function apply() {
    setBusy(true);
    setError(null);
    try {
      await post(`/jobs/${job.id}/apply`, { cv_id: cvId, cover_note: note });
      onApplied();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card space-y-3 border-indigo-200">
      <h2 className="font-semibold">Ứng tuyển vào {job.company}</h2>
      {cvs.length === 0 ? (
        <p className="text-sm">Bạn cần <Link href="/cv" className="text-indigo-700 underline">tải CV lên</Link> trước khi ứng tuyển.</p>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="label">CV gửi kèm</label>
              <select className="input" value={cvId} onChange={(e) => setCvId(e.target.value)}>
                {cvs.map((c) => <option key={c.id} value={c.id}>{c.filename} · {new Date(c.created_at).toLocaleDateString("vi-VN")}</option>)}
              </select>
            </div>
            <div className="flex items-end">
              <Link href={`/cv?jd=${job.id}`} className="text-sm text-indigo-700 hover:underline">Chấm CV theo JD này trước khi nộp →</Link>
            </div>
          </div>
          <textarea className="input min-h-20" placeholder="Lời nhắn cho nhà tuyển dụng (không bắt buộc)" value={note} onChange={(e) => setNote(e.target.value)} />
          <p className="text-xs text-slate-500">Công ty nhận nội dung CV đã che email, số điện thoại, ngày sinh, địa chỉ.</p>
          <ErrorBox message={error} />
          <button className="btn" onClick={apply} disabled={busy || !cvId}>{busy ? "Đang nộp..." : "Nộp đơn ứng tuyển"}</button>
        </>
      )}
    </div>
  );
}

function JobDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const [job, setJob] = useState<Job | null>(null);
  const [checks, setChecks] = useState<JobChecks | null>(null);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [review, setReview] = useState({ comment: "" });
  const [practice, setPractice] = useState({ round_type: "behavioral", question_count: 5 });

  const load = useCallback(() => {
    api<Job>(`/jobs/${id}`).then((j) => {
      setJob(j);
      if (j.org_id && (j.can_edit || user!.role === "manager")) api<JobChecks>(`/jobs/${id}/checks`).then(setChecks).catch(() => {});
    }).catch((e) => setError(e.message));
  }, [id, user]);

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

  async function save(input: JobInput) {
    await act("save", async () => {
      await put<Job>(`/jobs/${id}`, input);
      setEditing(false);
    });
  }

  async function startInterview() {
    setBusy("interview");
    setError(null);
    try {
      const s = await post<Interview>("/interviews", { jd_id: id, ...practice });
      router.push(`/interviews/${s.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(null);
    }
  }

  if (!job) return error ? <ErrorBox message={error} /> : <p className="text-slate-500">Đang tải...</p>;
  if (editing) return <JobEditor initial={job} onSave={save} saving={busy === "save"} jobId={job.id} />;

  const st = JOB_STATUS[job.status];
  const canReview = user!.role === "manager" && job.status === "pending_approval" && job.created_by !== user!.id;
  const isSeeker = user!.role === "student";
  const isOwnCompany = !!user!.org_id && job.org_id === user!.org_id;
  const showBank = ORG_STAFF.includes(user!.role) && isOwnCompany;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">{job.title}</h1>
            <Badge cls={st.cls}>{st.label}</Badge>
          </div>
          {job.company && <p className="font-medium text-indigo-700">{job.company}</p>}
          <p className="text-sm text-slate-500">
            {job.level}{job.department && ` · ${job.department}`}{job.job_family && ` · nhóm ${job.job_family}`}
            {job.org_id && ` · tuyển ${job.headcount} người`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {job.can_edit && <button className="btn-ghost" onClick={() => setEditing(true)}>Sửa</button>}
          {job.can_edit && job.org_id && (job.status === "draft" || job.status === "rejected") && (
            <button className="btn" disabled={!!busy} onClick={() => act("submit", () => post(`/jobs/${id}/submit`))}>
              Gửi duyệt / ban hành
            </button>
          )}
          {job.can_edit && job.status === "published" && (
            <button className="btn-ghost" onClick={() => act("close", () => post(`/jobs/${id}/status`, { status: "closed" }))}>Đóng tuyển</button>
          )}
          {job.can_edit && (
            <button className="btn-ghost text-red-600" onClick={async () => { if (confirm("Xóa JD này?")) { await del(`/jobs/${id}`); router.push("/company-jobs"); } }}>Xóa</button>
          )}
        </div>
      </div>
      <ErrorBox message={error} />
      {job.can_edit && job.status === "pending_approval" && (
        <Notice tone="warn">JD đang chờ quản lý duyệt. Nếu sửa nội dung, JD sẽ quay về nháp và phải gửi duyệt lại.</Notice>
      )}

      {isSeeker && job.status === "published" && <ApplyBox job={job} onApplied={load} />}

      {isSeeker && (
        <div className="card flex flex-wrap items-end gap-3">
          <p className="w-full text-sm font-medium">Chuẩn bị cho vị trí này</p>
          <Link href={`/cv?jd=${job.id}`} className="btn-ghost">Chấm CV theo JD này</Link>
          <div className="ml-auto flex flex-wrap items-end gap-2">
            <div>
              <label className="label">Loại vòng</label>
              <select className="input" value={practice.round_type} onChange={(e) => setPractice({ ...practice, round_type: e.target.value })}>
                {Object.entries(ROUND_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Số câu</label>
              <input className="input w-20" type="number" min={1} max={10} value={practice.question_count} onChange={(e) => setPractice({ ...practice, question_count: Number(e.target.value) })} />
            </div>
            <button className="btn" onClick={startInterview} disabled={!!busy}>{busy === "interview" ? "Đang tạo câu hỏi..." : "Phỏng vấn thử"}</button>
          </div>
        </div>
      )}

      {canReview && (
        <div className="card space-y-3 border-amber-300">
          <h2 className="font-semibold">Phê duyệt JD</h2>
          <textarea className="input" placeholder="Nhận xét (bắt buộc khi từ chối)" value={review.comment} onChange={(e) => setReview({ comment: e.target.value })} />
          <div className="flex gap-2">
            <button className="btn" disabled={!!busy} onClick={() => act("approve", () => post(`/jobs/${id}/review`, { decision: "approved", comment: review.comment }))}>Duyệt</button>
            <button className="btn-ghost text-red-600" disabled={!!busy} onClick={() => act("reject", () => post(`/jobs/${id}/review`, { decision: "rejected", comment: review.comment }))}>Từ chối</button>
          </div>
        </div>
      )}

      {checks && (checks.bias.length > 0 || checks.consistency.length > 0 || checks.headcount) && (
        <div className="space-y-2">
          <BiasList issues={checks.bias} />
          {checks.consistency.length > 0 && <Notice tone="warn" title="Chưa nhất quán với vị trí cùng nhóm">{checks.consistency.map((c, i) => <p key={i}>• {c.message}</p>)}</Notice>}
          {checks.headcount && <Notice tone="warn" title="Định biên">{checks.headcount.message}</Notice>}
        </div>
      )}

      {job.approvals.length > 0 && (
        <div className="card">
          <h2 className="mb-2 font-semibold">Lịch sử phê duyệt</h2>
          <ol className="space-y-1 text-sm">
            {job.approvals.map((a, i) => (
              <li key={i}>
                <span className="text-slate-500">{new Date(a.at).toLocaleString("vi-VN")}</span> · <b>{a.by}</b>{" "}
                {a.decision === "submitted" ? "gửi duyệt" : a.decision === "approved" ? `duyệt cấp ${a.level}` : "từ chối"}
                {a.comment && <span className="text-slate-600">: “{a.comment}”</span>}
              </li>
            ))}
          </ol>
        </div>
      )}

      <div className="card whitespace-pre-wrap text-sm leading-relaxed">{job.content}</div>

      <div className="card">
        <h2 className="mb-3 font-semibold">Khung năng lực</h2>
        <div className="space-y-3">
          {job.competencies.map((c) => (
            <details key={c.name} className="rounded-lg border border-slate-200 p-3">
              <summary className="cursor-pointer">
                <span className="font-medium">{c.name}</span>
                <span className="ml-2 text-xs text-slate-500">yêu cầu mức {c.required_level}/5 · trọng số {c.weight}</span>
              </summary>
              <p className="mt-2 text-sm text-slate-600">{c.description}</p>
              <ol className="mt-2 space-y-1 text-sm">
                {c.rubric.map((r) => (
                  <li key={r.level} className={r.level === c.required_level ? "font-medium text-indigo-700" : "text-slate-600"}>
                    <span className="inline-block w-14">Mức {r.level}</span>{r.descriptor}
                  </li>
                ))}
              </ol>
            </details>
          ))}
        </div>
      </div>

      {showBank && (
        <div className="card space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-semibold">Câu hỏi phỏng vấn & tiêu chí chấm theo JD</h2>
            <button className="btn-ghost" disabled={!!busy} onClick={() => act("bank", () => post(`/jobs/${id}/question-bank`))}>
              {busy === "bank" ? "AI đang soạn..." : job.question_bank.length ? "Soạn lại" : "AI soạn ngân hàng câu hỏi"}
            </button>
          </div>
          {job.question_bank.length > 0 && (
            <>
              <p className="text-xs text-slate-500">Các vòng phỏng vấn ứng viên của vị trí này sẽ dùng ngân hàng câu hỏi này để mọi ứng viên được hỏi nhất quán.</p>
              <ol className="space-y-3 text-sm">
                {job.question_bank.map((q, i) => (
                  <li key={i} className="rounded-lg bg-slate-50 p-3">
                    <p className="text-xs font-semibold uppercase text-indigo-700">{q.competency}<QuestionTypeTag type={q.type} /></p>
                    <p className="font-medium">{q.question}</p>
                    <p className="mt-1 text-emerald-700">✓ {q.good_signals.join("; ")}</p>
                    <p className="text-red-600">✗ {q.red_flags.join("; ")}</p>
                    <QuestionDetail followUps={q.follow_ups} guide={q.scoring_guide} />
                  </li>
                ))}
              </ol>
              <Csat targetType="question_bank" targetId={job.id} label="Bộ câu hỏi này có dùng được không?" />
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <JobDetail />
    </RequireAuth>
  );
}
