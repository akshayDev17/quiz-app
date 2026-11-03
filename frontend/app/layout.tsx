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

export const metadata: Metadata = {
  title: 'The Quiz Room',
  description: 'Timed multiple-answer quizzes.',
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
