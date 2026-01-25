'use client';

/**
 * Tooltip Component
 * =================
 *
 * A lightweight, accessible tooltip component for displaying contextual help
 * throughout the Conference Contrarian UI.
 *
 * Features:
 * - Keyboard accessible (shows on focus)
 * - Touch friendly (tap to toggle on mobile)
 * - ARIA compliant
 * - Positioned to avoid viewport edges
 * - Customizable delay and positioning
 *
 * @example
 * ```tsx
 * <Tooltip content="Spread is the point handicap given to the underdog">
 *   <span>-7.5</span>
 * </Tooltip>
 *
 * <InfoTooltip content="Points per 100 possessions, adjusted for opponent" />
 * ```
 */

import { useState, useRef, useEffect, ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface TooltipProps {
  /** The content to display in the tooltip */
  content: ReactNode;
  /** The element that triggers the tooltip */
  children: ReactNode;
  /** Position relative to trigger element */
  position?: 'top' | 'bottom' | 'left' | 'right';
  /** Delay before showing tooltip (ms) */
  delay?: number;
  /** Additional class names for the tooltip */
  className?: string;
  /** Maximum width of tooltip */
  maxWidth?: number;
}

export function Tooltip({
  content,
  children,
  position = 'top',
  delay = 300,
  className,
  maxWidth = 250,
}: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [isTouchDevice, setIsTouchDevice] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const triggerRef = useRef<HTMLSpanElement>(null);

  // Detect touch device
  useEffect(() => {
    setIsTouchDevice('ontouchstart' in window);
  }, []);

  const showTooltip = () => {
    timeoutRef.current = setTimeout(() => {
      setIsVisible(true);
    }, delay);
  };

  const hideTooltip = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    setIsVisible(false);
  };

  const toggleTooltip = () => {
    if (isTouchDevice) {
      setIsVisible(!isVisible);
    }
  };

  // Position classes
  const positionClasses = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  };

  // Arrow classes
  const arrowClasses = {
    top: 'top-full left-1/2 -translate-x-1/2 border-l-transparent border-r-transparent border-b-transparent border-t-gray-800',
    bottom: 'bottom-full left-1/2 -translate-x-1/2 border-l-transparent border-r-transparent border-t-transparent border-b-gray-800',
    left: 'left-full top-1/2 -translate-y-1/2 border-t-transparent border-b-transparent border-r-transparent border-l-gray-800',
    right: 'right-full top-1/2 -translate-y-1/2 border-t-transparent border-b-transparent border-l-transparent border-r-gray-800',
  };

  return (
    <span
      ref={triggerRef}
      className="relative inline-flex"
      onMouseEnter={!isTouchDevice ? showTooltip : undefined}
      onMouseLeave={!isTouchDevice ? hideTooltip : undefined}
      onFocus={showTooltip}
      onBlur={hideTooltip}
      onClick={toggleTooltip}
    >
      {children}
      {isVisible && (
        <span
          role="tooltip"
          className={cn(
            'absolute z-50 px-3 py-2 text-sm bg-gray-800 text-gray-200 rounded-lg shadow-lg',
            'animate-in fade-in-0 zoom-in-95 duration-200',
            positionClasses[position],
            className
          )}
          style={{ maxWidth }}
        >
          {content}
          {/* Arrow */}
          <span
            className={cn(
              'absolute w-0 h-0 border-4',
              arrowClasses[position]
            )}
          />
        </span>
      )}
    </span>
  );
}

/**
 * InfoTooltip Component
 * =====================
 *
 * A small info icon that displays a tooltip on hover/focus/tap.
 * Useful for adding contextual help next to labels and values.
 */

interface InfoTooltipProps {
  /** The help text to display */
  content: ReactNode;
  /** Position relative to icon */
  position?: 'top' | 'bottom' | 'left' | 'right';
  /** Size of the info icon */
  size?: 'sm' | 'md';
  /** Link to help page section (optional) */
  helpLink?: string;
}

export function InfoTooltip({
  content,
  position = 'top',
  size = 'sm',
  helpLink,
}: InfoTooltipProps) {
  const sizeClasses = {
    sm: 'w-3.5 h-3.5',
    md: 'w-4 h-4',
  };

  const tooltipContent = helpLink ? (
    <span>
      {content}
      <a
        href={helpLink}
        className="block mt-1 text-blue-400 hover:underline text-xs"
        onClick={(e) => e.stopPropagation()}
      >
        Learn more &rarr;
      </a>
    </span>
  ) : (
    content
  );

  return (
    <Tooltip content={tooltipContent} position={position}>
      <button
        type="button"
        className="inline-flex items-center justify-center text-gray-500 hover:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 focus:ring-offset-gray-900 rounded-full"
        aria-label="More information"
      >
        <svg
          className={sizeClasses[size]}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      </button>
    </Tooltip>
  );
}

/**
 * Betting Term Definitions
 * ========================
 *
 * Pre-defined tooltips for common betting terminology used throughout the app.
 * These can be imported and used consistently across components.
 */

export const BETTING_TERMS = {
  spread: {
    content: 'The point handicap. Favorites must win by more than this number to cover.',
    helpLink: '/help#spreads',
  },
  moneyline: {
    content: 'Odds for a straight-up win. Negative = favorite (risk more to win less). Positive = underdog.',
    helpLink: '/help#moneylines',
  },
  total: {
    content: 'Over/Under: The combined score of both teams. Bet on whether the total will be higher or lower.',
    helpLink: '/help#totals',
  },
  edge: {
    content: 'Your advantage over the market. Edge = Your win probability - 50%. Higher edge = more confidence.',
    helpLink: '/help#edge',
  },
  confidence: {
    content: 'Model conviction level. HIGH (>4% edge), MEDIUM (2-4%), LOW (<2%), PASS (no edge).',
    helpLink: '/help#confidence',
  },
  adjEM: {
    content: 'KenPom Adjusted Efficiency Margin. Expected point differential vs average team per 100 possessions.',
    helpLink: '/help#kenpom',
  },
  adjO: {
    content: 'KenPom Adjusted Offense. Points scored per 100 possessions, adjusted for opponent quality.',
    helpLink: '/help#kenpom',
  },
  adjD: {
    content: 'KenPom Adjusted Defense. Points allowed per 100 possessions. Lower is better!',
    helpLink: '/help#kenpom',
  },
  allPlay: {
    content: 'Haslametrics All-Play %. Probability of beating an average D1 team on a neutral court.',
    helpLink: '/help#haslametrics',
  },
  momentum: {
    content: 'Haslametrics trend indicator. Positive = team improving, negative = declining performance.',
    helpLink: '/help#haslametrics',
  },
  quadrant: {
    content: 'NET quadrant records. Q1 = elite opponents, Q4 = weakest. Strong Q1 = tournament quality.',
    helpLink: '/help#haslametrics',
  },
} as const;

/**
 * TermTooltip Component
 * =====================
 *
 * Convenience component for displaying predefined betting term tooltips.
 */

interface TermTooltipProps {
  term: keyof typeof BETTING_TERMS;
  position?: 'top' | 'bottom' | 'left' | 'right';
}

export function TermTooltip({ term, position = 'top' }: TermTooltipProps) {
  const termData = BETTING_TERMS[term];
  return (
    <InfoTooltip
      content={termData.content}
      helpLink={termData.helpLink}
      position={position}
    />
  );
}
