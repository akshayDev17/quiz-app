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

// The AI evaluators of written answers: admin only (/quiz/api/admin/evaluators…, ADR 0011).
/** A value a provider needs for a key or a billing credential. Secret ones are never sent back. */
export type EvaluatorField = { name: string; label: string; secret: boolean; placeholder: string; help: string };
export type EvaluatorProvider = { id: string; label: string; key_fields: EvaluatorField[];
  /** The optional read-only billing credential that lets "check now" read the provider's own budget. */
  billing: { label: string; fields: EvaluatorField[] } | null;
  /** What the page can say about money for this provider. */
  balance_note: string };
/** The provider's own budget figures, as last read by "check now". `remaining` can be negative. */
export type ProviderBudget = { limit: number; spent: number; remaining: number; currency: string; source: string;
  as_of: number | null };
export type EvaluatorKeyState = 'ready' | 'out_of_credit' | 'key_refused' | 'unreadable';
/** A stored key: never its value, only what identifies it. */
export type EvaluatorKey = { id: number; provider: string; provider_label: string; label: string;
  /** The key's last four characters, e.g. "…a1b2"; '' when too short to show any. */
  hint: string;
  /** The non-secret values, e.g. { region: 'us-east-1' }. */
  settings: Record<string, string>;
  billing: { settings: Record<string, string> } | null;
  state: EvaluatorKeyState; problem: string | null;
  unusable_since: number | null; retry_at: number | null;
  checked_at: number | null; check_result: string | null;
  reads_balance: boolean; provider_budget: ProviderBudget | null; provider_budget_error: string | null;
  /** The app's tracked spend this month, every entry of the key plus its checks. */
  spent_usd: number; entries: number; created_at: number };
export type EvaluatorEntry = { id: number; key_id: number; key_label: string; provider: string; provider_label: string;
  model: string; position: number;
  /** false (with `problem`) when its key cannot be used now or its cap is reached: marking passes it over. */
  usable: boolean; problem: string | null;
  /** The app's own tracking for `month`; the cap is optional (null: none). */
  monthly_cap_usd: number | null; spent_usd: number; left_of_cap_usd: number | null;
  provider_budget: ProviderBudget | null;
  input_price_per_mtok: number; output_price_per_mtok: number };
export type PricePreset = { provider: string; model: string; input_price_per_mtok: number;
  output_price_per_mtok: number; source: string };
export type AdminEvaluators = {
  month: string;                        // UTC 'YYYY-MM' the spend is for
  key_storage: { ready: boolean; secret: string };
  providers: EvaluatorProvider[];
  keys: EvaluatorKey[];
  entries: EvaluatorEntry[];            // in routing order: marking takes the first that can take the call
  defaults: { monthly_cap_usd: number };
  price_presets: PricePreset[];
  queue: { awaiting: number; flagged: number; awaiting_reasons: Record<string, number> };
  quotas: { per_user_daily: number; global_daily: number; calls_today: number };
  /** Present on the reply to "check now". */
  check?: { key_id: number; result: string; provider_budget_error: string | null };
};
export type EntryFields = { monthly_cap_usd: number | null; input_price_per_mtok: number; output_price_per_mtok: number };
export type NewKey = { provider: string; label: string; fields: Record<string, string>;
  billing?: Record<string, string> | null };
/** A key's change: any of a new label, the whole key again, or the billing credential (null removes it). */
export type KeyUpdate = { label?: string; fields?: Record<string, string>; billing?: Record<string, string> | null };
export type RerunResult = { attempts_tried: number; still_awaiting: number };
