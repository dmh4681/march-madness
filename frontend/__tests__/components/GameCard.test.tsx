import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { GameCard, GameCardCompact, GameCardCompactSkeleton, GameCardWithAnalytics } from '@/components/GameCard';
import { LiveRegionProvider } from '@/components/ui/LiveRegion';
import type { TodayGame, ConfidenceTier } from '@/lib/types';

// Mock next/link
jest.mock('next/link', () => {
  return function MockLink({ children, href }: { children: React.ReactNode; href: string }) {
    return <a href={href}>{children}</a>;
  };
});

// Mock date-fns to control date formatting
jest.mock('date-fns', () => ({
  format: jest.fn((date: Date) => {
    const hours = date.getHours();
    const minutes = date.getMinutes();
    const ampm = hours >= 12 ? 'PM' : 'AM';
    const displayHours = hours % 12 || 12;
    const displayMinutes = minutes.toString().padStart(2, '0');
    return `${displayHours}:${displayMinutes} ${ampm}`;
  }),
}));

// Mock the useGameAnalytics hook
jest.mock('@/hooks/useGameAnalytics', () => ({
  useGameAnalytics: jest.fn(() => ({
    analytics: null,
    isLoading: false,
    error: null,
    loadAnalytics: jest.fn(),
    hasLoaded: false,
  })),
}));

// Helper wrapper with LiveRegionProvider
const renderWithProvider = (ui: React.ReactElement) => {
  return render(
    <LiveRegionProvider>
      {ui}
    </LiveRegionProvider>
  );
};

// Base mock game data
const createMockGame = (overrides: Partial<TodayGame> = {}): TodayGame => ({
  id: 'game-123',
  date: '2024-01-15',
  tip_time: '2024-01-15T19:00:00Z',
  home_team: 'Duke Blue Devils',
  home_conference: 'ACC',
  away_team: 'North Carolina Tar Heels',
  away_conference: 'ACC',
  is_conference_game: true,
  home_spread: -5.5,
  home_ml: -200,
  away_ml: 180,
  over_under: 145.5,
  home_rank: 5,
  away_rank: 8,
  predicted_home_cover_prob: 0.58,
  confidence_tier: 'medium' as ConfidenceTier,
  recommended_bet: 'home_spread',
  edge_pct: 3.2,
  ...overrides,
});

describe('GameCard', () => {
  describe('Basic rendering', () => {
    it('renders game matchup correctly', () => {
      renderWithProvider(<GameCard game={createMockGame()} />);

      expect(screen.getByText('Duke Blue Devils')).toBeInTheDocument();
      expect(screen.getByText('North Carolina Tar Heels')).toBeInTheDocument();
    });

    it('renders as an article with game description', () => {
      renderWithProvider(<GameCard game={createMockGame()} />);

      const article = screen.getByRole('article');
      expect(article).toHaveAttribute('aria-label');
      expect(article.getAttribute('aria-label')).toContain('North Carolina Tar Heels at Duke Blue Devils');
    });

    it('links to game detail page', () => {
      renderWithProvider(<GameCard game={createMockGame()} />);

      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', '/games/game-123');
    });
  });

  describe('Tip time display', () => {
    it('displays formatted tip time when available', () => {
      renderWithProvider(<GameCard game={createMockGame({ tip_time: '2024-01-15T19:00:00Z' })} />);

      // The mock date-fns will format this
      expect(screen.getByRole('time')).toBeInTheDocument();
    });

    it('displays TBD when tip_time is same as date', () => {
      renderWithProvider(<GameCard game={createMockGame({ tip_time: '2024-01-15', date: '2024-01-15' })} />);

      expect(screen.getByText('TBD')).toBeInTheDocument();
    });

    it('displays TBD when tip_time ends with T00:00:00', () => {
      renderWithProvider(<GameCard game={createMockGame({ tip_time: '2024-01-15T00:00:00' })} />);

      expect(screen.getByText('TBD')).toBeInTheDocument();
    });

    it('displays TBD when tip_time is null', () => {
      renderWithProvider(<GameCard game={createMockGame({ tip_time: null })} />);

      expect(screen.getByText('TBD')).toBeInTheDocument();
    });
  });

  describe('Team rankings display', () => {
    it('displays both team rankings when available', () => {
      renderWithProvider(<GameCard game={createMockGame({ home_rank: 5, away_rank: 8 })} />);

      expect(screen.getByText('#5')).toBeInTheDocument();
      expect(screen.getByText('#8')).toBeInTheDocument();
    });

    it('displays only home ranking when away is null', () => {
      renderWithProvider(<GameCard game={createMockGame({ home_rank: 5, away_rank: null })} />);

      expect(screen.getByText('#5')).toBeInTheDocument();
      expect(screen.queryByText('#8')).not.toBeInTheDocument();
    });

    it('displays only away ranking when home is null', () => {
      renderWithProvider(<GameCard game={createMockGame({ home_rank: null, away_rank: 8 })} />);

      expect(screen.queryByText('#5')).not.toBeInTheDocument();
      expect(screen.getByText('#8')).toBeInTheDocument();
    });

    it('does not display rankings when both are null', () => {
      renderWithProvider(<GameCard game={createMockGame({ home_rank: null, away_rank: null })} />);

      expect(screen.queryByText(/#\d+/)).not.toBeInTheDocument();
    });

    it('shows RANKED badge when either team is ranked', () => {
      renderWithProvider(<GameCard game={createMockGame({ home_rank: 5, away_rank: null })} />);

      expect(screen.getByText('RANKED')).toBeInTheDocument();
    });

    it('does not show RANKED badge when no team is ranked', () => {
      renderWithProvider(<GameCard game={createMockGame({ home_rank: null, away_rank: null })} />);

      expect(screen.queryByText('RANKED')).not.toBeInTheDocument();
    });
  });

  describe('Conference game badge', () => {
    it('shows CONF badge for conference games', () => {
      renderWithProvider(<GameCard game={createMockGame({ is_conference_game: true })} />);

      expect(screen.getByText('CONF')).toBeInTheDocument();
    });

    it('does not show CONF badge for non-conference games', () => {
      renderWithProvider(<GameCard game={createMockGame({ is_conference_game: false })} />);

      expect(screen.queryByText('CONF')).not.toBeInTheDocument();
    });
  });

  describe('Spread display', () => {
    it('displays home spread correctly', () => {
      renderWithProvider(<GameCard game={createMockGame({ home_spread: -5.5 })} />);

      expect(screen.getByText('-5.5')).toBeInTheDocument();
    });

    it('displays away spread correctly (inverted from home)', () => {
      renderWithProvider(<GameCard game={createMockGame({ home_spread: -5.5 })} />);

      expect(screen.getByText('+5.5')).toBeInTheDocument();
    });

    it('displays N/A when spread is null', () => {
      renderWithProvider(<GameCard game={createMockGame({ home_spread: null })} />);

      const naElements = screen.getAllByText('N/A');
      expect(naElements.length).toBeGreaterThan(0);
    });

    it('displays positive spread with plus sign', () => {
      renderWithProvider(<GameCard game={createMockGame({ home_spread: 3.5 })} />);

      expect(screen.getByText('+3.5')).toBeInTheDocument();
    });
  });

  describe('Over/Under display', () => {
    it('displays over/under total', () => {
      renderWithProvider(<GameCard game={createMockGame({ over_under: 145.5 })} />);

      expect(screen.getByText('O/U 145.5')).toBeInTheDocument();
    });

    it('displays N/A when over_under is null', () => {
      renderWithProvider(<GameCard game={createMockGame({ over_under: null })} />);

      expect(screen.getByText('O/U N/A')).toBeInTheDocument();
    });
  });

  describe('Prediction display', () => {
    it('shows prediction when showPrediction is true (default)', () => {
      renderWithProvider(<GameCard game={createMockGame()} />);

      // Should show the confidence badge and recommended bet
      expect(screen.getByRole('status', { name: /confidence level/i })).toBeInTheDocument();
    });

    it('hides prediction when showPrediction is false', () => {
      renderWithProvider(<GameCard game={createMockGame()} showPrediction={false} />);

      // Should not show confidence badge
      expect(screen.queryByRole('status', { name: /confidence level/i })).not.toBeInTheDocument();
    });

    it('shows "Analysis pending..." when predicted_home_cover_prob is null', () => {
      renderWithProvider(<GameCard game={createMockGame({ predicted_home_cover_prob: null })} />);

      expect(screen.getByText('Analysis pending...')).toBeInTheDocument();
    });

    it('displays recommended bet for home spread', () => {
      renderWithProvider(<GameCard game={createMockGame({ recommended_bet: 'home_spread' })} />);

      // Home team name should appear in the recommended bet section with spread
      const betRegion = screen.getByRole('region', { name: /betting prediction/i });
      expect(betRegion).toHaveTextContent('Duke Blue Devils');
      expect(betRegion).toHaveTextContent('-5.5');
    });

    it('displays recommended bet for away spread', () => {
      renderWithProvider(<GameCard game={createMockGame({ recommended_bet: 'away_spread' })} />);

      // Away team name should appear in the recommended bet section
      const betRegion = screen.getByRole('region', { name: /betting prediction/i });
      expect(betRegion).toHaveTextContent('North Carolina Tar Heels');
    });

    it('displays edge percentage when positive', () => {
      renderWithProvider(<GameCard game={createMockGame({ edge_pct: 3.2 })} />);

      expect(screen.getByText('+3.2% edge')).toBeInTheDocument();
    });

    it('does not display edge when null', () => {
      renderWithProvider(<GameCard game={createMockGame({ edge_pct: null })} />);

      expect(screen.queryByText(/% edge/)).not.toBeInTheDocument();
    });

    it('does not display edge when zero', () => {
      renderWithProvider(<GameCard game={createMockGame({ edge_pct: 0 })} />);

      expect(screen.queryByText(/% edge/)).not.toBeInTheDocument();
    });

    it('does not display edge when negative', () => {
      renderWithProvider(<GameCard game={createMockGame({ edge_pct: -1.5 })} />);

      expect(screen.queryByText(/% edge/)).not.toBeInTheDocument();
    });
  });

  describe('Confidence tiers', () => {
    const tiers: ConfidenceTier[] = ['high', 'medium', 'low', 'pass'];

    tiers.forEach((tier) => {
      it(`renders ${tier} confidence tier`, () => {
        renderWithProvider(<GameCard game={createMockGame({ confidence_tier: tier })} />);

        const badge = screen.getByRole('status', { name: /confidence level/i });
        expect(badge).toBeInTheDocument();
      });
    });

    it('handles null confidence tier', () => {
      renderWithProvider(<GameCard game={createMockGame({ confidence_tier: null })} />);

      // With null confidence_tier but valid predicted_home_cover_prob, should still render badge
      const badge = screen.getByRole('status', { name: /confidence level/i });
      expect(badge).toBeInTheDocument();
    });
  });

  describe('Mobile expand/collapse behavior', () => {
    it('renders expand button on mobile view', () => {
      renderWithProvider(<GameCard game={createMockGame()} />);

      const expandButton = screen.getByRole('button', { name: /show more details/i });
      expect(expandButton).toBeInTheDocument();
    });

    it('toggles expanded state when button is clicked', () => {
      renderWithProvider(<GameCard game={createMockGame()} />);

      const expandButton = screen.getByRole('button', { name: /show more details/i });
      expect(expandButton).toHaveAttribute('aria-expanded', 'false');

      fireEvent.click(expandButton);

      expect(expandButton).toHaveAttribute('aria-expanded', 'true');
      expect(expandButton).toHaveAttribute('aria-label', 'Show less details');
    });

    it('shows expanded content with moneylines when expanded', () => {
      renderWithProvider(<GameCard game={createMockGame()} />);

      const expandButton = screen.getByRole('button', { name: /show more details/i });
      fireEvent.click(expandButton);

      expect(screen.getByText('Moneylines')).toBeInTheDocument();
    });

    it('shows conference information when expanded and available', () => {
      renderWithProvider(<GameCard game={createMockGame({ home_conference: 'ACC', away_conference: 'ACC' })} />);

      const expandButton = screen.getByRole('button', { name: /show more details/i });
      fireEvent.click(expandButton);

      expect(screen.getByText('Conferences')).toBeInTheDocument();
      expect(screen.getByText('ACC vs ACC')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has accessible game description in aria-label', () => {
      renderWithProvider(<GameCard game={createMockGame()} />);

      const article = screen.getByRole('article');
      const label = article.getAttribute('aria-label');
      expect(label).toContain('North Carolina Tar Heels at Duke Blue Devils');
      expect(label).toContain('ranked matchup');
      expect(label).toContain('conference game');
    });

    it('has link to game detail page', () => {
      renderWithProvider(<GameCard game={createMockGame()} />);

      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', '/games/game-123');
    });

    it('has accessible expand button', () => {
      renderWithProvider(<GameCard game={createMockGame()} />);

      const expandButton = screen.getByRole('button', { name: /show more details/i });
      expect(expandButton).toHaveAttribute('aria-expanded');
      expect(expandButton).toHaveAttribute('aria-label');
    });

    it('provides time element with datetime attribute', () => {
      renderWithProvider(<GameCard game={createMockGame({ tip_time: '2024-01-15T19:00:00Z' })} />);

      const timeElement = screen.getByRole('time');
      expect(timeElement).toHaveAttribute('dateTime', '2024-01-15T19:00:00Z');
    });

    it('has accessible team lists', () => {
      renderWithProvider(<GameCard game={createMockGame()} />);

      const teamsList = screen.getByRole('list', { name: /teams and betting lines/i });
      expect(teamsList).toBeInTheDocument();
    });
  });

  describe('Edge cases with null/undefined data', () => {
    it('handles all null betting data gracefully', () => {
      const nullGame = createMockGame({
        home_spread: null,
        home_ml: null,
        away_ml: null,
        over_under: null,
      });

      renderWithProvider(<GameCard game={nullGame} />);

      // Should render without crashing
      expect(screen.getByText('Duke Blue Devils')).toBeInTheDocument();
    });

    it('handles null prediction data gracefully', () => {
      const nullPrediction = createMockGame({
        predicted_home_cover_prob: null,
        confidence_tier: null,
        recommended_bet: null,
        edge_pct: null,
      });

      renderWithProvider(<GameCard game={nullPrediction} />);

      expect(screen.getByText('Analysis pending...')).toBeInTheDocument();
    });

    it('handles pass recommended_bet correctly', () => {
      renderWithProvider(<GameCard game={createMockGame({ recommended_bet: 'pass' })} />);

      // Should not show team name as recommended bet
      const confidenceBadge = screen.getByRole('status', { name: /confidence level/i });
      expect(confidenceBadge).toBeInTheDocument();
    });

    it('handles null conferences in expanded view', () => {
      renderWithProvider(<GameCard game={createMockGame({ home_conference: null, away_conference: null })} />);

      const expandButton = screen.getByRole('button', { name: /show more details/i });
      fireEvent.click(expandButton);

      // Should not show conferences section when both are null
      expect(screen.queryByText('Conferences')).not.toBeInTheDocument();
    });
  });

  describe('ML bet display', () => {
    it('displays ML for moneyline bets', () => {
      renderWithProvider(<GameCard game={createMockGame({ recommended_bet: 'home_ml' })} />);

      const betRegion = screen.getByRole('region', { name: /betting prediction/i });
      expect(betRegion).toHaveTextContent('ML');
    });

    it('displays spread for spread bets', () => {
      renderWithProvider(<GameCard game={createMockGame({ recommended_bet: 'home_spread', home_spread: -5.5 })} />);

      const betRegion = screen.getByRole('region', { name: /betting prediction/i });
      expect(betRegion).toHaveTextContent('-5.5');
    });
  });
});

describe('GameCardCompact', () => {
  it('renders team names correctly', () => {
    renderWithProvider(<GameCardCompact game={createMockGame()} />);

    expect(screen.getByText('Duke Blue Devils')).toBeInTheDocument();
    expect(screen.getByText('North Carolina Tar Heels')).toBeInTheDocument();
  });

  it('renders as a link to game detail page', () => {
    renderWithProvider(<GameCardCompact game={createMockGame()} />);

    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', '/games/game-123');
  });

  it('shows confidence badge for non-pass tiers', () => {
    renderWithProvider(<GameCardCompact game={createMockGame({ confidence_tier: 'high' })} />);

    expect(screen.getByRole('status', { name: /confidence level/i })).toBeInTheDocument();
  });

  it('hides confidence badge for pass tier', () => {
    renderWithProvider(<GameCardCompact game={createMockGame({ confidence_tier: 'pass' })} />);

    expect(screen.queryByRole('status', { name: /confidence level/i })).not.toBeInTheDocument();
  });

  it('hides confidence badge when tier is null', () => {
    renderWithProvider(<GameCardCompact game={createMockGame({ confidence_tier: null })} />);

    expect(screen.queryByRole('status', { name: /confidence level/i })).not.toBeInTheDocument();
  });

  it('shows rankings when available', () => {
    renderWithProvider(<GameCardCompact game={createMockGame({ home_rank: 5, away_rank: 8 })} />);

    expect(screen.getByText('#5')).toBeInTheDocument();
    expect(screen.getByText('#8')).toBeInTheDocument();
  });

  it('links to correct game detail page', () => {
    renderWithProvider(<GameCardCompact game={createMockGame({ confidence_tier: 'high' })} />);

    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', '/games/game-123');
  });
});

describe('GameCardCompactSkeleton', () => {
  it('renders skeleton elements', () => {
    render(<GameCardCompactSkeleton />);

    // Should render skeleton placeholders - check for presence of container
    const container = document.querySelector('.flex.items-center');
    expect(container).toBeInTheDocument();
  });
});

describe('GameCardWithAnalytics', () => {
  it('renders GameCard and analytics section', () => {
    renderWithProvider(<GameCardWithAnalytics game={createMockGame()} />);

    expect(screen.getByText('Duke Blue Devils')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /show advanced analytics/i })).toBeInTheDocument();
  });

  it('can toggle analytics section', () => {
    renderWithProvider(<GameCardWithAnalytics game={createMockGame()} />);

    const analyticsButton = screen.getByRole('button', { name: /show advanced analytics/i });
    expect(analyticsButton).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(analyticsButton);

    expect(analyticsButton).toHaveAttribute('aria-expanded', 'true');
  });
});
