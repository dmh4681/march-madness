// Database types for Supabase
export interface Database {
  public: {
    Tables: {
      teams: {
        Row: Team;
        Insert: Omit<Team, 'id' | 'created_at' | 'updated_at'>;
        Update: Partial<Omit<Team, 'id'>>;
      };
      games: {
        Row: Game;
        Insert: Omit<Game, 'id' | 'created_at' | 'updated_at'>;
        Update: Partial<Omit<Game, 'id'>>;
      };
      spreads: {
        Row: Spread;
        Insert: Omit<Spread, 'id'>;
        Update: Partial<Omit<Spread, 'id'>>;
      };
      rankings: {
        Row: Ranking;
        Insert: Omit<Ranking, 'id' | 'created_at'>;
        Update: Partial<Omit<Ranking, 'id'>>;
      };
      predictions: {
        Row: Prediction;
        Insert: Omit<Prediction, 'id' | 'created_at'>;
        Update: Partial<Omit<Prediction, 'id'>>;
      };
      ai_analysis: {
        Row: AIAnalysis;
        Insert: Omit<AIAnalysis, 'id' | 'created_at'>;
        Update: Partial<Omit<AIAnalysis, 'id'>>;
      };
      bet_results: {
        Row: BetResult;
        Insert: Omit<BetResult, 'id' | 'created_at'>;
        Update: Partial<Omit<BetResult, 'id'>>;
      };
    };
    Views: {
      today_games: {
        Row: TodayGame;
      };
      season_performance: {
        Row: SeasonPerformance;
      };
    };
  };
}

// Table types
export interface Team {
  id: string;
  name: string;
  normalized_name: string;
  mascot: string | null;
  conference: string | null;
  is_power_conference: boolean;
  logo_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface Game {
  id: string;
  external_id: string | null;
  date: string;
  tip_time: string | null;
  season: number;
  home_team_id: string | null;
  away_team_id: string | null;
  home_score: number | null;
  away_score: number | null;
  is_conference_game: boolean;
  is_tournament: boolean;
  tournament_round: string | null;
  venue: string | null;
  neutral_site: boolean;
  status: GameStatus;
  created_at: string;
  updated_at: string;
}

export type GameStatus = 'scheduled' | 'in_progress' | 'final' | 'postponed' | 'cancelled';

export interface Spread {
  id: string;
  game_id: string | null;
  captured_at: string;
  home_spread: number | null;
  away_spread: number | null;
  home_spread_odds: number;
  away_spread_odds: number;
  home_ml: number | null;
  away_ml: number | null;
  over_under: number | null;
  over_odds: number;
  under_odds: number;
  source: string;
  is_opening_line: boolean;
  is_closing_line: boolean;
}

export interface Ranking {
  id: string;
  team_id: string | null;
  season: number;
  week: number;
  poll_date: string | null;
  rank: number | null;
  previous_rank: number | null;
  first_place_votes: number | null;
  total_points: number | null;
  poll_type: string;
  created_at: string;
}

export interface Prediction {
  id: string;
  game_id: string | null;
  created_at: string;
  model_name: string;
  model_version: string;
  spread_at_prediction: number | null;
  predicted_home_cover_prob: number | null;
  predicted_away_cover_prob: number | null;
  predicted_home_win_prob: number | null;
  predicted_margin: number | null;
  confidence_tier: ConfidenceTier | null;
  recommended_bet: string | null;
  edge_pct: number | null;
  kelly_fraction: number | null;
  features_json: Record<string, unknown> | null;
}

export type ConfidenceTier = 'high' | 'medium' | 'low' | 'pass';

export interface AIAnalysis {
  id: string;
  game_id: string | null;
  created_at: string;
  ai_provider: AIProvider;
  model_used: string | null;
  analysis_type: string;
  prompt_hash: string | null;
  response: string | null;
  structured_analysis: Record<string, unknown> | null;
  recommended_bet: string | null;
  confidence_score: number | null;
  key_factors: string[] | null;
  reasoning: string | null;
  tokens_used: number | null;
}

export type AIProvider = 'claude' | 'grok' | 'openai';

export interface BetResult {
  id: string;
  prediction_id: string | null;
  game_id: string | null;
  created_at: string;
  bet_type: BetType;
  side: 'home' | 'away';
  spread_at_bet: number | null;
  odds_at_bet: number;
  result: BetResultStatus | null;
  units_wagered: number;
  units_won: number | null;
  actual_margin: number | null;
  graded_at: string | null;
}

export type BetType = 'spread' | 'ml' | 'over' | 'under';
export type BetResultStatus = 'win' | 'loss' | 'push' | 'pending';

// KenPom Advanced Analytics
export interface KenPomRating {
  id: string;
  team_id: string;
  season: number;
  rank: number | null;
  adj_efficiency_margin: number | null;
  adj_offense: number | null;
  adj_offense_rank: number | null;
  adj_defense: number | null;
  adj_defense_rank: number | null;
  adj_tempo: number | null;
  adj_tempo_rank: number | null;
  luck: number | null;
  luck_rank: number | null;
  sos_adj_em: number | null;
  sos_adj_em_rank: number | null;
  sos_opp_offense: number | null;
  sos_opp_offense_rank: number | null;
  sos_opp_defense: number | null;
  sos_opp_defense_rank: number | null;
  ncsos_adj_em: number | null;
  ncsos_adj_em_rank: number | null;
  wins: number | null;
  losses: number | null;
  conference: string | null;
  captured_at: string;
  captured_date: string;
}

// Haslametrics Advanced Analytics (FREE alternative to KenPom)
// Uses "All-Play Percentage" methodology instead of pure efficiency
export interface HaslametricsRating {
  id: string;
  team_id: string;
  season: number;
  rank: number | null;
  // Efficiency metrics
  offensive_efficiency: number | null;
  defensive_efficiency: number | null;
  efficiency_margin: number | null;  // Calculated: off - def
  // Shooting
  ft_pct: number | null;
  // Momentum (trending performance)
  momentum_overall: number | null;
  momentum_offense: number | null;
  momentum_defense: number | null;
  // Quality metrics
  consistency: number | null;  // Lower = more consistent
  sos: number | null;          // Strength of Schedule
  rpi: number | null;
  all_play_pct: number | null; // Core metric: win % vs average team
  // Record breakdown
  last_5_record: string | null;
  quad_1_record: string | null;
  quad_2_record: string | null;
  quad_3_record: string | null;
  quad_4_record: string | null;
  wins: number | null;
  losses: number | null;
  conference: string | null;
  captured_at: string;
  captured_date: string;
}

// View types
export interface TodayGame {
  id: string;
  date: string;
  tip_time: string | null;
  home_team: string;
  home_conference: string | null;
  away_team: string;
  away_conference: string | null;
  is_conference_game: boolean;
  home_spread: number | null;
  home_ml: number | null;
  away_ml: number | null;
  over_under: number | null;
  home_rank: number | null;
  away_rank: number | null;
  predicted_home_cover_prob: number | null;
  confidence_tier: ConfidenceTier | null;
  recommended_bet: string | null;
  edge_pct: number | null;
}

export interface SeasonPerformance {
  season: number;
  total_bets: number;
  wins: number;
  losses: number;
  pushes: number;
  win_pct: number | null;
  units_wagered: number;
  units_won: number;
  roi_pct: number | null;
}

// Extended types for UI
export interface GameWithDetails extends Game {
  home_team: Team;
  away_team: Team;
  latest_spread: Spread | null;
  home_ranking: Ranking | null;
  away_ranking: Ranking | null;
  home_kenpom: KenPomRating | null;
  away_kenpom: KenPomRating | null;
  home_haslametrics: HaslametricsRating | null;
  away_haslametrics: HaslametricsRating | null;
  prediction: Prediction | null;
  ai_analyses: AIAnalysis[];
}

export interface DashboardStats {
  season_roi: number;
  win_rate: number;
  total_bets: number;
  current_streak: number;
  streak_type: 'W' | 'L' | null;
}

// API response types
export interface PredictionResponse {
  game_id: string;
  home_cover_prob: number;
  away_cover_prob: number;
  confidence: ConfidenceTier;
  recommended_bet: string;
  edge_pct: number;
  reasoning: string;
}

export interface AIAnalysisResponse {
  provider: AIProvider;
  analysis: string;
  recommended_bet: string | null;
  confidence_score: number;
  key_factors: string[];
  reasoning: string;
}

// Analytics response for lazy loading
export interface GameAnalyticsResponse {
  game_id: string;
  home_team: string;
  away_team: string;
  home_kenpom: KenPomRating | null;
  away_kenpom: KenPomRating | null;
  home_haslametrics: HaslametricsRating | null;
  away_haslametrics: HaslametricsRating | null;
}

// Utility types
export type SortDirection = 'asc' | 'desc';

export interface GameFilters {
  date?: string;
  conference?: string;
  ranked_only?: boolean;
  conference_games_only?: boolean;
  with_predictions_only?: boolean;
}
