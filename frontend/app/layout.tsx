import type { Metadata } from 'next';
import { Newsreader, IBM_Plex_Mono } from 'next/font/google';
// The shared theme (boot script, tokens, picker) is not bundled: site-shell
// adds it to every page's <head> at the edge (worker.js). globals.css aliases
// this app's variable names onto the shared tokens and carries the Classic
// Light fallback.
import 'highlight.js/styles/github.css';
import './globals.css';

const newsreader = Newsreader({
  subsets: ['latin'],
  style: ['normal', 'italic'],
  // Variable font (no static `weight`) with the optical-size axis, so the
  // `font-optical-sizing: auto` in globals.css has an axis to act on.
  axes: ['opsz'],
  variable: '--font-newsreader',
});

const plexMono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-plex-mono',
});

// The browser tab icon: the app's "Q" (white bowl, green tail) on the navy
// tile the site's other app icons use. Inlined as a data URI so it loads on
// every page the app serves, with no request to a path that could fall outside
// /quiz (or behind sign-in), and so browsers do not fall back to the site
// root's /favicon.ico.
const ICON =
  'data:image/svg+xml,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">' +
      '<rect width="32" height="32" rx="7" fill="#0F172A"/>' +
      '<circle cx="14.5" cy="14.5" r="8" fill="none" stroke="#fff" stroke-width="3.5"/>' +
      '<path d="M17 17l7.5 7.5" stroke="#5BC28C" stroke-width="3.5" stroke-linecap="round"/>' +
      '</svg>',
  );

export const metadata: Metadata = {
  title: 'The Quiz Room',
  description: 'Timed multiple-answer quizzes.',
  icons: { icon: { url: ICON, type: 'image/svg+xml' } },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning: site-shell's boot script sets data-theme on
    // <html> before React hydrates, so the exported markup never carries it.
    <html lang="en" className={`${newsreader.variable} ${plexMono.variable}`} suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
