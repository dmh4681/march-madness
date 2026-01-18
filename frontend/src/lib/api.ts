import type { PredictionResponse, AIAnalysisResponse, AIProvider } from './types';

const PYTHON_BACKEND_URL = process.env.NEXT_PUBLIC_PYTHON_BACKEND_URL || 'http://localhost:8000';

class APIClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async fetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;

    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`API Error: ${response.status} - ${error}`);
    }

    return response.json();
  }

  // Health check
  async health(): Promise<{ status: string; version: string }> {
    return this.fetch('/health');
  }

  // Get prediction for a game
  async predict(gameId: string): Promise<PredictionResponse> {
    return this.fetch('/predict', {
      method: 'POST',
      body: JSON.stringify({ game_id: gameId }),
    });
  }

  // Get prediction for a custom matchup (no game in DB yet)
  async predictMatchup(params: {
    home_team: string;
    away_team: string;
    spread: number;
    is_conference_game: boolean;
    home_rank?: number;
    away_rank?: number;
  }): Promise<PredictionResponse> {
    return this.fetch('/predict', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  // Get AI analysis for a game
  async analyze(
    gameId: string,
    provider: AIProvider = 'claude'
  ): Promise<AIAnalysisResponse> {
    return this.fetch('/ai-analysis', {
      method: 'POST',
      body: JSON.stringify({ game_id: gameId, provider }),
    });
  }

  // Trigger data refresh
  async refresh(): Promise<{ status: string; games_updated: number }> {
    return this.fetch('/refresh', { method: 'POST' });
  }

  // Get backtest results
  async backtest(params: {
    start_date: string;
    end_date: string;
    model?: string;
  }): Promise<{
    roi: number;
    win_rate: number;
    sample_size: number;
    by_confidence: Record<string, { wins: number; losses: number; roi: number }>;
  }> {
    const query = new URLSearchParams(params as Record<string, string>);
    return this.fetch(`/backtest?${query}`);
  }
}

export const api = new APIClient(PYTHON_BACKEND_URL);

// Helper to format spreads for display
export function formatSpread(spread: number | null): string {
  if (spread === null) return 'N/A';
  if (spread > 0) return `+${spread}`;
  return spread.toString();
}

// Helper to format moneyline for display
export function formatMoneyline(ml: number | null): string {
  if (ml === null) return 'N/A';
  if (ml > 0) return `+${ml}`;
  return ml.toString();
}

// Helper to format probability as percentage
export function formatProbability(prob: number | null): string {
  if (prob === null) return 'N/A';
  return `${(prob * 100).toFixed(1)}%`;
}

// Helper to get confidence tier color
export function getConfidenceColor(tier: string | null): string {
  switch (tier) {
    case 'high':
      return 'text-green-500';
    case 'medium':
      return 'text-yellow-500';
    case 'low':
      return 'text-orange-500';
    default:
      return 'text-gray-500';
  }
}

// Helper to get confidence tier background
export function getConfidenceBg(tier: string | null): string {
  switch (tier) {
    case 'high':
      return 'bg-green-500/10 border-green-500/30';
    case 'medium':
      return 'bg-yellow-500/10 border-yellow-500/30';
    case 'low':
      return 'bg-orange-500/10 border-orange-500/30';
    default:
      return 'bg-gray-500/10 border-gray-500/30';
  }
}
