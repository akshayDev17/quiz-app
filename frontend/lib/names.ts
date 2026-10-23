/** Heading for a topic's group of sets; the null group holds sets with no subtopic. */
export function subtopicGroupLabel(subtopic: { name: string } | null): string {
  return subtopic ? subtopic.name : 'Whole course';
}

/** `1 question`, `2 questions`. Regular plurals only. */
export function pluralize(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`;
}
