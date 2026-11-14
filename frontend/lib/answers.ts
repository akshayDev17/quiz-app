import { MAX_TEXT_ANSWER, type AttemptSession, type ChoiceResult, type SubjectiveResult } from './types.ts';

type Question = Pick<AttemptSession['questions'][number], 'id' | 'kind'>;
/** Ticked option ids per question id. */
export type Picks = Record<number, number[]>;
/** Typed text per question id. */
export type Texts = Record<number, string>;

/**
 * Whether a question has an answer: a ticked option for a choice question, text that is not
 * all whitespace for a subjective one (the server stores whitespace-only text as blank).
 */
export function isAnswered(q: Question, picks: Picks, texts: Texts): boolean {
  if (q.kind === 'subjective') return (texts[q.id] ?? '').trim() !== '';
  return (picks[q.id]?.length ?? 0) > 0;
}

/**
 * The blanks the submit confirmation names, as labels in display order ("Q4").
 *
 * `unanswered` holds only choice questions: each costs −2 when left blank. A blank subjective
 * question scores 0 and never costs marks (written answers are never negative), so it goes in
 * `blankWritten` instead and is never counted as unanswered.
 */
export function blanks(questions: Question[], picks: Picks, texts: Texts): { unanswered: string[]; blankWritten: string[] } {
  const unanswered: string[] = [];
  const blankWritten: string[] = [];
  questions.forEach((q, i) => {
    if (isAnswered(q, picks, texts)) return;
    (q.kind === 'subjective' ? blankWritten : unanswered).push(`Q${i + 1}`);
  });
  return { unanswered, blankWritten };
}

/** A submitted question as far as whether it was answered: its ticks, or its typed text. */
type ResultAnswer =
  | { kind: 'choice'; options: Pick<ChoiceResult['options'][number], 'selected'>[] }
  | Pick<SubjectiveResult, 'kind' | 'text_answer'>;

/**
 * How many questions of a submitted attempt were left blank, for the results header: a choice
 * question with nothing ticked (it cost −2) and a written one with no text (it scored 0, never
 * less). The server sends a blank written answer's text as null; whitespace counts as blank too.
 */
export function countUnanswered(questions: ResultAnswer[]): number {
  return questions.filter((q) =>
    q.kind === 'subjective' ? (q.text_answer ?? '').trim() === '' : !q.options.some((o) => o.selected),
  ).length;
}

/** Input types that take typed text; a checkbox or button does not. */
const NON_TEXT_INPUTS = new Set(['checkbox', 'radio', 'button', 'submit', 'reset', 'range', 'color', 'file', 'image']);

/**
 * Whether a key event's target is a place the solver types into (a textarea, a text input, a
 * select or editable content). The play page's shortcuts (1–9 toggle options, arrows change
 * question) stand down there, so a digit or an arrow key stays in the text being written.
 * A focused option checkbox is not one: the shortcuts keep working after a click.
 */
export function isTypingTarget(target: EventTarget | null): boolean {
  if (!target || typeof target !== 'object') return false;
  const el = target as { tagName?: unknown; type?: unknown; isContentEditable?: unknown };
  if (el.isContentEditable === true) return true;
  const tag = typeof el.tagName === 'string' ? el.tagName.toUpperCase() : '';
  if (tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (tag !== 'INPUT') return false;
  return !NON_TEXT_INPUTS.has(typeof el.type === 'string' ? el.type.toLowerCase() : 'text');
}

/** Within this many characters of the limit, the text box shows how many are used. */
export const COUNTER_FROM = MAX_TEXT_ANSWER - 1_000;

/** "9,512 / 10,000" once a typed answer nears the limit; empty before that. */
export function textCounter(length: number): string {
  if (length < COUNTER_FROM) return '';
  return `${length.toLocaleString('en-US')} / ${MAX_TEXT_ANSWER.toLocaleString('en-US')}`;
}
