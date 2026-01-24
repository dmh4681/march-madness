import { notFound } from 'next/navigation';
import Link from 'next/link';
import { format } from 'date-fns';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';
import type { GameWithDetails, AIAnalysis, Prediction, Team, Spread, Ranking, GameStatus, KenPomRating, HaslametricsRating } from '@/lib/types';
import { formatSpread, formatMoneyline, formatProbability } from '@/lib/api';
import { ConfidenceBadge } from '@/components/ConfidenceBadge';
import { AIAnalysisPanel } from '@/components/AIAnalysis';
import { AIAnalysisButton } from '@/components/AIAnalysisButton';

// Force dynamic rendering to always fetch fresh data
export const dynamic = 'force-dynamic';
export const revalidate = 0;

async function getGame(id: string): Promise<GameWithDetails | null> {
  if (!isSupabaseConfigured()) {
    return null;
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

    // Fetch KenPom ratings
    let homeKenpom = null;
    let awayKenpom = null;

    if (g.home_team_id) {
      const { data } = await supabase
        .from('kenpom_ratings')
        .select('*')
        .eq('team_id', g.home_team_id as string)
        .eq('season', g.season as number)
        .order('captured_at', { ascending: false })
        .limit(1)
        .single();
      homeKenpom = data;
    }

    if (g.away_team_id) {
      const { data } = await supabase
        .from('kenpom_ratings')
        .select('*')
        .eq('team_id', g.away_team_id as string)
        .eq('season', g.season as number)
        .order('captured_at', { ascending: false })
        .limit(1)
        .single();
      awayKenpom = data;
    }

    // Fetch Haslametrics ratings
    let homeHaslametrics = null;
    let awayHaslametrics = null;

    if (g.home_team_id) {
      const { data } = await supabase
        .from('haslametrics_ratings')
        .select('*')
        .eq('team_id', g.home_team_id as string)
        .eq('season', g.season as number)
        .order('captured_at', { ascending: false })
        .limit(1)
        .single();
      homeHaslametrics = data;
    }

    if (g.away_team_id) {
      const { data } = await supabase
        .from('haslametrics_ratings')
        .select('*')
        .eq('team_id', g.away_team_id as string)
        .eq('season', g.season as number)
        .order('captured_at', { ascending: false })
        .limit(1)
        .single();
      awayHaslametrics = data;
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
      home_kenpom: homeKenpom ? (homeKenpom as unknown as KenPomRating) : null,
      away_kenpom: awayKenpom ? (awayKenpom as unknown as KenPomRating) : null,
      home_haslametrics: homeHaslametrics ? (homeHaslametrics as unknown as HaslametricsRating) : null,
      away_haslametrics: awayHaslametrics ? (awayHaslametrics as unknown as HaslametricsRating) : null,
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

  // Check for real tip time (not midnight placeholder)
  const hasRealTipTime = game.tip_time && !game.tip_time.endsWith('T00:00:00Z');
  const tipTime = hasRealTipTime
    ? new Date(game.tip_time!).toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        timeZone: 'America/New_York',
      }) + ' ET'
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
            {/* Model Stats - Quick baseline metrics */}
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
              <h3 className="text-lg font-semibold text-white mb-1">
                Quick Stats
              </h3>
              <p className="text-xs text-gray-500 mb-4">
                Baseline model {game.ai_analyses.length > 0 && '(see AI Analysis for detailed pick)'}
              </p>

              {game.prediction ? (
                <div className="space-y-4">
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

                  {/* Only show baseline recommendation if no AI analysis exists */}
                  {game.ai_analyses.length === 0 &&
                    game.prediction.recommended_bet &&
                    game.prediction.recommended_bet !== 'pass' && (
                      <div className="mt-4 p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                        <div className="text-sm text-blue-400 font-medium mb-1">
                          Baseline Pick
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
                    Model: {game.prediction.model_name}
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

            {/* KenPom Analytics */}
            {(game.home_kenpom || game.away_kenpom) && (
              <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-white mb-4">
                  KenPom Analytics
                </h3>
                <div className="space-y-3">
                  {/* KenPom Rank */}
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div className="text-right font-medium text-white">
                      #{game.away_kenpom?.rank ?? 'N/A'}
                    </div>
                    <div className="text-center text-gray-400">Rank</div>
                    <div className="text-left font-medium text-white">
                      #{game.home_kenpom?.rank ?? 'N/A'}
                    </div>
                  </div>

                  {/* Adj. Efficiency Margin */}
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div className={`text-right font-medium ${
                      (game.away_kenpom?.adj_efficiency_margin ?? 0) > (game.home_kenpom?.adj_efficiency_margin ?? 0)
                        ? 'text-green-400'
                        : 'text-white'
                    }`}>
                      {game.away_kenpom?.adj_efficiency_margin?.toFixed(1) ?? 'N/A'}
                    </div>
                    <div className="text-center text-gray-400">AdjEM</div>
                    <div className={`text-left font-medium ${
                      (game.home_kenpom?.adj_efficiency_margin ?? 0) > (game.away_kenpom?.adj_efficiency_margin ?? 0)
                        ? 'text-green-400'
                        : 'text-white'
                    }`}>
                      {game.home_kenpom?.adj_efficiency_margin?.toFixed(1) ?? 'N/A'}
                    </div>
                  </div>

                  {/* Adj. Offense */}
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div className={`text-right font-medium ${
                      (game.away_kenpom?.adj_offense ?? 0) > (game.home_kenpom?.adj_offense ?? 0)
                        ? 'text-green-400'
                        : 'text-white'
                    }`}>
                      {game.away_kenpom?.adj_offense?.toFixed(1) ?? 'N/A'}
                    </div>
                    <div className="text-center text-gray-400">AdjO</div>
                    <div className={`text-left font-medium ${
                      (game.home_kenpom?.adj_offense ?? 0) > (game.away_kenpom?.adj_offense ?? 0)
                        ? 'text-green-400'
                        : 'text-white'
                    }`}>
                      {game.home_kenpom?.adj_offense?.toFixed(1) ?? 'N/A'}
                    </div>
                  </div>

                  {/* Adj. Defense (lower is better) */}
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div className={`text-right font-medium ${
                      (game.away_kenpom?.adj_defense ?? 999) < (game.home_kenpom?.adj_defense ?? 999)
                        ? 'text-green-400'
                        : 'text-white'
                    }`}>
                      {game.away_kenpom?.adj_defense?.toFixed(1) ?? 'N/A'}
                    </div>
                    <div className="text-center text-gray-400">AdjD</div>
                    <div className={`text-left font-medium ${
                      (game.home_kenpom?.adj_defense ?? 999) < (game.away_kenpom?.adj_defense ?? 999)
                        ? 'text-green-400'
                        : 'text-white'
                    }`}>
                      {game.home_kenpom?.adj_defense?.toFixed(1) ?? 'N/A'}
                    </div>
                  </div>

                  {/* Tempo */}
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div className="text-right font-medium text-white">
                      {game.away_kenpom?.adj_tempo?.toFixed(1) ?? 'N/A'}
                    </div>
                    <div className="text-center text-gray-400">Tempo</div>
                    <div className="text-left font-medium text-white">
                      {game.home_kenpom?.adj_tempo?.toFixed(1) ?? 'N/A'}
                    </div>
                  </div>

                  {/* SOS */}
                  {(game.home_kenpom?.sos_adj_em || game.away_kenpom?.sos_adj_em) && (
                    <div className="grid grid-cols-3 gap-2 text-sm">
                      <div className={`text-right font-medium ${
                        (game.away_kenpom?.sos_adj_em ?? 0) > (game.home_kenpom?.sos_adj_em ?? 0)
                          ? 'text-green-400'
                          : 'text-white'
                      }`}>
                        {game.away_kenpom?.sos_adj_em?.toFixed(1) ?? 'N/A'}
                      </div>
                      <div className="text-center text-gray-400">SOS</div>
                      <div className={`text-left font-medium ${
                        (game.home_kenpom?.sos_adj_em ?? 0) > (game.away_kenpom?.sos_adj_em ?? 0)
                          ? 'text-green-400'
                          : 'text-white'
                      }`}>
                        {game.home_kenpom?.sos_adj_em?.toFixed(1) ?? 'N/A'}
                      </div>
                    </div>
                  )}

                  {/* Luck */}
                  {(game.home_kenpom?.luck !== null || game.away_kenpom?.luck !== null) && (
                    <div className="grid grid-cols-3 gap-2 text-sm">
                      <div className="text-right font-medium text-white">
                        {game.away_kenpom?.luck?.toFixed(3) ?? 'N/A'}
                      </div>
                      <div className="text-center text-gray-400">Luck</div>
                      <div className="text-left font-medium text-white">
                        {game.home_kenpom?.luck?.toFixed(3) ?? 'N/A'}
                      </div>
                    </div>
                  )}

                  {/* Record */}
                  <div className="grid grid-cols-3 gap-2 text-sm pt-2 border-t border-gray-800">
                    <div className="text-right font-medium text-white">
                      {game.away_kenpom?.wins ?? 0}-{game.away_kenpom?.losses ?? 0}
                    </div>
                    <div className="text-center text-gray-400">Record</div>
                    <div className="text-left font-medium text-white">
                      {game.home_kenpom?.wins ?? 0}-{game.home_kenpom?.losses ?? 0}
                    </div>
                  </div>
                </div>

                <div className="text-xs text-gray-500 mt-4 text-center">
                  Data from KenPom.com
                </div>
              </div>
            )}

            {/* Haslametrics Analytics */}
            {(game.home_haslametrics || game.away_haslametrics) && (
              <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-white mb-1">
                  Haslametrics Analytics
                </h3>
                <p className="text-xs text-gray-500 mb-4">All-Play Methodology (FREE)</p>
                <div className="space-y-3">
                  {/* Haslametrics Rank */}
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div className="text-right font-medium text-white">
                      #{game.away_haslametrics?.rank ?? 'N/A'}
                    </div>
                    <div className="text-center text-gray-400">Rank</div>
                    <div className="text-left font-medium text-white">
                      #{game.home_haslametrics?.rank ?? 'N/A'}
                    </div>
                  </div>

                  {/* All-Play % - unique Haslametrics metric */}
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div className={`text-right font-medium ${
                      (game.away_haslametrics?.all_play_pct ?? 0) > (game.home_haslametrics?.all_play_pct ?? 0)
                        ? 'text-green-400'
                        : 'text-white'
                    }`}>
                      {game.away_haslametrics?.all_play_pct?.toFixed(1) ?? 'N/A'}%
                    </div>
                    <div className="text-center text-gray-400">All-Play %</div>
                    <div className={`text-left font-medium ${
                      (game.home_haslametrics?.all_play_pct ?? 0) > (game.away_haslametrics?.all_play_pct ?? 0)
                        ? 'text-green-400'
                        : 'text-white'
                    }`}>
                      {game.home_haslametrics?.all_play_pct?.toFixed(1) ?? 'N/A'}%
                    </div>
                  </div>

                  {/* Momentum - trending indicator */}
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div className={`text-right font-medium ${
                      (game.away_haslametrics?.momentum_overall ?? 0) > 0 ? 'text-green-400' :
                      (game.away_haslametrics?.momentum_overall ?? 0) < 0 ? 'text-red-400' : 'text-white'
                    }`}>
                      {game.away_haslametrics?.momentum_overall != null
                        ? (game.away_haslametrics.momentum_overall > 0 ? '+' : '') + game.away_haslametrics.momentum_overall.toFixed(3)
                        : 'N/A'}
                    </div>
                    <div className="text-center text-gray-400">Momentum</div>
                    <div className={`text-left font-medium ${
                      (game.home_haslametrics?.momentum_overall ?? 0) > 0 ? 'text-green-400' :
                      (game.home_haslametrics?.momentum_overall ?? 0) < 0 ? 'text-red-400' : 'text-white'
                    }`}>
                      {game.home_haslametrics?.momentum_overall != null
                        ? (game.home_haslametrics.momentum_overall > 0 ? '+' : '') + game.home_haslametrics.momentum_overall.toFixed(3)
                        : 'N/A'}
                    </div>
                  </div>

                  {/* Offensive Efficiency */}
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div className={`text-right font-medium ${
                      (game.away_haslametrics?.offensive_efficiency ?? 0) > (game.home_haslametrics?.offensive_efficiency ?? 0)
                        ? 'text-green-400'
                        : 'text-white'
                    }`}>
                      {game.away_haslametrics?.offensive_efficiency?.toFixed(1) ?? 'N/A'}
                    </div>
                    <div className="text-center text-gray-400">Off Eff</div>
                    <div className={`text-left font-medium ${
                      (game.home_haslametrics?.offensive_efficiency ?? 0) > (game.away_haslametrics?.offensive_efficiency ?? 0)
                        ? 'text-green-400'
                        : 'text-white'
                    }`}>
                      {game.home_haslametrics?.offensive_efficiency?.toFixed(1) ?? 'N/A'}
                    </div>
                  </div>

                  {/* Defensive Efficiency (lower is better) */}
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div className={`text-right font-medium ${
                      (game.away_haslametrics?.defensive_efficiency ?? 999) < (game.home_haslametrics?.defensive_efficiency ?? 999)
                        ? 'text-green-400'
                        : 'text-white'
                    }`}>
                      {game.away_haslametrics?.defensive_efficiency?.toFixed(1) ?? 'N/A'}
                    </div>
                    <div className="text-center text-gray-400">Def Eff</div>
                    <div className={`text-left font-medium ${
                      (game.home_haslametrics?.defensive_efficiency ?? 999) < (game.away_haslametrics?.defensive_efficiency ?? 999)
                        ? 'text-green-400'
                        : 'text-white'
                    }`}>
                      {game.home_haslametrics?.defensive_efficiency?.toFixed(1) ?? 'N/A'}
                    </div>
                  </div>

                  {/* Last 5 */}
                  <div className="grid grid-cols-3 gap-2 text-sm pt-2 border-t border-gray-800">
                    <div className="text-right font-medium text-white">
                      {game.away_haslametrics?.last_5_record ?? 'N/A'}
                    </div>
                    <div className="text-center text-gray-400">Last 5</div>
                    <div className="text-left font-medium text-white">
                      {game.home_haslametrics?.last_5_record ?? 'N/A'}
                    </div>
                  </div>

                  {/* Quadrant 1 Record */}
                  {(game.home_haslametrics?.quad_1_record || game.away_haslametrics?.quad_1_record) && (
                    <div className="grid grid-cols-3 gap-2 text-sm">
                      <div className="text-right font-medium text-white">
                        {game.away_haslametrics?.quad_1_record ?? 'N/A'}
                      </div>
                      <div className="text-center text-gray-400">Q1 Record</div>
                      <div className="text-left font-medium text-white">
                        {game.home_haslametrics?.quad_1_record ?? 'N/A'}
                      </div>
                    </div>
                  )}
                </div>

                <div className="text-xs text-gray-500 mt-4 text-center">
                  Data from Haslametrics.com (FREE)
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
                  hasClaudeAnalysis={game.ai_analyses.some(a => a.ai_provider === 'claude')}
                  hasGrokAnalysis={game.ai_analyses.some(a => a.ai_provider === 'grok')}
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
