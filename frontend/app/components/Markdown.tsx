import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Renders quiz content (prompts, options, explanations) as Markdown.
 *
 * There is deliberately no `rehype-raw`: raw HTML in the source is shown as text, never parsed
 * into elements, so an author (or an imported file) cannot inject markup or script.
 */
export default function Markdown({ text }: { text: string }) {
  return <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>;
}
