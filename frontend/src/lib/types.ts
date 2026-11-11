export type Role = "student" | "advisor" | "hr" | "manager" | "interviewer" | "hiring_lead" | "employee" | "admin";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  org_id: string | null;
  department: string | null;
  share_with_advisor: boolean;
}

export interface Org {
  id: string;
  name: string;
  kind: "company" | "school";
  join_code: string | null;
  brand_voice: string;
  jd_approval_levels: number;
}

export interface Member extends User {
  is_active: boolean;
  created_at: string;
}

export interface RubricLevel {
  level: number;
  descriptor: string;
}

export interface Competency {
  name: string;
  category: string;
  description: string;
  required_level: number;
  weight: number;
  rubric: RubricLevel[];
}

export type JobStatus = "draft" | "pending_approval" | "rejected" | "published" | "closed";

export interface JobInput {
  title: string;
  level: string;
  department: string;
  job_family: string;
  headcount: number;
  content: string;
  competencies: Competency[];
}

export interface BiasIssue {
  category: string;
  severity: "high" | "medium";
  excerpt: string;
  suggestion: string;
}

export interface QuestionBankItem {
  question: string;
  competency: string;
  good_signals: string[];
  red_flags: string[];
}

export interface Job extends JobInput {
  id: string;
  status: JobStatus;
  created_at: string;
  created_by: string;
  org_id: string | null;
  bias_issues: BiasIssue[];
  question_bank: QuestionBankItem[];
  approvals: { level: number; decision: string; comment: string; by: string; at: string }[];
  can_edit: boolean;
  company: string | null;
  my_application: string | null;
}

export interface BoardItem {
  id: string;
  title: string;
  level: string;
  department: string;
  job_family: string;
  headcount: number;
  company: string;
  company_id: string;
  created_at: string;
  competencies: string[];
  summary: string;
  applied: boolean;
  match: { score: number; matched: string[]; missing: string[] } | null;
}

export interface Application {
  id: string;
  jd_id: string;
  title: string;
  level: string;
  company: string;
  stage: string;
  status: string;
  match_score: number | null;
  applied_at: string;
  can_withdraw: boolean;
}

export interface JobChecks {
  bias: BiasIssue[];
  consistency: { type: string; competency: string; message: string }[];
  headcount: { type: string; message: string } | null;
}

export interface CV {
  id: string;
  filename: string;
  parsed: { headline?: string; skills?: string[] };
  created_at: string;
}

export interface ATSResult {
  score: number;
  matched_keywords: string[];
  missing_keywords: string[];
  sections: Record<string, boolean>;
  word_count: number;
  tips: string[];
}

export interface CVSuggestionT {
  section: string;
  issue: string;
  suggestion: string;
  example_rewrite: string;
  unverified_details?: string[];
  guardrail_note?: string;
}

export interface Assessment {
  id: string;
  cv_id: string;
  jd_id: string;
  overall_score: number;
  ats_score: number;
  ats: ATSResult;
  model_used: string;
  created_at: string;
  result: {
    overall_comment: string;
    competency_scores: { competency: string; score: number; evidence: string; gap: string }[];
    strengths: string[];
    gaps: string[];
    suggestions: CVSuggestionT[];
    guardrail_flagged?: number;
    disclaimer?: string;
  };
}

export interface InterviewTurn {
  question: string;
  competency: string;
  what_good_looks_like: string;
  answer: string | null;
  score: number | null;
  feedback: string | null;
  better_answer_hint: string | null;
  follow_up_question?: string;
  parent: number | null;
}

export interface Interview {
  id: string;
  jd_id: string;
  mode: "mock" | "real";
  round_type: string;
  status: "in_progress" | "completed";
  turns: InterviewTurn[];
  summary: {
    overall: string;
    per_competency: { competency: string; average_score: number; comment: string }[];
    next_steps: string[];
  } | null;
  average_score: number | null;
  created_at: string;
}

export interface FirstLast {
  first: number | null;
  latest: number | null;
  delta: number | null;
  count: number;
}

export interface Progress {
  interview: FirstLast;
  cv: FirstLast;
  ats: FirstLast;
  interview_history: { id: string; date: string; round_type: string; average_score: number }[];
  cv_history: { id: string; date: string; jd: string; score: number; ats: number }[];
  advisor_notes?: AdvisorNote[];
}

export interface AdvisorNote {
  id: number;
  advisor: string;
  target_type: string;
  target_id: string | null;
  content: string;
  created_at: string;
}

export interface SurveyQuestion {
  id: string;
  type: "likert" | "text";
  text: string;
  dimension: string;
}

export interface Survey {
  id: string;
  title: string;
  description: string;
  period_label: string;
  questions: SurveyQuestion[];
  status: "draft" | "open" | "closed";
  created_at: string;
  analyzed_at: string | null;
  answered?: boolean;
  responses?: number | null;
}

export interface Insight {
  id: number;
  kind: "theme" | "risk" | "strength";
  title: string;
  detail: string;
  departments: string[];
  evidence_count: number;
  priority: "high" | "medium" | "low";
  suggested_actions: string[];
  selected_actions: string[];
  status: "pending" | "approved" | "rejected";
  hr_note: string;
}

export interface GroupStats {
  n: number;
  suppressed: boolean;
  engagement_index?: number | null;
  dimension_avgs?: Record<string, number>;
  sentiment?: Record<string, number>;
  negative_ratio?: number;
  risk_ratio?: number;
  top_topics?: [string, number][];
}
