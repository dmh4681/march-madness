'use client';

import { useEffect, useState, useCallback } from 'react';
import type { PredictionMarket, ArbitrageOpportunity } from '@/lib/types';

interface PredictionMarketData {
  markets: PredictionMarket[];
  arbitrage: ArbitrageOpportunity[];
  game_id: string;
}

interface PredictionMarketModalProps {
  gameId: string;
  homeTeam: string;
  awayTeam: string;
  onClose: () => void;
}

export function PredictionMarketModal({ gameId, homeTeam, awayTeam, onClose }: PredictionMarketModalProps) {
  const [data, setData] = useState<PredictionMarketData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_PYTHON_BACKEND_URL || 'http://localhost:8000';
      const res = await fetch(`${apiUrl}/games/${gameId}/prediction-data`);
      if (!res.ok) throw new Error(`Failed to fetch: ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load prediction market data');
    } finally {
      setLoading(false);
    }
  }, [gameId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Close on escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-gray-900 border border-gray-700 rounded-xl max-w-lg w-full max-h-[80vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-gray-900 border-b border-gray-800 p-4 flex items-center justify-between rounded-t-xl">
          <div>
            <h2 className="text-lg font-semibold text-white">Prediction Markets</h2>
            <p className="text-sm text-gray-400">{awayTeam} @ {homeTeam}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors p-1"
            aria-label="Close modal"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          {loading && (
            <div className="text-center py-8">
              <div className="w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
              <p className="text-sm text-gray-400">Loading market data...</p>
            </div>
          )}

          {error && (
            <div className="text-center py-8">
              <p className="text-red-400 text-sm mb-2">{error}</p>
              <button onClick={fetchData} className="text-sm text-gray-400 hover:text-white">
                Retry
              </button>
            </div>
          )}

          {data && !loading && (
            <>
              {/* Arbitrage Opportunities */}
              {data.arbitrage.length > 0 && (
                <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-yellow-400 mb-3">Arbitrage Signals</h3>
                  <div className="space-y-3">
                    {data.arbitrage.map((arb) => (
                      <div key={arb.id} className="flex items-center justify-between">
                        <div>
                          <p className="text-sm text-white">{arb.bet_type}</p>
                          <p className="text-xs text-gray-400">
                            {arb.edge_direction === 'prediction_higher' ? 'PM higher' : 'Sportsbook higher'}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-bold text-yellow-400">
                            {Math.abs(arb.delta * 100).toFixed(1)}% edge
                          </p>
                          <div className="flex gap-2 text-xs text-gray-400">
                            <span>SB: {(arb.sportsbook_implied_prob * 100).toFixed(0)}%</span>
                            <span>PM: {(arb.prediction_market_prob * 100).toFixed(0)}%</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Markets */}
              {data.markets.length > 0 ? (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-gray-300">Market Prices</h3>
                  {data.markets.map((market) => (
                    <div key={market.id} className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-3">
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-sm text-white font-medium truncate pr-2">{market.title}</p>
                        <span className={`text-xs px-1.5 py-0.5 rounded shrink-0 ${
                          market.source === 'polymarket'
                            ? 'bg-purple-500/20 text-purple-400'
                            : 'bg-blue-500/20 text-blue-400'
                        }`}>
                          {market.source === 'polymarket' ? 'Poly' : 'Kalshi'}
                        </span>
                      </div>
                      {market.outcomes.length > 0 && (
                        <div className="space-y-1">
                          {market.outcomes.map((outcome, idx) => (
                            <div key={idx} className="flex items-center justify-between text-sm">
                              <span className="text-gray-300">{outcome.name}</span>
                              <div className="flex items-center gap-2">
                                <div className="w-20 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                                  <div
                                    className="h-full bg-purple-500 rounded-full"
                                    style={{ width: `${outcome.price * 100}%` }}
                                  />
                                </div>
                                <span className="text-gray-400 text-xs w-10 text-right">
                                  {(outcome.price * 100).toFixed(0)}%
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                      {market.volume !== undefined && market.volume > 0 && (
                        <p className="text-xs text-gray-500 mt-2">
                          Vol: ${market.volume >= 1000 ? `${(market.volume / 1000).toFixed(0)}k` : market.volume}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : data.arbitrage.length === 0 && (
                <div className="text-center py-6 text-gray-400 text-sm">
                  No prediction market data available for this game
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
