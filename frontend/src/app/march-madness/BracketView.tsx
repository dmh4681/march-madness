'use client';

import { useState, useMemo, useTransition, type ReactNode } from 'react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { formatSpread } from '@/lib/api';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import type {
  Tournament,
  BracketMatchup,
  RegionSeedEntry,
  TournamentRegion,
  TournamentRound,
} from '@/lib/types';

// ============================================
// Constants
// ============================================

const REGIONS: TournamentRegion[] = ['East', 'West', 'South', 'Midwest'];

const ROUND_ORDER: TournamentRound[] = [
  'first_four',
  'round_64',
  'round_32',
  'sweet_16',
  'elite_8',
  'final_4',
  'championship',
];

const ROUND_LABELS: Record<TournamentRound, string> = {
  first_four: 'First Four',
  round_64: 'R64',
  round_32: 'R32',
  sweet_16: 'Sweet 16',
  elite_8: 'Elite 8',
  final_4: 'Final Four',
  championship: 'Championship',
};

const KEY_DATES = [
  { date: 'March 16', event: 'Selection Sunday', shortEvent: 'Selection' },
  { date: 'March 18-19', event: 'First Four', shortEvent: 'First Four' },
  { date: 'March 20-21', event: 'Round of 64', shortEvent: 'Rd of 64' },
  { date: 'March 22-23', event: 'Round of 32', shortEvent: 'Rd of 32' },
  { date: 'March 27-28', event: 'Sweet 16', shortEvent: 'Sweet 16' },
  { date: 'March 29-30', event: 'Elite Eight', shortEvent: 'Elite 8' },
  { date: 'April 5', event: 'Final Four', shortEvent: 'Final 4' },
  { date: 'April 7', event: 'National Championship', shortEvent: 'Title Game' },
];

// ============================================
// Props
// ============================================

interface BracketViewProps {
  tournament: Tournament | null;
  matchups: BracketMatchup[];
  regionSeeds: RegionSeedEntry[];
  isDemo: boolean;
  pickedCount: number;
  correctPct: number | null;
}

function StaleDataBanner() {
  return (
    <div className="mb-4 px-3 py-2 bg-yellow-500/10 border border-yellow-500/20 rounded-lg flex items-center gap-2 text-sm">
      <svg className="w-4 h-4 text-yellow-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <span className="text-yellow-300">
        Bracket data may be stale. Refresh the page for the latest results.
      </span>
    </div>
  );
}

// ============================================
// MatchupRow
// ============================================

function MatchupRow({ matchup }: { matchup: BracketMatchup }) {
  const isFinal = matchup.game_status === 'final';
  const homeWon = isFinal && (matchup.home_score ?? 0) > (matchup.away_score ?? 0);
  const awayWon = isFinal && (matchup.away_score ?? 0) > (matchup.home_score ?? 0);

  return (
    <Link
      href={`/games/${matchup.game_id}`}
      className="block px-3 sm:px-4 py-3 hover:bg-gray-800/50 transition-colors border-b border-gray-800 last:border-0"
    >
      {/* Line 1: Teams + Score */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0 flex-1">
          {/* Round badge */}
          <span className="text-[10px] sm:text-xs text-gray-500 font-medium w-6 sm:w-8 shrink-0">
            {ROUND_LABELS[matchup.tournament_round] ?? matchup.tournament_round}
          </span>
          {/* Home team */}
          <span className={cn(
            "text-xs sm:text-sm font-medium truncate",
            homeWon ? "text-green-400" : "text-white"
          )}>
            {matchup.home_seed != null && (
              <span className="text-gray-500 mr-0.5">#{matchup.home_seed}</span>
            )}
            {matchup.home_team}
          </span>
          <span className="text-gray-600 text-xs shrink-0">vs</span>
          {/* Away team */}
          <span className={cn(
            "text-xs sm:text-sm font-medium truncate",
            awayWon ? "text-green-400" : "text-white"
          )}>
            {matchup.away_seed != null && (
              <span className="text-gray-500 mr-0.5">#{matchup.away_seed}</span>
            )}
            {matchup.away_team}
          </span>
        </div>

        {/* Score or status */}
        <div className="shrink-0 text-right">
          {isFinal ? (
            <span className="text-xs sm:text-sm text-gray-300 font-mono">
              <span className={homeWon ? "text-green-400" : ""}>{matchup.home_score}</span>
              <span className="text-gray-600 mx-0.5">-</span>
              <span className={awayWon ? "text-green-400" : ""}>{matchup.away_score}</span>
            </span>
          ) : matchup.game_status === 'in_progress' ? (
            <span className="text-xs text-orange-400">Live</span>
          ) : (
            matchup.home_spread != null && (
              <span className="text-xs text-gray-500">{formatSpread(matchup.home_spread)}</span>
            )
          )}
        </div>
      </div>

      {/* Line 2: Pick indicator */}
      {matchup.picked_team && (
        <div className="flex items-center gap-1.5 mt-1 ml-7 sm:ml-9">
          <span className="text-[10px] sm:text-xs text-gray-500">Pick:</span>
          <span className="text-xs text-gray-300">{matchup.picked_team}</span>
          {matchup.is_correct === true && (
            <svg className="w-3.5 h-3.5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          )}
          {matchup.is_correct === false && (
            <svg className="w-3.5 h-3.5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          )}
          {matchup.is_correct === null && (
            <svg className="w-3.5 h-3.5 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          )}
          {matchup.pick_confidence != null && (
            <span className="text-[10px] text-gray-500">{Math.round(matchup.pick_confidence * 100)}%</span>
          )}
        </div>
      )}
    </Link>
  );
}

// ============================================
// RegionCardErrorBoundary
// ============================================

function RegionCardErrorBoundary({ region, children }: { region: string; children: ReactNode }) {
  return (
    <ErrorBoundary
      onError={(error) => {
        console.error(`[BracketView] ${region} region failed to render:`, error);
      }}
      fallbackRender={({ retry }) => (
        <div className="bg-gray-900 border border-red-500/20 rounded-lg overflow-hidden">
          <div className="px-3 sm:px-4 py-2.5 sm:py-3 border-b border-gray-800">
            <h3 className="text-sm sm:text-base font-bold text-white uppercase tracking-wide">
              {region}
            </h3>
          </div>
          <div className="px-4 py-6 text-center">
            <p className="text-sm text-red-400 mb-2">Failed to render {region} matchups</p>
            <button
              type="button"
              onClick={retry}
              className="text-xs text-orange-400 hover:text-orange-300 transition-colors"
            >
              Try again
            </button>
          </div>
        </div>
      )}
    >
      {children}
    </ErrorBoundary>
  );
}

// ============================================
// RegionCard
// ============================================

function RegionCard({
  region,
  matchups,
  seeds,
}: {
  region: TournamentRegion;
  matchups: BracketMatchup[];
  seeds: RegionSeedEntry[];
}) {
  const aliveCount = seeds.filter(s => s.is_alive).length;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-3 sm:px-4 py-2.5 sm:py-3 border-b border-gray-800 flex items-center justify-between">
        <h3 className="text-sm sm:text-base font-bold text-white uppercase tracking-wide">
          {region}
        </h3>
        {seeds.length > 0 && (
          <span className="text-xs text-gray-400">
            {aliveCount}/{seeds.length} alive
          </span>
        )}
      </div>

      {/* Matchups */}
      {matchups.length > 0 ? (
        <div>
          {matchups.map((m) => (
            <MatchupRow key={m.game_id} matchup={m} />
          ))}
        </div>
      ) : seeds.length > 0 ? (
        <div className="px-4 py-6 text-center">
          <p className="text-sm text-gray-500">Games not yet scheduled</p>
          <p className="text-xs text-gray-600 mt-1">{seeds.length} teams seeded</p>
        </div>
      ) : (
        <div className="px-4 py-6 text-center">
          <p className="text-sm text-gray-500">Seeds not yet assigned</p>
        </div>
      )}
    </div>
  );
}

// ============================================
// RegionSeedSidebar
// ============================================

function RegionSeedSidebar({ regionSeeds }: { regionSeeds: RegionSeedEntry[] }) {
  const [expandedRegion, setExpandedRegion] = useState<TournamentRegion | null>('East');

  const seedsByRegion = useMemo(() => {
    const grouped: Record<string, RegionSeedEntry[]> = {};
    for (const seed of regionSeeds) {
      (grouped[seed.region] ??= []).push(seed);
    }
    return grouped;
  }, [regionSeeds]);

  if (regionSeeds.length === 0) return null;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-800">
        <h3 className="text-sm font-semibold text-white">Tournament Seeds</h3>
      </div>
      {REGIONS.map((region) => {
        const seeds = seedsByRegion[region] ?? [];
        const isExpanded = expandedRegion === region;
        return (
          <div key={region} className="border-b border-gray-800 last:border-0">
            <button
              type="button"
              onClick={() => setExpandedRegion(isExpanded ? null : region)}
              className="w-full px-4 py-2.5 flex items-center justify-between hover:bg-gray-800/50 transition-colors min-h-[44px]"
            >
              <span className="text-sm font-medium text-gray-300">{region}</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">
                  {seeds.filter(s => s.is_alive).length} alive
                </span>
                <svg
                  className={cn(
                    "w-4 h-4 text-gray-500 transition-transform",
                    isExpanded && "rotate-180"
                  )}
                  fill="none" viewBox="0 0 24 24" stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </div>
            </button>
            {isExpanded && (
              <div className="px-4 pb-3 space-y-1">
                {seeds.map((seed) => (
                  <div
                    key={`${seed.region}-${seed.seed}-${seed.team_name}`}
                    className="flex items-center justify-between py-1"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-xs text-gray-500 w-4 text-right shrink-0">
                        {seed.seed}
                      </span>
                      <span className={cn(
                        "text-xs truncate",
                        seed.is_alive ? "text-gray-300" : "text-gray-600 line-through"
                      )}>
                        {seed.team_name}
                      </span>
                      {seed.is_play_in && (
                        <span className="text-[9px] px-1 py-0.5 bg-orange-500/20 text-orange-400 rounded shrink-0">
                          PI
                        </span>
                      )}
                    </div>
                    {seed.is_alive ? (
                      <span className="w-1.5 h-1.5 rounded-full bg-green-400 shrink-0" />
                    ) : (
                      <span className="text-[9px] text-red-400/70 shrink-0">
                        {ROUND_LABELS[seed.eliminated_in_round as TournamentRound] ?? 'OUT'}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ============================================
// BracketView (main export)
// ============================================

export function BracketView({
  tournament,
  matchups,
  regionSeeds,
  isDemo,
  pickedCount,
  correctPct,
}: BracketViewProps) {
  const [selectedRegion, setSelectedRegion] = useState<TournamentRegion | 'All'>('All');
  const [selectedRound, setSelectedRound] = useState<TournamentRound | 'All'>('All');
  const [isPending, startTransition] = useTransition();

  // Available rounds (only show tabs for rounds that exist)
  const availableRounds = useMemo(() => {
    const rounds = new Set(matchups.map(m => m.tournament_round));
    return ROUND_ORDER.filter(r => rounds.has(r));
  }, [matchups]);

  // Filter matchups by region and round
  const filteredMatchups = useMemo(() => {
    return matchups.filter(m => {
      const regionMatch =
        selectedRegion === 'All' ||
        m.home_region === selectedRegion ||
        m.away_region === selectedRegion;
      const roundMatch =
        selectedRound === 'All' || m.tournament_round === selectedRound;
      return regionMatch && roundMatch;
    });
  }, [matchups, selectedRegion, selectedRound]);

  // Group matchups by region for region cards
  const matchupsByRegion = useMemo(() => {
    return REGIONS.map(region => ({
      region,
      matchups: filteredMatchups.filter(
        m => m.home_region === region || m.away_region === region
      ),
      seeds: regionSeeds.filter(s => s.region === region),
    }));
  }, [filteredMatchups, regionSeeds]);

  // Cross-region games (Final Four / Championship)
  const crossRegionMatchups = useMemo(() => {
    return filteredMatchups.filter(
      m => m.home_region !== m.away_region
    );
  }, [filteredMatchups]);

  const isBracketSet = tournament && tournament.status !== 'upcoming';

  // Detect potentially stale data: tournament in_progress but no matchup data loaded
  const isStale = isBracketSet && tournament.status === 'in_progress' && matchups.length === 0;

  // ---- Pre-selection empty state ----
  if (!isBracketSet) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-8">
        {/* Key Dates */}
        <div className="lg:col-span-1 order-2 lg:order-1">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 sm:p-6">
            <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4">
              Key Dates
            </h2>
            {/* Mobile: Horizontal scroll */}
            <div className="sm:hidden overflow-x-auto -mx-4 px-4">
              <div className="flex gap-3 pb-2 scrollbar-hide min-w-max">
                {KEY_DATES.map((item, idx) => (
                  <div key={idx} className="bg-gray-800/50 rounded-lg p-3 min-w-[140px] shrink-0">
                    <p className="text-white font-medium text-sm">{item.shortEvent}</p>
                    <p className="text-xs text-gray-400">{item.date}</p>
                  </div>
                ))}
              </div>
            </div>
            {/* Desktop: Vertical list */}
            <div className="hidden sm:block space-y-3">
              {KEY_DATES.map((item, idx) => (
                <div key={idx} className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
                  <div>
                    <p className="text-white font-medium">{item.event}</p>
                    <p className="text-sm text-gray-400">{item.date}</p>
                  </div>
                  <span className="text-xs px-2.5 py-1 min-h-[32px] flex items-center bg-yellow-500/20 text-yellow-400 rounded">
                    Upcoming
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Bracket not set */}
        <div className="lg:col-span-2 order-1 lg:order-2">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 sm:p-8">
            <div className="text-center">
              <h2 className="text-xl sm:text-2xl font-bold text-white mb-2 sm:mb-4">
                Bracket Not Yet Set
              </h2>
              <p className="text-sm sm:text-base text-gray-400 mb-4 sm:mb-6 max-w-lg mx-auto">
                The tournament bracket will be populated after Selection Sunday.
                Check back for AI-powered analysis of every matchup.
              </p>
              <div className="bg-gray-800/50 rounded-lg p-4 sm:p-6 text-left max-w-md mx-auto mb-4 sm:mb-6">
                <h3 className="text-white font-semibold mb-2 sm:mb-3 text-sm sm:text-base">What to expect:</h3>
                <ul className="text-gray-400 space-y-1.5 sm:space-y-2 text-sm">
                  <li className="flex items-start gap-2">
                    <span className="text-orange-400 mt-0.5">&bull;</span>
                    Claude + Grok AI analysis on every game
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-orange-400 mt-0.5">&bull;</span>
                    Upset probability ratings per matchup
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-orange-400 mt-0.5">&bull;</span>
                    KenPom + Haslametrics matchup data
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-orange-400 mt-0.5">&bull;</span>
                    Bracket pick tracking with accuracy stats
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-orange-400 mt-0.5">&bull;</span>
                    Seed trend analysis and value bets
                  </li>
                </ul>
              </div>
              <Link
                href="/"
                className="inline-flex items-center justify-center px-5 sm:px-6 py-3 min-h-[48px] bg-orange-600 hover:bg-orange-700 active:bg-orange-800 text-white rounded-lg transition-colors text-sm sm:text-base font-medium"
              >
                View Today&apos;s Games
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ---- Post-selection bracket view ----
  return (
    <>
      {/* ARIA live region announces filter changes to screen readers */}
      <div role="status" aria-live="polite" aria-atomic="true" className="sr-only">
        {isPending
          ? 'Loading bracket...'
          : selectedRegion === 'All' && selectedRound === 'All'
          ? 'Showing all matchups'
          : `Showing ${selectedRegion === 'All' ? 'all regions' : selectedRegion}${selectedRound !== 'All' ? `, ${ROUND_LABELS[selectedRound]}` : ''}`
        }
      </div>

      {isStale && <StaleDataBanner />}

      {/* Region filter tabs */}
      <div className="mb-4 -mx-3 px-3 sm:mx-0 sm:px-0">
        <div className="flex items-center gap-2">
          <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide flex-1">
            {(['All', ...REGIONS] as const).map((region) => (
              <button
                key={region}
                type="button"
                onClick={() => startTransition(() => setSelectedRegion(region === 'All' ? 'All' : region))}
                className={cn(
                  "px-4 py-2 min-h-[44px] text-sm font-medium rounded-lg shrink-0 transition-colors",
                  selectedRegion === region
                    ? "bg-orange-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                )}
              >
                {region}
              </button>
            ))}
          </div>
          {/* Spinner visible during transition */}
          {isPending && (
            <svg
              className="w-4 h-4 text-orange-400 animate-spin shrink-0 mb-2"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          )}
        </div>
      </div>

      {/* Round filter pills */}
      {availableRounds.length > 1 && (
        <div className="mb-4 -mx-3 px-3 sm:mx-0 sm:px-0">
          <div className="flex gap-1.5 overflow-x-auto pb-2 scrollbar-hide">
            <button
              type="button"
              onClick={() => startTransition(() => setSelectedRound('All'))}
              className={cn(
                "px-3 py-1.5 min-h-[36px] text-xs font-medium rounded-md shrink-0 transition-colors",
                selectedRound === 'All'
                  ? "bg-gray-700 text-white"
                  : "bg-gray-800/50 text-gray-500 hover:text-gray-300"
              )}
            >
              All Rounds
            </button>
            {availableRounds.map((round) => (
              <button
                key={round}
                type="button"
                onClick={() => startTransition(() => setSelectedRound(round))}
                className={cn(
                  "px-3 py-1.5 min-h-[36px] text-xs font-medium rounded-md shrink-0 transition-colors",
                  selectedRound === round
                    ? "bg-gray-700 text-white"
                    : "bg-gray-800/50 text-gray-500 hover:text-gray-300"
                )}
              >
                {ROUND_LABELS[round]}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Main grid: sidebar + region cards */}
      <div className={cn("grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6 transition-opacity duration-150", isPending && "opacity-50")}>
        {/* Seed sidebar - desktop only */}
        <div className="hidden lg:block lg:col-span-1">
          <div className="sticky top-[80px]">
            <RegionSeedSidebar regionSeeds={regionSeeds} />
          </div>
        </div>

        {/* Region cards */}
        <div className="lg:col-span-2">
          {selectedRegion === 'All' ? (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {matchupsByRegion.map(({ region, matchups: regionMatchups, seeds }) => (
                  <RegionCardErrorBoundary key={region} region={region}>
                    <RegionCard
                      region={region}
                      matchups={regionMatchups}
                      seeds={seeds}
                    />
                  </RegionCardErrorBoundary>
                ))}
              </div>
              {/* Cross-region games (Final Four / Championship) */}
              {crossRegionMatchups.length > 0 && (
                <div className="mt-4">
                  <RegionCardErrorBoundary region="Final Four">
                    <RegionCard
                      region={"Final Four" as TournamentRegion}
                      matchups={crossRegionMatchups}
                      seeds={[]}
                    />
                  </RegionCardErrorBoundary>
                </div>
              )}
            </>
          ) : (
            // Single region selected - full width
            <RegionCardErrorBoundary region={selectedRegion}>
              <RegionCard
                region={selectedRegion as TournamentRegion}
                matchups={filteredMatchups}
                seeds={regionSeeds.filter(s => s.region === selectedRegion)}
              />
            </RegionCardErrorBoundary>
          )}

          {filteredMatchups.length === 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center mt-4">
              <p className="text-gray-400">No matchups for the selected filters</p>
              <button
                type="button"
                onClick={() => { setSelectedRegion('All'); setSelectedRound('All'); }}
                className="text-sm text-orange-400 hover:text-orange-300 mt-2 transition-colors"
              >
                Clear filters
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
