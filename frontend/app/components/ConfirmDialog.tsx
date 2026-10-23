/** "Submit your answers?" — lists what is still unanswered before the reader commits. */
export default function ConfirmDialog({
  total,
  unanswered,
  onConfirm,
  onCancel,
}: {
  total: number;
  /** Labels of the unanswered questions, e.g. `["Q4", "Q11"]`. */
  unanswered: string[];
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="scrim on">
      <div className="card dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <h3 id="confirm-title">Submit your answers?</h3>
        <p>
          You’ve answered {total - unanswered.length} of {total}.
          {unanswered.length > 0 && (
            <>
              {' '}<b>{unanswered.length} unanswered</b> ({unanswered.join(', ')}).
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
