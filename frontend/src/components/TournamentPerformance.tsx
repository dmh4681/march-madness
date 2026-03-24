'use client';

const ROUND_LABELS: Record<string, string> = {
  first_four: 'First Four',
  round_64: 'Round of 64',
  round_32: 'Round of 32',
  sweet_16: 'Sweet 16',
  elite_8: 'Elite Eight',
  final_4: 'Final Four',
  championship: 'Championship',
};

interface RoundStat {
  round: string;
  correct: number;
  incorrect: number;
  total: number;
  accuracy: number | null;
}

interface TournamentPerformanceProps {
  data: {
    season: number;
    overall: { total_picks: number; correct: number; incorrect: number; accuracy: number | null };
    by_round: RoundStat[];
  };
}

function AccuracyBar({ accuracy }: { accuracy: number | null }) {
  if (accuracy === null) return <span className="text-gray-500">--</span>;
  const color = accuracy >= 70 ? 'text-green-400' : accuracy >= 50 ? 'text-yellow-400' : 'text-red-400';
  return <span className={`font-medium ${color}`}>{accuracy.toFixed(1)}%</span>;
}

export function TournamentPerformance({ data }: TournamentPerformanceProps) {
  const { season, overall, by_round } = data;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">
          {season} Tournament Bracket Performance
        </h2>
        {overall.total_picks > 0 && (
          <span className="text-sm text-gray-400">
            {overall.correct}/{overall.total_picks} correct
          </span>
        )}
      </div>

      {overall.total_picks === 0 ? (
        <p className="text-sm text-gray-500">No graded bracket picks yet for {season}.</p>
      ) : (
        <>
          {/* Overall summary */}
          <div className="grid grid-cols-3 gap-3 mb-6">
            <div className="bg-gray-800/60 rounded-lg p-3 text-center">
              <p className="text-xs text-gray-400 mb-1">Accuracy</p>
              <p className="text-2xl font-bold">
                <AccuracyBar accuracy={overall.accuracy} />
              </p>
            </div>
            <div className="bg-gray-800/60 rounded-lg p-3 text-center">
              <p className="text-xs text-gray-400 mb-1">Correct</p>
              <p className="text-2xl font-bold text-green-400">{overall.correct}</p>
            </div>
            <div className="bg-gray-800/60 rounded-lg p-3 text-center">
              <p className="text-xs text-gray-400 mb-1">Incorrect</p>
              <p className="text-2xl font-bold text-red-400">{overall.incorrect}</p>
            </div>
          </div>

          {/* Round-by-round breakdown */}
          {by_round.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-400 border-b border-gray-800">
                    <th className="text-left py-2 pr-4">Round</th>
                    <th className="text-right py-2 px-2">Picks</th>
                    <th className="text-right py-2 px-2">Correct</th>
                    <th className="text-right py-2 px-2">Wrong</th>
                    <th className="text-right py-2 pl-2">Accuracy</th>
                  </tr>
                </thead>
                <tbody>
                  {by_round.map(r => (
                    <tr key={r.round} className="border-b border-gray-800/50 last:border-0">
                      <td className="py-2.5 pr-4 text-gray-200 font-medium">
                        {ROUND_LABELS[r.round] ?? r.round}
                      </td>
                      <td className="text-right py-2.5 px-2 text-gray-400">{r.total}</td>
                      <td className="text-right py-2.5 px-2 text-green-400">{r.correct}</td>
                      <td className="text-right py-2.5 px-2 text-red-400">{r.incorrect}</td>
                      <td className="text-right py-2.5 pl-2">
                        <AccuracyBar accuracy={r.accuracy} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
