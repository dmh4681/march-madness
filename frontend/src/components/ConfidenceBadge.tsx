'use client';

import type { ConfidenceTier } from '@/lib/types';
import { cn } from '@/lib/utils';

interface ConfidenceBadgeProps {
  tier: ConfidenceTier | null;
  showLabel?: boolean;
  size?: 'default' | 'touch';
  /** Optional ID for aria-describedby references */
  id?: string;
  /** Enable color-blind friendly patterns (defaults to true) */
  showPattern?: boolean;
}

// WCAG AA compliant colors (4.5:1 contrast ratio on dark backgrounds)
// High: #4ade80 on #0a0a0a = 8.5:1
// Medium: #facc15 on #0a0a0a = 12.6:1
// Low: #fb923c on #0a0a0a = 7.2:1
// Pass: #9ca3af on #0a0a0a = 5.4:1
const config = {
  high: {
    bg: 'bg-green-500/20',
    border: 'border-green-400',
    text: 'text-green-400',
    label: 'HIGH',
    fullLabel: 'High confidence',
    icon: '🔥',
    // SVG pattern for color-blind users (upward triangle = positive)
    pattern: 'confidence-pattern-high',
    // High contrast mode class
    hcClass: 'confidence-high',
  },
  medium: {
    bg: 'bg-yellow-500/20',
    border: 'border-yellow-400',
    text: 'text-yellow-400',
    label: 'MED',
    fullLabel: 'Medium confidence',
    icon: '⚡',
    pattern: 'confidence-pattern-medium',
    hcClass: 'confidence-medium',
  },
  low: {
    bg: 'bg-orange-500/20',
    border: 'border-orange-400',
    text: 'text-orange-400',
    label: 'LOW',
    fullLabel: 'Low confidence',
    icon: '📊',
    pattern: 'confidence-pattern-low',
    hcClass: 'confidence-low',
  },
  pass: {
    bg: 'bg-gray-500/20',
    border: 'border-gray-400',
    text: 'text-gray-400',
    label: 'PASS',
    fullLabel: 'No recommendation',
    icon: '⏸️',
    pattern: 'confidence-pattern-pass',
    hcClass: 'confidence-pass',
  },
};

export function ConfidenceBadge({
  tier,
  showLabel = true,
  size = 'default',
  id,
  showPattern = true
}: ConfidenceBadgeProps) {
  const c = tier ? config[tier] : config.pass;
  const ariaLabel = `Confidence level: ${c.fullLabel}`;

  return (
    <span
      id={id}
      role="status"
      aria-label={ariaLabel}
      className={cn(
        "inline-flex items-center gap-1 rounded text-xs font-medium border",
        c.bg, c.border, c.text, c.hcClass,
        // Apply color-blind friendly pattern
        showPattern && c.pattern,
        // Touch-friendly sizing: 44px min height on mobile, normal on desktop
        size === 'touch'
          ? "px-3 py-2 min-h-[44px] sm:px-2 sm:py-0.5 sm:min-h-0"
          : "px-2.5 py-1 min-h-[32px] sm:px-2 sm:py-0.5 sm:min-h-0"
      )}
    >
      {/* Icon hidden from screen readers since aria-label provides context */}
      <span aria-hidden="true">{c.icon}</span>
      {showLabel && <span>{c.label}</span>}
    </span>
  );
}

/** Helper to get confidence tier description for screen readers */
export function getConfidenceDescription(tier: ConfidenceTier | null): string {
  return tier ? config[tier].fullLabel : config.pass.fullLabel;
}
