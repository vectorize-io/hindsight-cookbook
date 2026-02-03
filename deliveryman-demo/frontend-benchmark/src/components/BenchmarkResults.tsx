import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, BarChart, Bar } from 'recharts';
import type { BenchmarkResults as BenchmarkResultsType } from '../types';

interface BenchmarkResultsProps {
  results: BenchmarkResultsType;
  onExport?: () => void;
}

export function BenchmarkResultsDisplay({ results, onExport }: BenchmarkResultsProps) {
  const { config, summary, learning, timeSeries, deliveries } = results;

  // Prepare chart data
  const efficiencyData = timeSeries.efficiencyByEpisode.map((eff, i) => ({
    episode: i + 1,
    efficiency: Math.round(eff * 100),
    isRepeat: deliveries[i]?.isRepeat ?? false,
  }));

  const tokenData = timeSeries.tokensByEpisode.map((tokens, i) => ({
    episode: i + 1,
    tokens,
  }));

  // Get mode color
  const getModeColor = (mode: string) => {
    switch (mode) {
      case 'no_memory': return '#64748b';
      case 'filesystem': return '#f59e0b';
      case 'recall': return '#a855f7';
      case 'reflect': return '#06b6d4';
      case 'hindsight_mm':
      case 'hindsight_mm_nowait': return '#10b981';
      default: return '#3b82f6';
    }
  };

  const modeColor = getModeColor(config.mode);

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
          <div className="text-2xl font-bold text-white">
            {Math.round(summary.avgPathEfficiency * 100)}%
          </div>
          <div className="text-xs text-slate-400">Avg Path Efficiency</div>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
          <div className="text-2xl font-bold text-white">
            {Math.round(summary.successRate * 100)}%
          </div>
          <div className="text-xs text-slate-400">Success Rate</div>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
          <div className="text-2xl font-bold text-white">
            {learning.convergenceEpisode || 'N/A'}
          </div>
          <div className="text-xs text-slate-400">Convergence Episode</div>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
          <div className={`text-2xl font-bold ${learning.improvement >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {learning.improvement >= 0 ? '+' : ''}{Math.round(learning.improvement * 100)}%
          </div>
          <div className="text-xs text-slate-400">Learning Improvement</div>
        </div>
      </div>

      {/* Learning Metrics */}
      <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
        <h3 className="text-sm font-medium text-slate-300 mb-3">Learning Analysis</h3>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <span className="text-slate-500">First Half Efficiency:</span>
            <span className="ml-2 text-slate-300">{Math.round(learning.firstHalfEfficiency * 100)}%</span>
          </div>
          <div>
            <span className="text-slate-500">Second Half Efficiency:</span>
            <span className="ml-2 text-slate-300">{Math.round(learning.secondHalfEfficiency * 100)}%</span>
          </div>
          <div>
            <span className="text-slate-500">Total Steps:</span>
            <span className="ml-2 text-slate-300">{summary.totalSteps} / {summary.totalOptimalSteps} optimal</span>
          </div>
        </div>
      </div>

      {/* Efficiency Chart */}
      <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
        <h3 className="text-sm font-medium text-slate-300 mb-3">Path Efficiency Over Time</h3>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={efficiencyData}>
              <XAxis
                dataKey="episode"
                stroke="#64748b"
                tick={{ fill: '#64748b', fontSize: 10 }}
              />
              <YAxis
                domain={[0, 100]}
                stroke="#64748b"
                tick={{ fill: '#64748b', fontSize: 10 }}
                tickFormatter={(v) => `${v}%`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1e293b',
                  border: '1px solid #334155',
                  borderRadius: '8px',
                }}
                formatter={(value) => [
                  `${value ?? 0}%`,
                  'Efficiency'
                ]}
              />
              <ReferenceLine y={90} stroke="#10b981" strokeDasharray="3 3" />
              <Line
                type="monotone"
                dataKey="efficiency"
                stroke={modeColor}
                strokeWidth={2}
                dot={({ cx, cy, payload }: { cx?: number; cy?: number; payload?: { isRepeat?: boolean } }) => {
                  if (cx === undefined || cy === undefined) return null;
                  const isRepeat = payload?.isRepeat ?? false;
                  return (
                    <circle
                      key={`dot-${cx}-${cy}`}
                      cx={cx}
                      cy={cy}
                      r={isRepeat ? 5 : 3}
                      fill={isRepeat ? '#f59e0b' : modeColor}
                      stroke="none"
                    />
                  );
                }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="flex gap-4 mt-2 text-[10px] text-slate-500">
          <span>
            <span className="inline-block w-2 h-2 rounded-full mr-1" style={{ backgroundColor: modeColor }} />
            New Visit
          </span>
          <span>
            <span className="inline-block w-2 h-2 rounded-full bg-amber-500 mr-1" />
            Repeat Visit
          </span>
          <span>
            <span className="inline-block w-4 border-t border-dashed border-emerald-500 mr-1" />
            90% Target
          </span>
        </div>
      </div>

      {/* Token Usage Chart */}
      <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
        <h3 className="text-sm font-medium text-slate-300 mb-3">Token Usage Per Delivery</h3>
        <div className="h-32">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={tokenData}>
              <XAxis
                dataKey="episode"
                stroke="#64748b"
                tick={{ fill: '#64748b', fontSize: 10 }}
              />
              <YAxis
                stroke="#64748b"
                tick={{ fill: '#64748b', fontSize: 10 }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1e293b',
                  border: '1px solid #334155',
                  borderRadius: '8px',
                }}
              />
              <Bar dataKey="tokens" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="text-xs text-slate-500 mt-2">
          Total: {summary.totalTokens.total.toLocaleString()} tokens
          ({summary.totalTokens.prompt.toLocaleString()} prompt, {summary.totalTokens.completion.toLocaleString()} completion)
        </div>
      </div>

      {/* Config & Export */}
      <div className="flex justify-between items-center">
        <div className="text-xs text-slate-500">
          Mode: <span className="text-slate-300">{config.mode}</span> |
          Deliveries: <span className="text-slate-300">{config.numDeliveries}</span> |
          Repeat Ratio: <span className="text-slate-300">{Math.round(config.repeatRatio * 100)}%</span> |
          Difficulty: <span className="text-slate-300">{config.difficulty}</span>
        </div>
        {onExport && (
          <button
            onClick={onExport}
            className="px-3 py-1.5 text-xs bg-blue-600/50 hover:bg-blue-600 border border-blue-500/50 text-blue-300 hover:text-white rounded transition-colors"
          >
            Export Results
          </button>
        )}
      </div>
    </div>
  );
}
