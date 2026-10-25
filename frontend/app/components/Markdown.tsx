import ReactMarkdown from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';
import remarkGfm from 'remark-gfm';

/**
 * Renders quiz content (prompts, options, explanations) as Markdown.
 *
 * Code fences are highlighted with GitHub Light: `rehype-highlight` tags the `<code>`
 * with `hljs` plus `hljs-*` token classes, and `highlight.js/styles/github.css` (loaded
 * in `layout.tsx`) colours them. `detect` is on because imported quiz JSON does not
 * always tag its fences; an explicit fence language still wins over detection.
 *
 * There is deliberately no `rehype-raw`: raw HTML in the source is shown as text, never parsed
 * into elements, so an author (or an imported file) cannot inject markup or script.
 */
export default function Markdown({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
    >
      {text}
    </ReactMarkdown>
  );
}
