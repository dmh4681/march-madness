import { notFound } from 'next/navigation';
import Link from 'next/link';
import { format } from 'date-fns';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';
import type { GameWithDetails, AIAnalysis, Prediction, Team, Spread, Ranking, GameStatus } from '@/lib/types';
import { formatSpread, formatMoneyline, formatProbability } from '@/lib/api';
import { ConfidenceBadge } from '@/components/ConfidenceBadge';
import { AIAnalysisPanel } from '@/components/AIAnalysis';
import { AIAnalysisButton } from '@/components/AIAnalysisButton';

// Demo game for when Supabase isn't configured
const DEMO_GAME: GameWithDetails = {
  id: 'demo-1',
  external_id: 'espn-12345',
  date: new Date().toISOString().split('T')[0],
  tip_time: new Date(Date.now() + 3600000).toISOString(),
  season: 2025,
  home_team_id: 'team-1',
  away_team_id: 'team-2',
  home_score: null,
  away_score: null,
  is_conference_game: true,
  is_tournament: false,
  tournament_round: null,
  venue: 'Cameron Indoor Stadium',
  neutral_site: false,
  status: 'scheduled',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  home_team: {
    id: 'team-1',
    name: 'Duke Blue Devils',
    normalized_name: 'duke',
    mascot: 'Blue Devils',
    conference: 'ACC',
    is_power_conference: true,
    logo_url: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  away_team: {
    id: 'team-2',
    name: 'North Carolina Tar Heels',
    normalized_name: 'north-carolina',
    mascot: 'Tar Heels',
    conference: 'ACC',
    is_power_conference: true,
    logo_url: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  latest_spread: {
    id: 'spread-1',
    game_id: 'demo-1',
    captured_at: new Date().toISOString(),
    home_spread: -3.5,
    away_spread: 3.5,
    home_spread_odds: -110,
    away_spread_odds: -110,
    home_ml: -160,
    away_ml: 140,
    over_under: 145.5,
    over_odds: -110,
    under_odds: -110,
    source: 'demo',
    is_opening_line: false,
    is_closing_line: false,
  },
  home_ranking: {
    id: 'rank-1',
    team_id: 'team-1',
    season: 2025,
    week: 12,
    poll_date: new Date().toISOString().split('T')[0],
    rank: 9,
    previous_rank: 11,
    first_place_votes: 0,
    total_points: 1234,
    poll_type: 'ap',
    created_at: new Date().toISOString(),
  },
  away_ranking: {
    id: 'rank-2',
    team_id: 'team-2',
    season: 2025,
    week: 12,
    poll_date: new Date().toISOString().split('T')[0],
    rank: 7,
    previous_rank: 6,
    first_place_votes: 0,
    total_points: 1456,
    poll_type: 'ap',
    created_at: new Date().toISOString(),
  },
  prediction: {
    id: 'pred-1',
    game_id: 'demo-1',
    created_at: new Date().toISOString(),
    model_name: 'xgboost',
    model_version: '1.0',
    spread_at_prediction: -3.5,
    predicted_home_cover_prob: 0.58,
    predicted_away_cover_prob: 0.42,
    predicted_home_win_prob: 0.65,
    predicted_margin: 5.2,
    confidence_tier: 'medium',
    recommended_bet: 'home_spread',
    edge_pct: 4.2,
    kelly_fraction: 0.08,
    features_json: null,
  },
  ai_analyses: [
    {
      id: 'ai-1',
      game_id: 'demo-1',
      created_at: new Date().toISOString(),
      ai_provider: 'claude',
      model_used: 'claude-3-sonnet',
      analysis_type: 'matchup',
      prompt_hash: null,
      response: null,
      structured_analysis: null,
      recommended_bet: 'home_spread',
      confidence_score: 0.72,
      key_factors: [
        "Duke's home court advantage at Cameron Indoor is historically dominant",
        'UNC has struggled to cover as road underdogs in rivalry games',
        'Duke coming off strong defensive performance, limiting opponents to 58 PPG last 3 games',
        "Both teams are ranked, but this is a classic 'look-ahead' spot for UNC with Clemson next",
      ],
      reasoning:
        "While UNC has the better ranking, Duke's home court advantage at Cameron Indoor Stadium is one of the most significant in college basketball. The Blue Devils are 8-2 ATS at home this season, and historically cover by 3+ points against ranked ACC opponents. The -3.5 spread undervalues Duke's home dominance in this rivalry.",
      tokens_used: 847,
    },
  ],
};

async function getGame(id: string): Promise<GameWithDetails | null> {
  if (!isSupabaseConfigured() || id.startsWith('demo-')) {
    return DEMO_GAME;
  }

  try {
    // Fetch game with related data
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { data: game, error } = await supabase
      .from('games')
      .select(
        `
        *,
        home_team:teams!games_home_team_id_fkey(*),
        away_team:teams!games_away_team_id_fkey(*)
      `
      )
      .eq('id', id)
      .single() as { data: Record<string, unknown> | null; error: unknown };

    if (error || !game) {
      return null;
    }

    // Access game data with proper typing
    const g = game as Record<string, unknown>;

    // Fetch latest spread
    const { data: spreads } = await supabase
      .from('spreads')
      .select('*')
      .eq('game_id', id)
      .order('captured_at', { ascending: false })
      .limit(1);

    // Fetch rankings (only if we have team IDs)
    let homeRanking = null;
    let awayRanking = null;

    if (g.home_team_id) {
      const { data } = await supabase
        .from('rankings')
        .select('*')
        .eq('team_id', g.home_team_id as string)
        .eq('season', g.season as number)
        .order('week', { ascending: false })
        .limit(1)
        .single();
      homeRanking = data;
    }

    if (g.away_team_id) {
      const { data } = await supabase
        .from('rankings')
        .select('*')
        .eq('team_id', g.away_team_id as string)
        .eq('season', g.season as number)
        .order('week', { ascending: false })
        .limit(1)
        .single();
      awayRanking = data;
    }

    // Fetch prediction
    const { data: prediction } = await supabase
      .from('predictions')
      .select('*')
      .eq('game_id', id)
      .order('created_at', { ascending: false })
      .limit(1)
      .single();

    // Fetch AI analyses
    const { data: aiAnalyses } = await supabase
      .from('ai_analysis')
      .select('*')
      .eq('game_id', id)
      .order('created_at', { ascending: false });

    // Construct the full game object
    const fullGame: GameWithDetails = {
      id: g.id as string,
      external_id: g.external_id as string | null,
      date: g.date as string,
      tip_time: g.tip_time as string | null,
      season: g.season as number,
      home_team_id: g.home_team_id as string | null,
      away_team_id: g.away_team_id as string | null,
      home_score: g.home_score as number | null,
      away_score: g.away_score as number | null,
      is_conference_game: g.is_conference_game as boolean,
      is_tournament: g.is_tournament as boolean,
      tournament_round: g.tournament_round as string | null,
      venue: g.venue as string | null,
      neutral_site: g.neutral_site as boolean,
      status: g.status as GameStatus,
      created_at: g.created_at as string,
      updated_at: g.updated_at as string,
      home_team: g.home_team as Team,
      away_team: g.away_team as Team,
      latest_spread: spreads?.[0] ? (spreads[0] as unknown as Spread) : null,
      home_ranking: homeRanking ? (homeRanking as unknown as Ranking) : null,
      away_ranking: awayRanking ? (awayRanking as unknown as Ranking) : null,
      prediction: prediction ? (prediction as unknown as Prediction) : null,
      ai_analyses: aiAnalyses ? (aiAnalyses as unknown as AIAnalysis[]) : [],
    };

    return fullGame;
  } catch (error) {
    console.error('Error fetching game:', error);
    return null;
  }
}

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function GameDetailPage({ params }: PageProps) {
  const { id } = await params;
  const game = await getGame(id);

  if (!game) {
    notFound();
  }

  const tipTime = game.tip_time
    ? format(new Date(game.tip_time), 'h:mm a')
    : 'TBD';
  const gameDate = format(new Date(game.date), 'EEEE, MMMM d, yyyy');

  return (
    <div className="min-h-screen bg-black text-white">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/50">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <Link
            href="/"
            className="text-gray-400 hover:text-white transition-colors"
          >
            ← Back to Dashboard
          </Link>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Game Header */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="text-sm text-gray-400">
              {gameDate} • {tipTime}
            </div>
            <div className="flex items-center gap-2">
              {game.is_conference_game && (
                <span className="text-xs px-2 py-1 bg-blue-500/20 text-blue-400 rounded">
                  Conference Game
                </span>
              )}
              {game.is_tournament && (
                <span className="text-xs px-2 py-1 bg-purple-500/20 text-purple-400 rounded">
                  Tournament
                </span>
              )}
            </div>
          </div>

          {/* Matchup */}
          <div className="grid grid-cols-3 gap-4 items-center py-6">
            {/* Away Team */}
            <div className="text-center">
              {game.away_ranking?.rank && (
                <div className="text-yellow-500 text-sm font-bold mb-1">
                  #{game.away_ranking.rank}
                </div>
              )}
              <div className="text-2xl font-bold text-white">
                {game.away_team.name}
              </div>
              <div className="text-sm text-gray-400">
                {game.away_team.conference}
              </div>
            </div>

            {/* VS / Score */}
            <div className="text-center">
              {game.status === 'final' ? (
                <div className="text-3xl font-bold">
                  <span
                    className={
                      (game.away_score || 0) > (game.home_score || 0)
                        ? 'text-green-400'
                        : 'text-white'
                    }
                  >
                    {game.away_score}
                  </span>
                  <span className="text-gray-500 mx-2">-</span>
                  <span
                    className={
                      (game.home_score || 0) > (game.away_score || 0)
                        ? 'text-green-400'
                        : 'text-white'
                    }
                  >
                    {game.home_score}
                  </span>
                </div>
              ) : (
                <div className="text-2xl text-gray-500">@</div>
              )}
              {game.venue && (
                <div className="text-xs text-gray-500 mt-2">{game.venue}</div>
              )}
            </div>

            {/* Home Team */}
            <div className="text-center">
              {game.home_ranking?.rank && (
                <div className="text-yellow-500 text-sm font-bold mb-1">
                  #{game.home_ranking.rank}
                </div>
              )}
              <div className="text-2xl font-bold text-white">
                {game.home_team.name}
              </div>
              <div className="text-sm text-gray-400">
                {game.home_team.conference}
              </div>
            </div>
          </div>

          {/* Spread Info */}
          {game.latest_spread && (
            <div className="grid grid-cols-3 gap-4 pt-4 border-t border-gray-800">
              <div className="text-center">
                <div className="text-lg font-medium text-white">
                  {formatSpread(game.latest_spread.away_spread)}
                </div>
                <div className="text-xs text-gray-400">
                  ({game.latest_spread.away_spread_odds})
                </div>
              </div>
              <div className="text-center">
                <div className="text-sm text-gray-400">Total</div>
                <div className="text-lg font-medium text-white">
                  O/U {game.latest_spread.over_under}
                </div>
              </div>
              <div className="text-center">
                <div className="text-lg font-medium text-white">
                  {formatSpread(game.latest_spread.home_spread)}
                </div>
                <div className="text-xs text-gray-400">
                  ({game.latest_spread.home_spread_odds})
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Prediction */}
          <div className="space-y-6">
            {/* Model Prediction */}
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
              <h3 className="text-lg font-semibold text-white mb-4">
                Model Prediction
              </h3>

              {game.prediction ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Confidence</span>
                    <ConfidenceBadge tier={game.prediction.confidence_tier} />
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Home Cover Prob</span>
                    <span className="text-white font-medium">
                      {formatProbability(
                        game.prediction.predicted_home_cover_prob
                      )}
                    </span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Away Cover Prob</span>
                    <span className="text-white font-medium">
                      {formatProbability(
                        game.prediction.predicted_away_cover_prob
                      )}
                    </span>
                  </div>

                  {game.prediction.predicted_margin && (
                    <div className="flex items-center justify-between">
                      <span className="text-gray-400">Predicted Margin</span>
                      <span className="text-white font-medium">
                        {game.home_team.name.split(' ')[0]}{' '}
                        {game.prediction.predicted_margin > 0 ? '+' : ''}
                        {game.prediction.predicted_margin.toFixed(1)}
                      </span>
                    </div>
                  )}

                  {game.prediction.edge_pct && game.prediction.edge_pct > 0 && (
                    <div className="flex items-center justify-between">
                      <span className="text-gray-400">Edge</span>
                      <span className="text-green-400 font-medium">
                        +{game.prediction.edge_pct.toFixed(1)}%
                      </span>
                    </div>
                  )}

                  {/* Recommendation */}
                  {game.prediction.recommended_bet &&
                    game.prediction.recommended_bet !== 'pass' && (
                      <div className="mt-4 p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
                        <div className="text-sm text-green-400 font-medium mb-1">
                          Recommended Bet
                        </div>
                        <div className="text-white font-semibold">
                          {game.prediction.recommended_bet.includes('home')
                            ? game.home_team.name
                            : game.away_team.name}{' '}
                          {game.prediction.recommended_bet.includes('spread')
                            ? formatSpread(
                                game.prediction.recommended_bet.includes('home')
                                  ? game.latest_spread?.home_spread || null
                                  : game.latest_spread?.away_spread || null
                              )
                            : 'ML'}
                        </div>
                      </div>
                    )}

                  <div className="text-xs text-gray-500 pt-2 border-t border-gray-800">
                    Model: {game.prediction.model_name} v
                    {game.prediction.model_version}
                  </div>
                </div>
              ) : (
                <div className="text-center py-6 text-gray-400">
                  No prediction available yet
                </div>
              )}
            </div>

            {/* Moneylines */}
            {game.latest_spread && (
              <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-white mb-4">
                  Moneylines
                </h3>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-300">{game.away_team.name}</span>
                    <span
                      className={`font-medium ${
                        (game.latest_spread.away_ml || 0) > 0
                          ? 'text-green-400'
                          : 'text-white'
                      }`}
                    >
                      {formatMoneyline(game.latest_spread.away_ml)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-300">{game.home_team.name}</span>
                    <span
                      className={`font-medium ${
                        (game.latest_spread.home_ml || 0) > 0
                          ? 'text-green-400'
                          : 'text-white'
                      }`}
                    >
                      {formatMoneyline(game.latest_spread.home_ml)}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Column - AI Analysis */}
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">
                AI Analysis
              </h3>
              <div className="w-48">
                <AIAnalysisButton
                  gameId={game.id}
                  hasExistingAnalysis={game.ai_analyses.length > 0}
                />
              </div>
            </div>
            <AIAnalysisPanel analyses={game.ai_analyses} />
          </div>
        </div>
      </main>
    </div>
  );
}
