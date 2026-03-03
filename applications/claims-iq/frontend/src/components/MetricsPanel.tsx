import { useState } from 'react';
import type { ClaimResult } from '../types.ts';

interface MetricsPanelProps {
  claimsProcessed: number;
  correctDecisions: number;
  totalSteps: number;
  totalRework: number;
  history: ClaimResult[];
}

function ProgressBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="w-full bg-slate-700/50 rounded-full h-2">
      <div className={`h-2 rounded-full transition-all duration-500 ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function Trend({ current, previous }: { current: number; previous: number }) {
  if (previous === 0) return null;
  const diff = current - previous;
  if (Math.abs(diff) < 0.01) return null;
  return (
    <span className={`text-xs ${diff > 0 ? 'text-green-400' : 'text-red-400'}`}>
      {diff > 0 ? '\u2191' : '\u2193'}
    </span>
  );
}

function getDotColor(result: ClaimResult): { bg: string; ring: string; label: string } {
  if (!result.correct) return { bg: 'bg-red-500', ring: 'ring-red-500/30', label: 'Incorrect' };
  if (result.reworkCount > 0) return { bg: 'bg-amber-500', ring: 'ring-amber-500/30', label: 'Correct (rework)' };
  return { bg: 'bg-green-500', ring: 'ring-green-500/30', label: 'Correct' };
}

function LearningTimeline({ history }: { history: ClaimResult[] }) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  if (history.length === 0) return null;

  return (
    <div>
      <p className="text-xs text-slate-400 mb-2">Learning Timeline</p>
      <div className="flex flex-wrap gap-1.5 relative">
        {history.map((result, i) => {
          const dot = getDotColor(result);
          return (
            <div
              key={i}
              className="relative"
              onMouseEnter={() => setHoveredIdx(i)}
              onMouseLeave={() => setHoveredIdx(null)}
            >
              <div
                className={`w-3.5 h-3.5 rounded-full ${dot.bg} ring-2 ${dot.ring} cursor-pointer transition-transform hover:scale-125`}
              />
              {hoveredIdx === i && (
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 z-10 pointer-events-none">
                  <div className="bg-slate-900 border border-slate-600 rounded px-2 py-1 text-xs text-slate-200 whitespace-nowrap shadow-lg">
                    <p className="font-medium">Claim #{result.claimId}</p>
                    <p className={`${!result.correct ? 'text-red-400' : result.reworkCount > 0 ? 'text-amber-400' : 'text-green-400'}`}>
                      {dot.label} &middot; {result.steps} steps
                      {result.mistakes && result.mistakes.length > 0 && (
                        <span className="text-red-400"> &middot; {result.mistakes.length} mistake{result.mistakes.length > 1 ? 's' : ''}</span>
                      )}
                    </p>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function MetricsPanel({ claimsProcessed, correctDecisions, totalSteps, totalRework, history }: MetricsPanelProps) {
  const accuracy = claimsProcessed > 0 ? (correctDecisions / claimsProcessed) * 100 : 0;
  const avgSteps = claimsProcessed > 0 ? totalSteps / claimsProcessed : 0;
  const reworkRate = claimsProcessed > 0 ? (totalRework / claimsProcessed) * 100 : 0;

  // Compute routing accuracy (claims where no rework was needed)
  const perfectRouting = history.filter(h => h.reworkCount === 0 && h.correct).length;
  const routingAccuracy = claimsProcessed > 0 ? (perfectRouting / claimsProcessed) * 100 : 0;

  // Previous values for trend (last 3 vs everything)
  const recentWindow = 3;
  const recent = history.slice(-recentWindow);
  const earlier = history.slice(0, -recentWindow);
  const recentAcc = recent.length > 0 ? (recent.filter(h => h.correct).length / recent.length) * 100 : 0;
  const earlierAcc = earlier.length > 0 ? (earlier.filter(h => h.correct).length / earlier.length) * 100 : 0;

  return (
    <div className="bg-slate-800/60 rounded-lg border border-slate-700/50 p-4 space-y-4">
      <h2 className="text-sm font-semibold text-slate-300">Performance</h2>

      {/* Accuracy */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-slate-400">Accuracy</span>
          <div className="flex items-center gap-1">
            <span className="text-sm font-bold text-white">{accuracy.toFixed(0)}%</span>
            {history.length > recentWindow && <Trend current={recentAcc} previous={earlierAcc} />}
          </div>
        </div>
        <ProgressBar value={accuracy} max={100} color="bg-green-500" />
      </div>

      {/* Avg Steps */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-slate-400">Avg Steps</span>
          <span className="text-sm font-bold text-white">{avgSteps.toFixed(1)}</span>
        </div>
        <ProgressBar value={7} max={Math.max(avgSteps, 7)} color="bg-blue-500" />
        <p className="text-xs text-slate-500 mt-0.5">Optimal: 7</p>
      </div>

      {/* Rework Rate */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-slate-400">Rework Rate</span>
          <span className="text-sm font-bold text-white">{reworkRate.toFixed(0)}%</span>
        </div>
        <ProgressBar value={100 - reworkRate} max={100} color="bg-amber-500" />
      </div>

      {/* Routing */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-slate-400">Perfect Routing</span>
          <span className="text-sm font-bold text-white">{routingAccuracy.toFixed(0)}%</span>
        </div>
        <ProgressBar value={routingAccuracy} max={100} color="bg-purple-500" />
      </div>

      {/* Learning Timeline */}
      <LearningTimeline history={history} />

      {/* Summary */}
      <div className="pt-2 border-t border-slate-700/30 text-xs text-slate-500">
        {claimsProcessed} claims processed &middot; {correctDecisions} correct
      </div>
    </div>
  );
}
