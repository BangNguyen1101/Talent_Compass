export type Role = "student" | "hr" | "admin";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  org_id: string | null;
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

export interface JobInput {
  title: string;
  level: string;
  content: string;
  status: "draft" | "published" | "closed";
  competencies: Competency[];
}

export interface Job extends JobInput {
  id: string;
  created_at: string;
}

export interface CV {
  id: string;
  filename: string;
  parsed: { headline?: string; skills?: string[] };
  created_at: string;
}

export interface Assessment {
  id: string;
  cv_id: string;
  jd_id: string;
  overall_score: number;
  model_used: string;
  created_at: string;
  result: {
    overall_comment: string;
    competency_scores: { competency: string; score: number; evidence: string; gap: string }[];
    strengths: string[];
    gaps: string[];
    suggestions: { section: string; issue: string; suggestion: string; example_rewrite: string }[];
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
}

export interface Interview {
  id: string;
  jd_id: string;
  mode: "mock" | "real";
  status: "in_progress" | "completed";
  turns: InterviewTurn[];
  summary: {
    overall: string;
    per_competency: { competency: string; average_score: number; comment: string }[];
    next_steps: string[];
  } | null;
  created_at: string;
}
