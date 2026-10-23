// Wire contract: the backend serializers (backend/quiz_app/serializers.py) and
// this file implement exactly the same shapes. Times are integer epoch ms.

export type Role = 'solver' | 'admin';
export type Me = { email: string; display_name: string | null; role: Role };

export type SetCard = {
  id: number; name: string; short_name: string;          // short_name = name without the "subtopic · " prefix
  difficulty: 'easy' | 'medium' | 'hard' | null; style: 'standard' | 'scenario';
  time_limit_minutes: number | null; question_count: number;
  last: { attempt_id: string; status: 'submitted' | 'expired'; score: number; max_score: number } | null;
  open_attempt: { attempt_id: string; deadline_at: number | null } | null;
};
export type TopicsResponse = { topics: {
  id: number; name: string;
  groups: { subtopic: { id: number; name: string } | null; sets: SetCard[] }[];   // null group first, then subtopic position
}[] };                                                                              // topics by position, then id

export type SetIntro = { id: number; topic: string; subtopic: string | null; name: string; description: string | null;
  time_limit_minutes: number | null; question_count: number; max_attempts: number | null; attempts_used: number;
  open_attempt_id: string | null };

export type AttemptSession = {
  attempt: { id: string; set_id: number; status: 'in_progress' | 'submitted' | 'expired';
             started_at: number; deadline_at: number | null };
  server_now: number;
  set: { name: string; topic: string; subtopic: string | null };
  questions: { id: number; prompt: string; options: { id: number; body: string }[] }[];  // display order
  selections: Record<string, number[]>;   // question id (string key) → option ids
};

export type Results = {
  attempt: { id: string; status: 'submitted' | 'expired'; started_at: number; finished_at: number;
             score: number; max_score: number };
  set: { id: number; name: string; topic: string; scoring_policy: 'all_or_nothing' | 'partial'; reveal_answers: boolean };
  questions: { id: number; prompt: string; points: number; awarded_points: number; is_correct: boolean;
               explanation: string | null;                          // null when !reveal_answers
               options: { id: number; body: string; selected: boolean; correct: boolean | null }[] }[];  // correct null when !reveal_answers
};

export type History = { attempts: { id: string; set_id: number; name: string; topic: string;
  status: 'in_progress' | 'submitted' | 'expired'; started_at: number; finished_at: number | null;
  score: number | null; max_score: number | null }[] };            // newest first

export type AdminSets = { sets: { id: number; topic: string; name: string; status: 'draft' | 'published' | 'archived';
  question_count: number; attempt_count: number }[] };

// Small route responses the contract table gives inline.
export type SubmitResult = { attempt_id: string; status: AttemptSession['attempt']['status'] };
export type ImportResult = { id: number; name: string };
export type SetStatusResult = { id: number; status: AdminSets['sets'][number]['status'] };
