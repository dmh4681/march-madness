/**
 * Tests for Game Detail Page Components
 *
 * Since the GameDetailPage is a server component that fetches data directly,
 * we test:
 * 1. The client components it renders (AIAnalysisButton, AIAnalysisPanel)
 * 2. Integration of components within the page context
 * 3. UI formatting utilities used by the page
 */

import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { AIAnalysisButton } from '@/components/AIAnalysisButton';
import { AIAnalysisPanel } from '@/components/AIAnalysis';
import { ConfidenceBadge } from '@/components/ConfidenceBadge';
import { formatSpread, formatMoneyline, formatProbability } from '@/lib/api';
import {
  mockGameWithDetails,
  mockClaudeAnalysis,
  mockGrokAnalysis,
  mockSpread,
  createMockAnalysisResponse,
} from '../__mocks__/mockData';

// Test the formatting utilities used in the page
describe('Game Detail Page Utilities', () => {
  describe('formatSpread', () => {
    it('formats positive spread correctly', () => {
      expect(formatSpread(5.5)).toBe('+5.5');
    });

    it('formats negative spread correctly', () => {
      expect(formatSpread(-5.5)).toBe('-5.5');
    });

    it('formats zero spread as pick/even', () => {
      const result = formatSpread(0);
      expect(result).toMatch(/pick|pk|even|0/i);
    });

    it('handles null spread', () => {
      expect(formatSpread(null)).toBe('N/A');
    });
  });

  describe('formatMoneyline', () => {
    it('formats positive moneyline with plus sign', () => {
      expect(formatMoneyline(180)).toBe('+180');
    });

    it('formats negative moneyline correctly', () => {
      expect(formatMoneyline(-200)).toBe('-200');
    });

    it('handles null moneyline', () => {
      expect(formatMoneyline(null)).toBe('N/A');
    });
  });

  describe('formatProbability', () => {
    it('formats probability as percentage', () => {
      expect(formatProbability(0.58)).toBe('58%');
    });

    it('formats high probability correctly', () => {
      expect(formatProbability(0.95)).toBe('95%');
    });

    it('handles null probability', () => {
      expect(formatProbability(null)).toBe('N/A');
    });

    it('handles edge cases', () => {
      expect(formatProbability(1)).toBe('100%');
      expect(formatProbability(0)).toBe('0%');
    });
  });
});

// Test ConfidenceBadge component used in the page
describe('ConfidenceBadge', () => {
  it('renders high confidence tier correctly', () => {
    render(<ConfidenceBadge tier="high" />);

    const badge = screen.getByText(/high/i);
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain('green');
  });

  it('renders medium confidence tier correctly', () => {
    render(<ConfidenceBadge tier="medium" />);

    const badge = screen.getByText(/medium/i);
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain('yellow');
  });

  it('renders low confidence tier correctly', () => {
    render(<ConfidenceBadge tier="low" />);

    const badge = screen.getByText(/low/i);
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain('orange');
  });

  it('renders pass tier correctly', () => {
    render(<ConfidenceBadge tier="pass" />);

    const badge = screen.getByText(/pass/i);
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain('gray');
  });

  it('handles null tier gracefully', () => {
    render(<ConfidenceBadge tier={null} />);

    // Should not crash, may show default or nothing
    expect(document.body).toBeInTheDocument();
  });
});

// Integration tests for the game detail workflow
describe('Game Detail Page Integration', () => {
  const TEST_API_URL = 'http://localhost:8000';

  describe('AI Analysis Section', () => {
    it('renders AIAnalysisPanel with game analyses', () => {
      render(
        <AIAnalysisPanel analyses={[mockClaudeAnalysis, mockGrokAnalysis]} />
      );

      // Should show analysis tabs
      expect(screen.getByRole('button', { name: /claude/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /grok/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /compare/i })).toBeInTheDocument();
    });

    it('renders AIAnalysisButton alongside panel', () => {
      const hasClaudeAnalysis = mockGameWithDetails.ai_analyses.some(a => a.ai_provider === 'claude');
      const hasGrokAnalysis = mockGameWithDetails.ai_analyses.some(a => a.ai_provider === 'grok');

      render(
        <div>
          <AIAnalysisButton
            gameId={mockGameWithDetails.id}
            hasClaudeAnalysis={hasClaudeAnalysis}
            hasGrokAnalysis={hasGrokAnalysis}
            apiUrl={TEST_API_URL}
          />
          <AIAnalysisPanel analyses={mockGameWithDetails.ai_analyses} />
        </div>
      );

      // Both button and panel should be present
      expect(screen.getByRole('button', { name: /re-run claude analysis/i })).toBeInTheDocument();
      expect(screen.getByText(/home spread/i)).toBeInTheDocument();
    });
  });

  describe('Complete User Journey', () => {
    it('user can view existing analysis', () => {
      render(<AIAnalysisPanel analyses={[mockClaudeAnalysis]} />);

      // View Claude's recommendation
      expect(screen.getByText(/recommended bet/i)).toBeInTheDocument();
      expect(screen.getByText(/home spread/i)).toBeInTheDocument();
      expect(screen.getByText('72%')).toBeInTheDocument();

      // View key factors
      mockClaudeAnalysis.key_factors?.forEach(factor => {
        expect(screen.getByText(factor)).toBeInTheDocument();
      });

      // View reasoning
      expect(screen.getByText(mockClaudeAnalysis.reasoning!)).toBeInTheDocument();
    });

    it('user can switch between AI providers', () => {
      render(<AIAnalysisPanel analyses={[mockClaudeAnalysis, mockGrokAnalysis]} />);

      // Start with Claude (72%)
      expect(screen.getByText('72%')).toBeInTheDocument();

      // Switch to Grok
      fireEvent.click(screen.getByRole('button', { name: /grok/i }));

      // Now shows Grok's confidence (68%)
      expect(screen.getByText('68%')).toBeInTheDocument();
    });

    it('user can compare both AI analyses', () => {
      render(<AIAnalysisPanel analyses={[mockClaudeAnalysis, mockGrokAnalysis]} />);

      // Switch to compare view
      fireEvent.click(screen.getByRole('button', { name: /compare/i }));

      // Both analyses should be visible
      expect(screen.getByText(/ai consensus/i)).toBeInTheDocument();
      expect(screen.getByText('Claude')).toBeInTheDocument();
      expect(screen.getByText('Grok')).toBeInTheDocument();
    });

    it('user can request new AI analysis', async () => {
      const mockFetch = global.fetch as jest.Mock;
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        text: () => Promise.resolve(JSON.stringify(createMockAnalysisResponse())),
      });

      render(
        <AIAnalysisButton
          gameId="game-123"
          hasClaudeAnalysis={false}
          apiUrl={TEST_API_URL}
        />
      );

      // Click run analysis
      const runButton = screen.getByRole('button', { name: /run claude analysis/i });

      await act(async () => {
        fireEvent.click(runButton);
      });

      // Should show success
      await waitFor(() => {
        expect(screen.getByText(/analysis complete/i)).toBeInTheDocument();
      });
    });

    it('user sees loading state while analysis runs', async () => {
      let resolvePromise: (value: unknown) => void;
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });

      (global.fetch as jest.Mock).mockReturnValueOnce(pendingPromise);

      render(
        <AIAnalysisButton
          gameId="game-123"
          hasClaudeAnalysis={false}
          apiUrl={TEST_API_URL}
        />
      );

      fireEvent.click(screen.getByRole('button', { name: /run claude analysis/i }));

      // Should show loading state
      await waitFor(() => {
        expect(screen.getByText(/running claude analysis/i)).toBeInTheDocument();
        expect(screen.getByText(/typically completes within 30-60 seconds/i)).toBeInTheDocument();
      });

      // Clean up
      resolvePromise!({
        ok: true,
        status: 200,
        text: () => Promise.resolve(JSON.stringify(createMockAnalysisResponse())),
      });
    });

    it('user can retry after analysis fails', async () => {
      const mockFetch = global.fetch as jest.Mock;

      // First attempt fails
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        text: () => Promise.resolve('Server error'),
      });

      render(
        <AIAnalysisButton
          gameId="game-123"
          hasClaudeAnalysis={false}
          apiUrl={TEST_API_URL}
        />
      );

      // First attempt
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /run claude analysis/i }));
      });

      // Should show error with retry
      await waitFor(() => {
        expect(screen.getByText(/server error/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
      });

      // Second attempt succeeds
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        text: () => Promise.resolve(JSON.stringify(createMockAnalysisResponse())),
      });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /try again/i }));
      });

      // Should show success
      await waitFor(() => {
        expect(screen.getByText(/analysis complete/i)).toBeInTheDocument();
      });
    });
  });

  describe('Empty States', () => {
    it('shows empty state when no analyses exist', () => {
      render(<AIAnalysisPanel analyses={[]} />);

      expect(screen.getByText(/no claude analysis available yet/i)).toBeInTheDocument();
    });

    it('shows generate button for missing analysis', () => {
      const mockRequest = jest.fn();
      render(<AIAnalysisPanel analyses={[]} onRequestAnalysis={mockRequest} />);

      expect(screen.getByRole('button', { name: /generate claude analysis/i })).toBeInTheDocument();
    });

    it('shows one provider when only other exists', () => {
      render(<AIAnalysisPanel analyses={[mockGrokAnalysis]} />);

      // Claude tab should be default, showing empty
      expect(screen.getByText(/no claude analysis available yet/i)).toBeInTheDocument();

      // Grok should have content
      fireEvent.click(screen.getByRole('button', { name: /grok/i }));
      expect(screen.getByText('68%')).toBeInTheDocument();
    });
  });

  describe('Spread Information Display', () => {
    it('correctly displays home and away spreads', () => {
      // Test spread formatting as used in the page
      const homeSpread = mockSpread.home_spread;
      const awaySpread = mockSpread.away_spread;

      expect(formatSpread(homeSpread)).toBe('-5.5');
      expect(formatSpread(awaySpread)).toBe('+5.5');
    });

    it('correctly displays moneylines', () => {
      const homeMl = mockSpread.home_ml;
      const awayMl = mockSpread.away_ml;

      expect(formatMoneyline(homeMl)).toBe('-200');
      expect(formatMoneyline(awayMl)).toBe('+180');
    });
  });
});

// Test edge cases and error scenarios
describe('Edge Cases', () => {
  it('handles analysis with missing optional fields', () => {
    const minimalAnalysis = {
      ...mockClaudeAnalysis,
      key_factors: null,
      reasoning: null,
      tokens_used: null,
    };

    render(<AIAnalysisPanel analyses={[minimalAnalysis]} />);

    // Should still render without crashing
    expect(screen.getByText(/recommended bet/i)).toBeInTheDocument();
  });

  it('handles empty key factors array', () => {
    const noFactorsAnalysis = {
      ...mockClaudeAnalysis,
      key_factors: [],
    };

    render(<AIAnalysisPanel analyses={[noFactorsAnalysis]} />);

    // Should render without the key factors section
    expect(screen.queryByText(/key factors/i)).not.toBeInTheDocument();
  });

  it('handles very long reasoning text', () => {
    const longReasoning = 'A'.repeat(2000);
    const longAnalysis = {
      ...mockClaudeAnalysis,
      reasoning: longReasoning,
    };

    render(<AIAnalysisPanel analyses={[longAnalysis]} />);

    // Should render the long text
    expect(screen.getByText(longReasoning)).toBeInTheDocument();
  });

  it('handles special characters in analysis content', () => {
    const specialAnalysis = {
      ...mockClaudeAnalysis,
      reasoning: 'Analysis with <special> "characters" & symbols 100% sure',
      key_factors: ['Factor with "quotes"', 'Factor with <tags>', 'Factor with & ampersand'],
    };

    render(<AIAnalysisPanel analyses={[specialAnalysis]} />);

    expect(screen.getByText(/Analysis with <special>/i)).toBeInTheDocument();
  });
});
