import Markdown from './Markdown';

/**
 * A subjective question's authored model answer, on results and on View: Markdown, in the
 * green that marks the answer key. Never a score: subjective questions are not marked.
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
