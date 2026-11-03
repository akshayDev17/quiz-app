// <site-slot>: a place site-shell (akshayDev17/site-themes, shell/) fills at the
// edge from the site's app list. The element stays; only its content is replaced,
// so what the app renders inside it is the fallback.
import type { DetailedHTMLProps, HTMLAttributes } from 'react';

declare module 'react' {
  namespace JSX {
    interface IntrinsicElements {
      'site-slot': DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement> & {
        /** Which slot: "site-path" (the site path switcher) or "site-apps". */
        name: 'site-path' | 'site-apps';
        /** site-path only: the app's crumbs after its name, as JSON [{ label, href? }]. */
        'data-tail'?: string;
      };
    }
  }
}
