import Markdown from './Markdown';

/**
 * A subjective question's authored model answer, on results and on View: Markdown, in the
 * green that marks the answer key. It is what the AI evaluator marks a written answer against.
 */
export default function ModelAnswer({ text }: { text: string }) {
  return (
    <div className="answer-block model">
      <span className="mc lab">Model answer</span>
      <div>
        <Markdown text={text} />
      </div>
    </div>
  );
}
