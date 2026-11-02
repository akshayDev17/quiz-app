import type { Metadata } from 'next';
import { Newsreader, IBM_Plex_Mono } from 'next/font/google';
import { bootScript } from 'site-themes';
// The shared site themes come first: globals.css aliases this app's variable
// names to their tokens, so it must load after them.
import 'site-themes/themes.css';
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
    // suppressHydrationWarning: the boot script sets data-theme on <html> before
    // React hydrates, so the server HTML and the live element differ on purpose.
    <html lang="en" className={`${newsreader.variable} ${plexMono.variable}`} suppressHydrationWarning>
      <head>
        {/* Inline, so the theme is set before first paint with nothing fetched. */}
        <script dangerouslySetInnerHTML={{ __html: bootScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
