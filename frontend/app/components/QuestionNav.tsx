/**
 * The question grid beside the play card: filled = answered, ringed = current, plain = neither.
 * Any button jumps straight to its question.
 */
export default function QuestionNav({
  answered,
  current,
  onJump,
}: {
  /** One entry per question, in display order. */
  answered: boolean[];
  current: number;
  onJump: (index: number) => void;
}) {
  return (
    <aside className="card qnav">
      <div className="mc">Questions</div>
      <div className="grid">
        {answered.map((isAnswered, i) => (
          <button
            key={i}
            className={[isAnswered && 'ans', i === current && 'cur'].filter(Boolean).join(' ')}
            aria-label={`Question ${i + 1}${isAnswered ? ', answered' : ''}`}
            aria-current={i === current ? 'step' : undefined}
            onClick={() => onJump(i)}
          >
            {i + 1}
          </button>
        ))}
      </div>
      <div className="mc" style={{ letterSpacing: '.04em', textTransform: 'none', lineHeight: 1.6 }}>
        Filled — answered<br />Ringed — current<br />Keys 1–9 toggle
      </div>
    </aside>
  );
}
