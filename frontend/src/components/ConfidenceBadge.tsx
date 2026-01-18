'use client';

import type { ConfidenceTier } from '@/lib/types';

interface ConfidenceBadgeProps {
  tier: ConfidenceTier | null;
  showLabel?: boolean;
}

export function ConfidenceBadge({ tier, showLabel = true }: ConfidenceBadgeProps) {
  const config = {
    high: {
      bg: 'bg-green-500/20',
      border: 'border-green-500/50',
      text: 'text-green-400',
      label: 'HIGH',
      icon: '🔥',
    },
    medium: {
      bg: 'bg-yellow-500/20',
      border: 'border-yellow-500/50',
      text: 'text-yellow-400',
      label: 'MED',
      icon: '⚡',
    },
    low: {
      bg: 'bg-orange-500/20',
      border: 'border-orange-500/50',
      text: 'text-orange-400',
      label: 'LOW',
      icon: '📊',
    },
    pass: {
      bg: 'bg-gray-500/20',
      border: 'border-gray-500/50',
      text: 'text-gray-400',
      label: 'PASS',
      icon: '⏸️',
    },
  };

  const c = tier ? config[tier] : config.pass;

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border ${c.bg} ${c.border} ${c.text}`}
    >
      <span>{c.icon}</span>
      {showLabel && <span>{c.label}</span>}
    </span>
  );
}
