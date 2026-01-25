'use client';

/**
 * ConfidenceBadge Component
 * =========================
 *
 * Displays a visual indicator of betting confidence based on model predictions.
 * The badge communicates both the confidence level and the underlying edge
 * calculation to help users make informed betting decisions.
 *
 * Confidence Tier Calculation
 * ===========================
 *
 * Confidence tiers are derived from the model's predicted cover probability
 * and the implied edge over fair market odds.
 *
 * **Edge Formula:**
 *   edge = |P(cover) - 0.50| × 100%
 *
 * This represents how far our prediction deviates from a coin flip (50%).
 *
 * **Tier Assignment:**
 *
 * | Tier   | Edge Range | P(cover) Range | Interpretation                    |
 * |--------|------------|----------------|-----------------------------------|
 * | HIGH   | > 4%       | > 54% or < 46% | Strong conviction, clear value    |
 * | MEDIUM | 2-4%       | 52-54%         | Moderate edge, standard bet size  |
 * | LOW    | < 2%       | 50-52%         | Marginal edge, proceed cautiously |
 * | PASS   | n/a        | ~50%           | No edge detected, skip this game  |
 *
 * ROI Implications
 * ================
 *
 * At standard -110 odds, breakeven win rate is 52.4%.
 *
 * **Expected ROI by Tier (theoretical):**
 *
 * | Tier   | Win Rate | Expected ROI |
 * |--------|----------|--------------|
 * | HIGH   | ~55-60%  | +5% to +14%  |
 * | MEDIUM | ~53-55%  | +1% to +5%   |
 * | LOW    | ~51-53%  | -3% to +1%   |
 * | PASS   | ~50%     | -4.5%        |
 *
 * Note: These are expected long-term returns assuming proper bankroll
 * management. Short-term variance can be significant.
 *
 * Bet Sizing Recommendations
 * ==========================
 *
 * Using Kelly Criterion-inspired sizing:
 *
 * | Tier   | Suggested Unit Size | Example ($100 unit) |
 * |--------|---------------------|---------------------|
 * | HIGH   | 1.5-2 units         | $150-$200           |
 * | MEDIUM | 1 unit              | $100                |
 * | LOW    | 0.5 units           | $50                 |
 * | PASS   | 0 units             | $0 (no bet)         |
 *
 * Accessibility Features
 * ======================
 *
 * - WCAG AA color contrast compliance (minimum 4.5:1 ratio)
 * - ARIA labels for screen reader support
 * - Color-blind friendly patterns (optional)
 * - High contrast mode classes for OS-level settings
 * - Touch-friendly sizing on mobile (44px minimum)
 *
 * @example
 * ```tsx
 * // Basic usage
 * <ConfidenceBadge tier="high" />
 *
 * // Without label (icon only)
 * <ConfidenceBadge tier="medium" showLabel={false} />
 *
 * // Touch-friendly size for mobile
 * <ConfidenceBadge tier="low" size="touch" />
 *
 * // With accessibility ID
 * <ConfidenceBadge tier="high" id="game-123-confidence" />
 * ```
 */

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

/**
 * Color Configuration
 * ===================
 *
 * Colors are chosen for both aesthetics and accessibility:
 *
 * WCAG AA Contrast Ratios (text on #0a0a0a dark background):
 * - High (Green #4ade80): 8.5:1 ratio - Excellent
 * - Medium (Yellow #facc15): 12.6:1 ratio - Excellent
 * - Low (Orange #fb923c): 7.2:1 ratio - Good
 * - Pass (Gray #9ca3af): 5.4:1 ratio - Passes AA
 *
 * Color Psychology:
 * - Green: Positive, go signal, confidence
 * - Yellow: Caution, attention, moderate
 * - Orange: Warning, lower confidence
 * - Gray: Neutral, no action needed
 */
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
