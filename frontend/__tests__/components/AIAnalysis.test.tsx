import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AIAnalysisPanel, SingleAnalysisCard } from '@/components/AIAnalysis';
import { mockClaudeAnalysis, mockGrokAnalysis, mockPassAnalysis } from '../__mocks__/mockData';
import type { AIAnalysis, AIProvider } from '@/lib/types';

describe('AIAnalysisPanel', () => {
  describe('Tab Navigation', () => {
    it('renders Claude and Grok tabs', () => {
      render(<AIAnalysisPanel analyses={[]} />);

      expect(screen.getByRole('button', { name: /claude/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /grok/i })).toBeInTheDocument();
    });

    it('shows Claude tab as active by default', () => {
      render(<AIAnalysisPanel analyses={[mockClaudeAnalysis]} />);

      const claudeTab = screen.getByRole('button', { name: /claude/i });
      // Check for active styling class
      expect(claudeTab.className).toContain('border-orange-500');
    });

    it('switches to Grok tab when clicked', () => {
      render(<AIAnalysisPanel analyses={[mockClaudeAnalysis, mockGrokAnalysis]} />);

      const grokTab = screen.getByRole('button', { name: /grok/i });
      fireEvent.click(grokTab);

      expect(grokTab.className).toContain('border-blue-500');
    });

    it('shows Compare tab only when both analyses exist', () => {
      // Without both analyses
      const { rerender } = render(<AIAnalysisPanel analyses={[mockClaudeAnalysis]} />);

      expect(screen.queryByRole('button', { name: /compare/i })).not.toBeInTheDocument();

      // With both analyses
      rerender(<AIAnalysisPanel analyses={[mockClaudeAnalysis, mockGrokAnalysis]} />);

      expect(screen.getByRole('button', { name: /compare/i })).toBeInTheDocument();
    });

    it('shows "Ready" indicator when analysis exists for provider', () => {
      render(<AIAnalysisPanel analyses={[mockClaudeAnalysis]} />);

      // Claude should show Ready
      expect(screen.getByText('Ready')).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('shows empty state message when no analysis for selected provider', () => {
      render(<AIAnalysisPanel analyses={[]} />);

      expect(screen.getByText(/no claude analysis available yet/i)).toBeInTheDocument();
    });

    it('shows generate button in empty state when callback provided', () => {
      const mockRequestAnalysis = jest.fn();
      render(
        <AIAnalysisPanel analyses={[]} onRequestAnalysis={mockRequestAnalysis} />
      );

      const generateButton = screen.getByRole('button', { name: /generate claude analysis/i });
      expect(generateButton).toBeInTheDocument();
    });

    it('calls onRequestAnalysis with correct provider when generate clicked', async () => {
      const mockRequestAnalysis = jest.fn().mockResolvedValue(undefined);
      render(
        <AIAnalysisPanel analyses={[]} onRequestAnalysis={mockRequestAnalysis} />
      );

      // Click to generate Claude analysis
      fireEvent.click(screen.getByRole('button', { name: /generate claude analysis/i }));

      expect(mockRequestAnalysis).toHaveBeenCalledWith('claude');

      // Switch to Grok and try
      fireEvent.click(screen.getByRole('button', { name: /grok/i }));
      fireEvent.click(screen.getByRole('button', { name: /generate grok analysis/i }));

      expect(mockRequestAnalysis).toHaveBeenCalledWith('grok');
    });
  });

  describe('Analysis Content Display', () => {
    it('displays recommended bet when not pass', () => {
      render(<AIAnalysisPanel analyses={[mockClaudeAnalysis]} />);

      expect(screen.getByText(/recommended bet/i)).toBeInTheDocument();
      expect(screen.getByText(/home spread/i)).toBeInTheDocument();
    });

    it('displays pass recommendation correctly', () => {
      render(<AIAnalysisPanel analyses={[mockPassAnalysis]} />);

      expect(screen.getByText(/pass on this game/i)).toBeInTheDocument();
    });

    it('displays confidence score as percentage', () => {
      render(<AIAnalysisPanel analyses={[mockClaudeAnalysis]} />);

      // 0.72 confidence should display as 72%
      expect(screen.getByText('72%')).toBeInTheDocument();
    });

    it('displays key factors list', () => {
      render(<AIAnalysisPanel analyses={[mockClaudeAnalysis]} />);

      expect(screen.getByText(/key factors/i)).toBeInTheDocument();

      // Check for each key factor
      mockClaudeAnalysis.key_factors?.forEach((factor) => {
        expect(screen.getByText(factor)).toBeInTheDocument();
      });
    });

    it('displays reasoning text', () => {
      render(<AIAnalysisPanel analyses={[mockClaudeAnalysis]} />);

      expect(screen.getByText(/analysis/i)).toBeInTheDocument();
      expect(screen.getByText(mockClaudeAnalysis.reasoning!)).toBeInTheDocument();
    });

    it('shows full response in collapsed details', () => {
      const analysisWithDifferentResponse: AIAnalysis = {
        ...mockClaudeAnalysis,
        response: 'This is the full response text that differs from reasoning',
      };
      render(<AIAnalysisPanel analyses={[analysisWithDifferentResponse]} />);

      expect(screen.getByText(/view full ai response/i)).toBeInTheDocument();
    });

    it('displays creation date', () => {
      render(<AIAnalysisPanel analyses={[mockClaudeAnalysis]} />);

      // Should show formatted date
      expect(screen.getByText(/generated:/i)).toBeInTheDocument();
    });

    it('displays token usage when available', () => {
      render(<AIAnalysisPanel analyses={[mockClaudeAnalysis]} />);

      expect(screen.getByText(/1250 tokens/i)).toBeInTheDocument();
    });
  });

  describe('Compare View', () => {
    it('shows compare view when compare tab is selected', () => {
      render(<AIAnalysisPanel analyses={[mockClaudeAnalysis, mockGrokAnalysis]} />);

      fireEvent.click(screen.getByRole('button', { name: /compare/i }));

      // Should show both AI provider names in compare view
      expect(screen.getByText('Claude')).toBeInTheDocument();
      expect(screen.getByText('Grok')).toBeInTheDocument();
    });

    it('shows AI Consensus when both models agree', () => {
      const agreingGrok: AIAnalysis = {
        ...mockGrokAnalysis,
        recommended_bet: mockClaudeAnalysis.recommended_bet,
      };

      render(<AIAnalysisPanel analyses={[mockClaudeAnalysis, agreingGrok]} />);

      fireEvent.click(screen.getByRole('button', { name: /compare/i }));

      expect(screen.getByText(/ai consensus/i)).toBeInTheDocument();
    });

    it('shows Split Decision when models disagree', () => {
      const disagreeingGrok: AIAnalysis = {
        ...mockGrokAnalysis,
        recommended_bet: 'away_spread',
      };

      render(<AIAnalysisPanel analyses={[mockClaudeAnalysis, disagreeingGrok]} />);

      fireEvent.click(screen.getByRole('button', { name: /compare/i }));

      expect(screen.getByText(/split decision/i)).toBeInTheDocument();
    });

    it('shows average confidence when both agree', () => {
      // Claude: 0.72, Grok: 0.68 => avg = 0.70 = 70%
      render(<AIAnalysisPanel analyses={[mockClaudeAnalysis, mockGrokAnalysis]} />);

      fireEvent.click(screen.getByRole('button', { name: /compare/i }));

      expect(screen.getByText('70%')).toBeInTheDocument();
    });

    it('shows both models pass recommendation correctly', () => {
      const passingGrok: AIAnalysis = {
        ...mockGrokAnalysis,
        recommended_bet: 'pass',
      };
      const passingClaude: AIAnalysis = {
        ...mockClaudeAnalysis,
        recommended_bet: 'pass',
      };

      render(<AIAnalysisPanel analyses={[passingClaude, passingGrok]} />);

      fireEvent.click(screen.getByRole('button', { name: /compare/i }));

      expect(screen.getByText(/both recommend passing/i)).toBeInTheDocument();
    });

    it('displays key factors for both providers in compare view', () => {
      render(<AIAnalysisPanel analyses={[mockClaudeAnalysis, mockGrokAnalysis]} />);

      fireEvent.click(screen.getByRole('button', { name: /compare/i }));

      // Check Claude's factors appear
      expect(screen.getByText(mockClaudeAnalysis.key_factors![0])).toBeInTheDocument();

      // Check Grok's factors appear
      expect(screen.getByText(mockGrokAnalysis.key_factors![0])).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('shows skeleton loading state when isLoading is true', () => {
      render(<AIAnalysisPanel analyses={[]} isLoading={true} />);

      // The skeleton should render - check for skeleton structure
      const container = document.querySelector('.space-y-6');
      expect(container).toBeInTheDocument();
    });

    it('shows compare skeleton when loading and compare tab selected', () => {
      render(<AIAnalysisPanel analyses={[mockClaudeAnalysis, mockGrokAnalysis]} isLoading={true} />);

      fireEvent.click(screen.getByRole('button', { name: /compare/i }));

      // Should render compare skeleton structure
      const gridContainer = document.querySelector('.grid.grid-cols-2');
      expect(gridContainer).toBeInTheDocument();
    });
  });

  describe('Bet Recommendation Formatting', () => {
    it('formats home_spread as "Home Spread"', () => {
      render(<AIAnalysisPanel analyses={[mockClaudeAnalysis]} />);

      expect(screen.getByText(/home spread/i)).toBeInTheDocument();
    });

    it('formats away_ml as "Away Moneyline"', () => {
      const mlAnalysis: AIAnalysis = {
        ...mockClaudeAnalysis,
        recommended_bet: 'away_ml',
      };

      render(<AIAnalysisPanel analyses={[mlAnalysis]} />);

      expect(screen.getByText(/away moneyline/i)).toBeInTheDocument();
    });

    it('handles unknown bet formats gracefully', () => {
      const unknownBet: AIAnalysis = {
        ...mockClaudeAnalysis,
        recommended_bet: 'unknown_format',
      };

      render(<AIAnalysisPanel analyses={[unknownBet]} />);

      // Should still render something
      expect(screen.getByText(/recommended bet/i)).toBeInTheDocument();
    });
  });
});

describe('SingleAnalysisCard', () => {
  describe('Rendering', () => {
    it('renders Claude analysis card correctly', () => {
      render(<SingleAnalysisCard analysis={mockClaudeAnalysis} provider="claude" />);

      expect(screen.getByText(/claude analysis/i)).toBeInTheDocument();
    });

    it('renders Grok analysis card correctly', () => {
      render(<SingleAnalysisCard analysis={mockGrokAnalysis} provider="grok" />);

      expect(screen.getByText(/grok analysis/i)).toBeInTheDocument();
    });

    it('shows empty state when analysis is null', () => {
      render(<SingleAnalysisCard analysis={null} provider="claude" />);

      expect(screen.getByText(/no analysis yet/i)).toBeInTheDocument();
    });

    it('shows generate button when onRequest provided and no analysis', () => {
      const mockRequest = jest.fn();
      render(<SingleAnalysisCard analysis={null} provider="claude" onRequest={mockRequest} />);

      const button = screen.getByRole('button', { name: /generate analysis/i });
      expect(button).toBeInTheDocument();
    });

    it('calls onRequest when generate button clicked', () => {
      const mockRequest = jest.fn().mockResolvedValue(undefined);
      render(<SingleAnalysisCard analysis={null} provider="claude" onRequest={mockRequest} />);

      fireEvent.click(screen.getByRole('button', { name: /generate analysis/i }));

      expect(mockRequest).toHaveBeenCalled();
    });
  });

  describe('Loading State', () => {
    it('shows skeleton when isLoading is true', () => {
      render(<SingleAnalysisCard analysis={null} provider="claude" isLoading={true} />);

      // Skeleton should be rendered instead of empty state
      expect(screen.queryByText(/no analysis yet/i)).not.toBeInTheDocument();
    });
  });

  describe('Content Display', () => {
    it('displays analysis content when provided', () => {
      render(<SingleAnalysisCard analysis={mockClaudeAnalysis} provider="claude" />);

      // Should show recommendation
      expect(screen.getByText(/home spread/i)).toBeInTheDocument();

      // Should show confidence
      expect(screen.getByText('72%')).toBeInTheDocument();
    });
  });
});

describe('Integration: Tab Switching and Content', () => {
  it('shows correct analysis when switching between tabs', () => {
    render(<AIAnalysisPanel analyses={[mockClaudeAnalysis, mockGrokAnalysis]} />);

    // Initially shows Claude (72% confidence)
    expect(screen.getByText('72%')).toBeInTheDocument();

    // Switch to Grok
    fireEvent.click(screen.getByRole('button', { name: /grok/i }));

    // Should now show Grok's confidence (68%)
    expect(screen.getByText('68%')).toBeInTheDocument();
    expect(screen.queryByText('72%')).not.toBeInTheDocument();
  });

  it('maintains compare view content when re-selected', () => {
    render(<AIAnalysisPanel analyses={[mockClaudeAnalysis, mockGrokAnalysis]} />);

    // Go to compare
    fireEvent.click(screen.getByRole('button', { name: /compare/i }));
    expect(screen.getByText(/ai consensus/i)).toBeInTheDocument();

    // Go to Claude
    fireEvent.click(screen.getByRole('button', { name: /claude/i }));
    expect(screen.queryByText(/ai consensus/i)).not.toBeInTheDocument();

    // Go back to compare
    fireEvent.click(screen.getByRole('button', { name: /compare/i }));
    expect(screen.getByText(/ai consensus/i)).toBeInTheDocument();
  });
});
