import type { JobStatus, Role } from "./types";

export const ROLE_LABEL: Record<Role, string> = {
  student: "Sinh viên",
  advisor: "Cố vấn hướng nghiệp",
  hr: "HR",
  manager: "Quản lý phê duyệt",
  interviewer: "Người phỏng vấn",
  hiring_lead: "Trưởng nhóm tuyển dụng",
  employee: "Nhân viên",
  admin: "Quản trị",
};

export const COMPANY_ROLES: Role[] = ["hr", "manager", "hiring_lead", "interviewer", "employee"];
export const SCHOOL_ROLES: Role[] = ["advisor", "student"];

type NavItem = { href: string; label: string };

export function navFor(role: Role): NavItem[] {
  const jobs = { href: "/jobs", label: "JD & năng lực" };
  const settings = { href: "/settings", label: "Cài đặt" };
  switch (role) {
    case "student":
      return [jobs, { href: "/cv", label: "Chấm CV" }, { href: "/interviews", label: "Phỏng vấn thử" },
        { href: "/progress", label: "Tiến bộ" }, settings];
    case "advisor":
      return [{ href: "/advisor", label: "Bảng cố vấn" }, jobs, settings];
    case "hr":
      return [jobs, { href: "/hiring", label: "Tuyển dụng" }, { href: "/surveys", label: "Khảo sát" }, settings];
    case "manager":
      return [{ href: "/approvals", label: "Chờ duyệt" }, jobs, { href: "/surveys", label: "Báo cáo khảo sát" }, settings];
    case "hiring_lead":
      return [{ href: "/hiring", label: "Tuyển dụng" }, jobs, { href: "/surveys", label: "Khảo sát" }, settings];
    case "interviewer":
      return [{ href: "/hiring", label: "Lịch phỏng vấn" }, { href: "/surveys", label: "Khảo sát" }, settings];
    case "employee":
      return [{ href: "/surveys", label: "Khảo sát" }, settings];
    default:
      return [jobs, settings];
  }
}

export function homeFor(role: Role): string {
  return navFor(role)[0].href;
}

export const JOB_STATUS: Record<JobStatus, { label: string; cls: string }> = {
  draft: { label: "Nháp", cls: "bg-slate-100 text-slate-700" },
  pending_approval: { label: "Chờ duyệt", cls: "bg-amber-100 text-amber-800" },
  rejected: { label: "Bị từ chối", cls: "bg-red-100 text-red-700" },
  published: { label: "Đã ban hành", cls: "bg-emerald-100 text-emerald-800" },
  closed: { label: "Đã đóng", cls: "bg-slate-200 text-slate-600" },
};

export const ROUND_TYPES: Record<string, string> = {
  screening: "Sàng lọc",
  behavioral: "Hành vi (STAR)",
  technical: "Chuyên môn",
  final: "Vòng cuối",
};

export const STAGE: Record<string, { label: string; cls: string }> = {
  interviewing: { label: "Đang phỏng vấn", cls: "bg-indigo-100 text-indigo-800" },
  review: { label: "Chờ hội đồng", cls: "bg-amber-100 text-amber-800" },
  hired: { label: "Đã tuyển", cls: "bg-emerald-100 text-emerald-800" },
  rejected: { label: "Không tuyển", cls: "bg-slate-200 text-slate-700" },
  on_hold: { label: "Tạm hoãn", cls: "bg-slate-100 text-slate-700" },
};

export const REC_LABEL: Record<string, string> = {
  strong_hire: "Rất nên tuyển",
  hire: "Nên tuyển",
  no_hire: "Không nên tuyển",
  strong_no_hire: "Chắc chắn không",
  more_info: "Cần thêm thông tin",
};
