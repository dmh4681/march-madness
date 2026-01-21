'use client';

import { createContext, useContext, useState, useCallback, useRef, useEffect, type ReactNode } from 'react';

interface LiveRegionContextType {
  announce: (message: string, priority?: 'polite' | 'assertive') => void;
}

const LiveRegionContext = createContext<LiveRegionContextType | null>(null);

/**
 * Provider for screen reader live announcements.
 * Wrap your app or layout with this to enable announcements via the useAnnounce hook.
 */
export function LiveRegionProvider({ children }: { children: ReactNode }) {
  const [politeMessage, setPoliteMessage] = useState('');
  const [assertiveMessage, setAssertiveMessage] = useState('');
  const politeTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const assertiveTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const announce = useCallback((message: string, priority: 'polite' | 'assertive' = 'polite') => {
    if (priority === 'assertive') {
      // Clear existing timeout
      if (assertiveTimeoutRef.current) {
        clearTimeout(assertiveTimeoutRef.current);
      }
      // Set message then clear after screen reader has time to read it
      setAssertiveMessage(message);
      assertiveTimeoutRef.current = setTimeout(() => {
        setAssertiveMessage('');
      }, 1000);
    } else {
      if (politeTimeoutRef.current) {
        clearTimeout(politeTimeoutRef.current);
      }
      setPoliteMessage(message);
      politeTimeoutRef.current = setTimeout(() => {
        setPoliteMessage('');
      }, 1000);
    }
  }, []);

  // Cleanup timeouts on unmount
  useEffect(() => {
    return () => {
      if (politeTimeoutRef.current) clearTimeout(politeTimeoutRef.current);
      if (assertiveTimeoutRef.current) clearTimeout(assertiveTimeoutRef.current);
    };
  }, []);

  return (
    <LiveRegionContext.Provider value={{ announce }}>
      {children}
      {/* Polite announcements - wait for user to finish current task */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {politeMessage}
      </div>
      {/* Assertive announcements - interrupt immediately for important updates */}
      <div
        role="alert"
        aria-live="assertive"
        aria-atomic="true"
        className="sr-only"
      >
        {assertiveMessage}
      </div>
    </LiveRegionContext.Provider>
  );
}

/**
 * Hook to announce messages to screen readers.
 * @returns Object with announce function
 *
 * @example
 * const { announce } = useAnnounce();
 * announce('Odds updated: Kansas -3.5');
 * announce('Error loading data', 'assertive');
 */
export function useAnnounce(): LiveRegionContextType {
  const context = useContext(LiveRegionContext);
  if (!context) {
    // Return a no-op if provider is not present (for SSR or non-wrapped components)
    return { announce: () => {} };
  }
  return context;
}
