/** "Submit your answers?" — lists what is still unanswered before the reader commits. */
export default function ConfirmDialog({
  total,
  unanswered,
  blankWritten = [],
  onConfirm,
  onCancel,
}: {
  total: number;
  /** Labels of the unanswered choice questions, e.g. `["Q4", "Q11"]`: each costs −2. */
  unanswered: string[];
  /**
   * Labels of the subjective questions left blank. A blank written answer scores 0 (written
   * answers are never negative), so it is not counted as unanswered; they are named so none is
   * skipped by mistake.
   */
  blankWritten?: string[];
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const answered = total - unanswered.length - blankWritten.length;
  return (
    <div className="scrim on">
      <div className="card dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <h3 id="confirm-title">Submit your answers?</h3>
        <p>
          You’ve answered {answered} of {total}.
          {unanswered.length > 0 && (
            <>
              {' '}<b>{unanswered.length} unanswered</b> ({unanswered.join(', ')}).
            </>
          )}
          {blankWritten.length > 0 && (
            <>
              {' '}Written {blankWritten.length === 1 ? 'answer' : 'answers'} left blank ({blankWritten.join(', ')}):
              {blankWritten.length === 1 ? ' it scores' : ' they score'} 0, but never cost marks.
            </>
          )}
          <br />
          <br />
          Once you submit, you can’t change your answers.
        </p>
        <div className="row">
          <button className="btn ghost" onClick={onCancel}>Keep going</button>
          <button className="btn" onClick={onConfirm} autoFocus>Submit</button>
        </div>
      </div>
    </div>
  );
}
