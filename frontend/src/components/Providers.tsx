'use client';

import type { ReactNode } from 'react';
import { LiveRegionProvider } from './ui/LiveRegion';

interface ProvidersProps {
  children: ReactNode;
}

/**
 * Client-side providers wrapper for the application.
 * Includes accessibility features like live region announcements.
 */
export function Providers({ children }: ProvidersProps) {
  return (
    <LiveRegionProvider>
      {children}
    </LiveRegionProvider>
  );
}
