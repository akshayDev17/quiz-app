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
  subjective_count: number;  // of question_count, how many are subjective (marked 0–4 by the AI evaluator)
  max_attempts: number | null; attempts_used: number; open_attempt_id: string | null };

/**
 * A choice question is answered by ticking options and marked +2 / −1 / −2 blank; a subjective one
 * is answered by typing into a text box and marked 0–4 by the AI evaluator against its authored
 * model answer, never below 0 (a blank one scores 0). The model answer is shown on review when the
 * set reveals answers.
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
             score: number; max_score: number;
             /** Written answers still awaiting the evaluator: until 0 the score is provisional. */
             awaiting_count: number };
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
/**
 * How a written answer stands: `blank` (0), `awaiting` the evaluator (counts nothing yet),
 * `marked` by the evaluator, or `flagged` for review (0). `null`, with no points, only on an
 * attempt started before written answers were marked. Never who or what marked it.
 */
export type WrittenEvaluation = 'blank' | 'awaiting' | 'marked' | 'flagged';
/** The solver's own text always; the model answer only when revealed. */
export type SubjectiveResult = ResultBase & {
  kind: 'subjective'; is_correct: null; options: [];
  points: number | null;                                            // out of; null when not marked
  awarded_points: number | null;                                    // null while awaiting, or not marked
  evaluation: WrittenEvaluation | null;
  feedback: string | null;                                          // the evaluator's, when marked
  text_answer: string | null;                                       // null when left blank
  model_answer: string | null;                                      // null when !reveal_answers
};

export type History = { attempts: { id: string; set_id: number | null; name: string; topic: string;
  status: 'in_progress' | 'submitted' | 'expired'; started_at: number; finished_at: number | null;
  score: number | null; max_score: number | null;
  awaiting_count: number }[] };                                    // newest first

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
  | { type: 'subjective'; prompt: string; explanation: string | null; model_answer: string;
      /** The authored rubric: the essential points the evaluator checks. Absent when none. */
      key_points?: string[] };

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

// The AI evaluators of written answers: admin only (GET/POST/PUT/DELETE /quiz/api/admin/evaluators…).
export type EvaluatorProvider = { id: string; label: string;
  /** Worker secret names this provider needs; values are never sent. */
  secrets: string[]; usable: boolean };
export type EvaluatorModel = { id: number; provider: string; provider_label: string; model: string; position: number;
  /** false when its provider's secrets are missing: it is skipped. */
  usable: boolean;
  /** The app's own tracked spend for `month`, not the provider's billing figure. */
  monthly_budget_usd: number; spent_usd: number; remaining_usd: number;
  input_price_per_mtok: number; output_price_per_mtok: number };
export type PricePreset = { provider: string; model: string; input_price_per_mtok: number;
  output_price_per_mtok: number; source: string };
export type AdminEvaluators = {
  month: string;                        // UTC 'YYYY-MM' the spend is for
  providers: EvaluatorProvider[];
  models: EvaluatorModel[];             // in routing order: the first usable one with budget left marks
  price_presets: PricePreset[];
  queue: { awaiting: number; flagged: number; awaiting_reasons: Record<string, number> };
  quotas: { per_user_daily: number; global_daily: number; calls_today: number };
};
export type EvaluatorFields = { monthly_budget_usd: number; input_price_per_mtok: number; output_price_per_mtok: number };
export type RerunResult = { attempts_tried: number; still_awaiting: number };
