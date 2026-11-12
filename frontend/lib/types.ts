// Wire contract: the backend serializers (backend/quiz_app/serializers.py) and
// this file implement exactly the same shapes. Times are integer epoch ms.

export type Role = 'solver' | 'admin';
export type Me = { email: string; display_name: string | null; role: Role };

export type SetCard = {
  id: number; name: string; short_name: string;          // short_name = name without the "subtopic · " prefix
  difficulty: 'easy' | 'medium' | 'hard' | null; style: 'standard' | 'scenario';
  time_limit_minutes: number | null; question_count: number;
  last: { attempt_id: string; status: 'submitted' | 'expired'; score: number; max_score: number } | null;
  /** `remaining_ms` is computed by the server with pause already folded in. */
  open_attempt: { attempt_id: string; remaining_ms: number | null } | null;
};
/** The home page's catalogue, with cards of type C. */
export type Topics<C> = {
  id: number; name: string;
  groups: { subtopic: { id: number; name: string } | null; sets: C[] }[];   // null group first, then subtopic position
}[];                                                                        // topics by position, then id
export type TopicsResponse = { topics: Topics<SetCard> };

export type SetIntro = { id: number; topic: string; subtopic: string | null; name: string; description: string | null;
  time_limit_minutes: number | null; question_count: number;
  subjective_count: number;  // of question_count, how many are subjective (never marked)
  max_attempts: number | null; attempts_used: number; open_attempt_id: string | null };

/**
 * A choice question is answered by ticking options and marked; a subjective one is answered by
 * typing into a text box and never marked (no points, no -2 when blank). Every subjective
 * question carries an authored model answer, shown on review when the set reveals answers.
 */
export type QuestionKind = 'choice' | 'subjective';
/** A subjective answer is at most this many characters (the backend's MAX_TEXT_ANSWER). */
export const MAX_TEXT_ANSWER = 10_000;

export type AttemptSession = {
  attempt: { id: string; set_id: number | null; status: 'in_progress' | 'submitted' | 'expired';
             started_at: number; deadline_at: number | null; paused_at: number | null };
  server_now: number;
  set: { name: string; topic: string; subtopic: string | null };
  questions: { id: number; kind: QuestionKind; prompt: string;
               options: { id: number; body: string }[] }[];  // display order; options [] for subjective
  selections: Record<string, number[]>;   // question id (string key) → option ids
  texts: Record<string, string>;          // question id (string key) → typed answer; blank ones absent
};

export type Results = {
  attempt: { id: string; status: 'submitted' | 'expired'; started_at: number; finished_at: number;
             score: number; max_score: number };
  // negative_marking for every attempt started now; the other two only on older attempts.
  set: { id: number | null; name: string; topic: string;
         scoring_policy: 'negative_marking' | 'all_or_nothing' | 'partial'; reveal_answers: boolean };
  questions: (ChoiceResult | SubjectiveResult)[];
};
type ResultBase = { id: number; prompt: string;
                    explanation: string | null };                   // null when !reveal_answers
export type ChoiceResult = ResultBase & {
  kind: 'choice'; points: number; awarded_points: number; is_correct: boolean;
  options: { id: number; body: string; selected: boolean; correct: boolean | null }[];  // correct null when !reveal_answers
};
/** Never marked: no points of any kind. The solver's own text always; the model answer only when revealed. */
export type SubjectiveResult = ResultBase & {
  kind: 'subjective'; points: null; awarded_points: null; is_correct: null; options: [];
  text_answer: string | null;                                       // null when left blank
  model_answer: string | null;                                      // null when !reveal_answers
};

export type History = { attempts: { id: string; set_id: number | null; name: string; topic: string;
  status: 'in_progress' | 'submitted' | 'expired'; started_at: number; finished_at: number | null;
  score: number | null; max_score: number | null }[] };            // newest first

/** Who may see a published set: public = anyone may View it and solvers may take it; private = admins only. */
export type Visibility = 'public' | 'private';

export type AdminSets = { sets: { id: number; topic: string; name: string; status: 'draft' | 'published' | 'archived';
  visibility: Visibility; question_count: number; attempt_count: number }[] };

export type AdminSetDetail = {
  id: number; name: string; topic: string; subtopic: string | null;
  status: 'draft' | 'published' | 'archived'; seq: number; question_count: number;
  difficulty: 'easy' | 'medium' | 'hard' | null; style: 'standard' | 'scenario';
  title: string | null; description: string | null;
  time_limit_minutes: number | null; scoring_policy: 'all_or_nothing' | 'partial';
  max_attempts: number | null;
  shuffle_questions: boolean; shuffle_options: boolean; reveal_answers: boolean;
  visibility: Visibility;
  questions: AdminQuestion[];
};
/** A question in its import shape, so the editor can send it straight back. */
export type AdminQuestion =
  | { type: 'choice'; prompt: string; explanation: string | null; points: number;
      options: { body: string; correct: boolean }[] }
  | { type: 'subjective'; prompt: string; explanation: string | null; model_answer: string };

// Small route responses the contract table gives inline.
export type SubmitResult = { attempt_id: string; status: AttemptSession['attempt']['status'] };
export type ImportResult = { id: number; name: string };
export type SetStatusResult = { id: number; status: AdminSets['sets'][number]['status'] };
export type SetVisibilityResult = { id: number; visibility: Visibility };

// The signed-out reads (GET /quiz/api/public/*): published, public sets only; nothing of any person.
/** A card as anyone may see it: SetCard without the reader's own last score and open attempt. */
export type PublicSetCard = Omit<SetCard, 'last' | 'open_attempt'>;
export type PublicTopicsResponse = { topics: Topics<PublicSetCard> };
/** One set for View: questions in authored order with the answer key, never a score or points. */
export type PublicSet = {
  set: { id: number; name: string; topic: string; subtopic: string | null; description: string | null;
         time_limit_minutes: number | null; question_count: number; reveal_answers: boolean };
  questions: { id: number; kind: QuestionKind; prompt: string;
               explanation: string | null;                                     // null when !reveal_answers
               model_answer: string | null;                                    // subjective only; null when !reveal_answers
               options: { id: number; body: string; correct: boolean | null }[] }[];  // correct null when !reveal_answers; [] for subjective
};
