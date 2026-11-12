/** Heading for a topic's group of sets; the null group holds sets with no subtopic. */
export function subtopicGroupLabel(subtopic: { name: string } | null): string {
  return subtopic ? subtopic.name : 'Whole course';
}

/** `1 question`, `2 questions`; pass `plural` for irregular words (`quiz`, `quizzes`). */
export function pluralize(n: number, word: string, plural = `${word}s`): string {
  return `${n} ${n === 1 ? word : plural}`;
}
