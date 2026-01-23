import { render, screen } from '@testing-library/react';
import { ConfidenceBadge, getConfidenceDescription } from '@/components/ConfidenceBadge';
import type { ConfidenceTier } from '@/lib/types';

describe('ConfidenceBadge', () => {
  describe('Rendering confidence tiers', () => {
    it('renders HIGH confidence tier correctly', () => {
      render(<ConfidenceBadge tier="high" />);

      expect(screen.getByRole('status')).toBeInTheDocument();
      expect(screen.getByText('HIGH')).toBeInTheDocument();
      expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Confidence level: High confidence');
    });

    it('renders MEDIUM confidence tier correctly', () => {
      render(<ConfidenceBadge tier="medium" />);

      expect(screen.getByText('MED')).toBeInTheDocument();
      expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Confidence level: Medium confidence');
    });

    it('renders LOW confidence tier correctly', () => {
      render(<ConfidenceBadge tier="low" />);

      expect(screen.getByText('LOW')).toBeInTheDocument();
      expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Confidence level: Low confidence');
    });

    it('renders PASS tier correctly', () => {
      render(<ConfidenceBadge tier="pass" />);

      expect(screen.getByText('PASS')).toBeInTheDocument();
      expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Confidence level: No recommendation');
    });
  });

  describe('Null/undefined tier handling', () => {
    it('renders as PASS tier when tier is null', () => {
      render(<ConfidenceBadge tier={null} />);

      expect(screen.getByText('PASS')).toBeInTheDocument();
      expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Confidence level: No recommendation');
    });

    it('applies pass styling when tier is null', () => {
      render(<ConfidenceBadge tier={null} />);

      const badge = screen.getByRole('status');
      expect(badge).toHaveClass('text-gray-400');
      expect(badge).toHaveClass('border-gray-400');
    });
  });

  describe('showLabel prop', () => {
    it('shows label when showLabel is true (default)', () => {
      render(<ConfidenceBadge tier="high" />);

      expect(screen.getByText('HIGH')).toBeInTheDocument();
    });

    it('hides label when showLabel is false', () => {
      render(<ConfidenceBadge tier="high" showLabel={false} />);

      expect(screen.queryByText('HIGH')).not.toBeInTheDocument();
    });

    it('still shows icon when label is hidden', () => {
      render(<ConfidenceBadge tier="high" showLabel={false} />);

      // Icon should still be visible (hidden from screen readers with aria-hidden)
      const badge = screen.getByRole('status');
      const iconSpan = badge.querySelector('[aria-hidden="true"]');
      expect(iconSpan).toBeInTheDocument();
    });
  });

  describe('size prop', () => {
    it('applies default size classes', () => {
      render(<ConfidenceBadge tier="high" size="default" />);

      const badge = screen.getByRole('status');
      expect(badge).toHaveClass('px-2.5');
      expect(badge).toHaveClass('py-1');
      expect(badge).toHaveClass('min-h-[32px]');
    });

    it('applies touch size classes for mobile', () => {
      render(<ConfidenceBadge tier="high" size="touch" />);

      const badge = screen.getByRole('status');
      expect(badge).toHaveClass('px-3');
      expect(badge).toHaveClass('py-2');
      expect(badge).toHaveClass('min-h-[44px]');
    });
  });

  describe('id prop', () => {
    it('applies custom id when provided', () => {
      render(<ConfidenceBadge tier="high" id="custom-confidence-badge" />);

      const badge = screen.getByRole('status');
      expect(badge).toHaveAttribute('id', 'custom-confidence-badge');
    });

    it('does not apply id when not provided', () => {
      render(<ConfidenceBadge tier="high" />);

      const badge = screen.getByRole('status');
      expect(badge).not.toHaveAttribute('id');
    });
  });

  describe('showPattern prop', () => {
    it('applies pattern class when showPattern is true (default)', () => {
      render(<ConfidenceBadge tier="high" />);

      const badge = screen.getByRole('status');
      expect(badge).toHaveClass('confidence-pattern-high');
    });

    it('does not apply pattern class when showPattern is false', () => {
      render(<ConfidenceBadge tier="high" showPattern={false} />);

      const badge = screen.getByRole('status');
      expect(badge).not.toHaveClass('confidence-pattern-high');
    });

    it('applies correct pattern for each tier', () => {
      const tiers: ConfidenceTier[] = ['high', 'medium', 'low', 'pass'];
      const patterns = ['confidence-pattern-high', 'confidence-pattern-medium', 'confidence-pattern-low', 'confidence-pattern-pass'];

      tiers.forEach((tier, index) => {
        const { unmount } = render(<ConfidenceBadge tier={tier} />);
        const badge = screen.getByRole('status');
        expect(badge).toHaveClass(patterns[index]);
        unmount();
      });
    });
  });

  describe('Accessibility', () => {
    it('has correct role', () => {
      render(<ConfidenceBadge tier="high" />);

      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    it('has descriptive aria-label', () => {
      render(<ConfidenceBadge tier="medium" />);

      const badge = screen.getByRole('status');
      expect(badge).toHaveAttribute('aria-label', 'Confidence level: Medium confidence');
    });

    it('hides icon from screen readers', () => {
      render(<ConfidenceBadge tier="high" />);

      const badge = screen.getByRole('status');
      const iconSpan = badge.querySelector('[aria-hidden="true"]');
      expect(iconSpan).toBeInTheDocument();
      expect(iconSpan).toHaveAttribute('aria-hidden', 'true');
    });

    it('applies high contrast mode class', () => {
      render(<ConfidenceBadge tier="high" />);

      const badge = screen.getByRole('status');
      expect(badge).toHaveClass('confidence-high');
    });

    it('applies correct high contrast class for each tier', () => {
      const testCases: Array<{ tier: ConfidenceTier; expectedClass: string }> = [
        { tier: 'high', expectedClass: 'confidence-high' },
        { tier: 'medium', expectedClass: 'confidence-medium' },
        { tier: 'low', expectedClass: 'confidence-low' },
        { tier: 'pass', expectedClass: 'confidence-pass' },
      ];

      testCases.forEach(({ tier, expectedClass }) => {
        const { unmount } = render(<ConfidenceBadge tier={tier} />);
        const badge = screen.getByRole('status');
        expect(badge).toHaveClass(expectedClass);
        unmount();
      });
    });
  });

  describe('Styling classes', () => {
    it('applies correct color classes for HIGH tier', () => {
      render(<ConfidenceBadge tier="high" />);

      const badge = screen.getByRole('status');
      expect(badge).toHaveClass('bg-green-500/20');
      expect(badge).toHaveClass('border-green-400');
      expect(badge).toHaveClass('text-green-400');
    });

    it('applies correct color classes for MEDIUM tier', () => {
      render(<ConfidenceBadge tier="medium" />);

      const badge = screen.getByRole('status');
      expect(badge).toHaveClass('bg-yellow-500/20');
      expect(badge).toHaveClass('border-yellow-400');
      expect(badge).toHaveClass('text-yellow-400');
    });

    it('applies correct color classes for LOW tier', () => {
      render(<ConfidenceBadge tier="low" />);

      const badge = screen.getByRole('status');
      expect(badge).toHaveClass('bg-orange-500/20');
      expect(badge).toHaveClass('border-orange-400');
      expect(badge).toHaveClass('text-orange-400');
    });

    it('applies correct color classes for PASS tier', () => {
      render(<ConfidenceBadge tier="pass" />);

      const badge = screen.getByRole('status');
      expect(badge).toHaveClass('bg-gray-500/20');
      expect(badge).toHaveClass('border-gray-400');
      expect(badge).toHaveClass('text-gray-400');
    });

    it('applies common base styling classes', () => {
      render(<ConfidenceBadge tier="high" />);

      const badge = screen.getByRole('status');
      expect(badge).toHaveClass('inline-flex');
      expect(badge).toHaveClass('items-center');
      expect(badge).toHaveClass('gap-1');
      expect(badge).toHaveClass('rounded');
      expect(badge).toHaveClass('text-xs');
      expect(badge).toHaveClass('font-medium');
      expect(badge).toHaveClass('border');
    });
  });

  describe('Icons', () => {
    it('shows fire icon for HIGH tier', () => {
      render(<ConfidenceBadge tier="high" />);

      const badge = screen.getByRole('status');
      const iconSpan = badge.querySelector('[aria-hidden="true"]');
      expect(iconSpan?.textContent).toContain('\uD83D\uDD25'); // Fire emoji
    });

    it('shows lightning icon for MEDIUM tier', () => {
      render(<ConfidenceBadge tier="medium" />);

      const badge = screen.getByRole('status');
      const iconSpan = badge.querySelector('[aria-hidden="true"]');
      expect(iconSpan?.textContent).toContain('\u26A1'); // Lightning emoji
    });

    it('shows chart icon for LOW tier', () => {
      render(<ConfidenceBadge tier="low" />);

      const badge = screen.getByRole('status');
      const iconSpan = badge.querySelector('[aria-hidden="true"]');
      expect(iconSpan?.textContent).toContain('\uD83D\uDCCA'); // Chart emoji
    });

    it('shows pause icon for PASS tier', () => {
      render(<ConfidenceBadge tier="pass" />);

      const badge = screen.getByRole('status');
      const iconSpan = badge.querySelector('[aria-hidden="true"]');
      expect(iconSpan?.textContent).toContain('\u23F8'); // Pause emoji (part of the actual content)
    });
  });
});

describe('getConfidenceDescription', () => {
  it('returns "High confidence" for high tier', () => {
    expect(getConfidenceDescription('high')).toBe('High confidence');
  });

  it('returns "Medium confidence" for medium tier', () => {
    expect(getConfidenceDescription('medium')).toBe('Medium confidence');
  });

  it('returns "Low confidence" for low tier', () => {
    expect(getConfidenceDescription('low')).toBe('Low confidence');
  });

  it('returns "No recommendation" for pass tier', () => {
    expect(getConfidenceDescription('pass')).toBe('No recommendation');
  });

  it('returns "No recommendation" for null tier', () => {
    expect(getConfidenceDescription(null)).toBe('No recommendation');
  });
});
