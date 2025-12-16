'use client';

import { useState, useEffect } from 'react';
import { StancePoint, TimelineData } from '@/types';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceDot,
} from 'recharts';
import { ExternalLink, Info } from 'lucide-react';

interface StanceTimelineProps {
  data: TimelineData[];
  onPointClick?: (point: StancePoint) => void;
}

const CANDIDATE_COLORS = [
  '#2563eb', // blue
  '#dc2626', // red
  '#16a34a', // green
  '#ea580c', // orange
  '#9333ea', // purple
  '#0891b2', // cyan
];

// Stance position colors
const STANCE_COLORS = {
  support: '#16a34a', // green
  oppose: '#dc2626', // red
  neutral: '#6b7280', // gray
};

// Analyze stance text to determine position
function determineStancePosition(stance: string, summary: string): 'support' | 'oppose' | 'neutral' {
  const text = `${stance} ${summary}`.toLowerCase();

  const supportKeywords = ['support', 'favor', 'advocate', 'endorse', 'promote', 'champion', 'back', 'approve', 'agree', 'in favor'];
  const opposeKeywords = ['oppose', 'opposed', 'against', 'reject', 'resist', 'condemn', 'criticize', 'denounce', 'disapprove', 'vote against', 'voted against'];

  const supportScore = supportKeywords.filter(keyword => text.includes(keyword)).length;
  const opposeScore = opposeKeywords.filter(keyword => text.includes(keyword)).length;

  // When scores are tied but oppose keywords exist, favor oppose classification
  if (supportScore > opposeScore && supportScore > 0) return 'support';
  if (opposeScore > supportScore && opposeScore > 0) return 'oppose';
  if (opposeScore > 0) return 'oppose'; // Tie-breaker: if any oppose keywords, classify as oppose
  return 'neutral';
}

export default function StanceTimeline({ data, onPointClick }: StanceTimelineProps) {
  const [selectedPoint, setSelectedPoint] = useState<StancePoint | null>(null);
  const [hoveredPoint, setHoveredPoint] = useState<StancePoint | null>(null);

  // Clear selected point when data changes (e.g., switching sessions)
  useEffect(() => {
    setSelectedPoint(null);
    setHoveredPoint(null);
  }, [data]);

  if (!data || data.length === 0) {
    return (
      <div className="p-8 text-center text-gray-900">
        No stance data available yet. Start tracking to see results.
      </div>
    );
  }

  // Transform data for Recharts
  const allPoints = data.flatMap((candidateData) =>
    candidateData.points.map((point) => ({
      ...point,
      candidate: candidateData.candidate,
      timestamp: new Date(point.timestamp).getTime(),
      dateLabel: new Date(point.timestamp).toLocaleDateString(),
      position: determineStancePosition(point.stance, point.stance_summary || ''),
    }))
  );

  // Sort by timestamp
  allPoints.sort((a, b) => a.timestamp - b.timestamp);

  // Get all unique timestamps and candidates
  const uniqueTimestamps = Array.from(new Set(allPoints.map(p => p.timestamp))).sort((a, b) => a - b);
  const uniqueCandidates = Array.from(new Set(allPoints.map(p => p.candidate)));

  // Create complete time-series data structure with null values for missing data
  const timeSeriesData = uniqueTimestamps.map(timestamp => {
    const dateLabel = new Date(timestamp).toLocaleDateString();
    const entry: any = { timestamp, dateLabel };

    // Add data for each candidate (null if no data at this timestamp)
    uniqueCandidates.forEach(candidate => {
      const point = allPoints.find(p => p.timestamp === timestamp && p.candidate === candidate);
      entry[`${candidate}_confidence`] = point ? point.confidence : null;
      entry[`${candidate}_data`] = point || null;
    });

    return entry;
  });

  const handlePointClick = (candidateKey: string, dataPoint: any) => {
    const point = dataPoint[`${candidateKey}_data`];

    if (point) {
      setSelectedPoint(point);
      setHoveredPoint(null);
      if (onPointClick) {
        onPointClick(point);
      }
    }
  };

  const displayPoint = selectedPoint;

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-2xl font-bold mb-4 text-gray-900">Stance Timeline</h2>

        <ResponsiveContainer width="100%" height={400}>
          <LineChart
            data={timeSeriesData}
            onMouseLeave={() => setHoveredPoint(null)}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="dateLabel"
              label={{ value: 'Date', position: 'insideBottom', offset: -5 }}
            />
            <YAxis
              label={{ value: 'Confidence', angle: -90, position: 'insideLeft' }}
              domain={[0, 1]}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend />

            {data.map((candidateData, index) => {
              const candidateKey = candidateData.candidate;
              return (
                <Line
                  key={candidateKey}
                  type="monotone"
                  dataKey={`${candidateKey}_confidence`}
                  name={candidateKey}
                  stroke={CANDIDATE_COLORS[index % CANDIDATE_COLORS.length]}
                  strokeWidth={2}
                  connectNulls={true}
                  dot={(props: any) => {
                    const { cx, cy, payload, index: dotIndex } = props;
                    const point = payload[`${candidateKey}_data`];

                    // Only render dot if this candidate has data at this timestamp
                    if (!point) return null;

                    const position = determineStancePosition(point.stance, point.stance_summary || '');
                    const positionColor = STANCE_COLORS[position];
                    const candidateColor = CANDIDATE_COLORS[index % CANDIDATE_COLORS.length];

                    return (
                      <g key={`dot-group-${candidateKey}-${point.id || dotIndex}`}>
                        {/* Outer ring - candidate color */}
                        <circle
                          cx={cx}
                          cy={cy}
                          r={10}
                          fill={candidateColor}
                          stroke="white"
                          strokeWidth={2}
                          style={{ cursor: 'pointer' }}
                        />
                        {/* Inner dot - position color */}
                        <circle
                          cx={cx}
                          cy={cy}
                          r={6}
                          fill={positionColor}
                          style={{ cursor: 'pointer' }}
                        />
                      </g>
                    );
                  }}
                  activeDot={{
                    r: 8,
                    onClick: (e: any, payload: any) => {
                      handlePointClick(candidateKey, payload.payload);
                    },
                  }}
                />
              );
            })}

            {/* Mark stance changes */}
            {allPoints
              .filter((point) => point.change_from_previous)
              .map((point, index) => (
                <ReferenceDot
                  key={`change-${index}`}
                  x={point.timestamp}
                  y={point.confidence}
                  r={10}
                  fill="red"
                  stroke="none"
                  opacity={0.3}
                />
              ))}
          </LineChart>
        </ResponsiveContainer>

        {/* Legend for dot colors */}
        <div className="mt-4 space-y-2">
          <div className="text-sm text-gray-900 bg-blue-50 border border-blue-200 rounded-lg p-3">
            <div className="font-semibold mb-2">Position Colors:</div>
            <div className="grid grid-cols-3 gap-4">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full" style={{ backgroundColor: STANCE_COLORS.support }}></div>
                <span>Supports</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full" style={{ backgroundColor: STANCE_COLORS.oppose }}></div>
                <span>Opposes</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full" style={{ backgroundColor: STANCE_COLORS.neutral }}></div>
                <span>Neutral/Unclear</span>
              </div>
            </div>
          </div>

          {allPoints.some(point => point.change_from_previous) && (
            <div className="text-sm text-gray-900 bg-yellow-50 border border-yellow-200 rounded-lg p-3">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-red-300 rounded-full opacity-30"></div>
                <span className="font-medium">Red circles highlight points where the candidate's stance has changed from their previous position</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Sources Panel - Always visible when hovering or selecting a point */}
      {displayPoint && (
        <div className="bg-white rounded-lg shadow-lg p-6 border-l-4 border-blue-500">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-gray-900">
              Source Data - {displayPoint.candidate}
            </h3>
            <span className="text-sm text-gray-600">
              {new Date(displayPoint.timestamp).toLocaleDateString()} •
              Confidence: {(displayPoint.confidence * 100).toFixed(0)}%
            </span>
          </div>

          {displayPoint.stance_summary && (
            <div className="mb-4 p-3 bg-blue-50 rounded-lg">
              <h4 className="font-semibold text-gray-900 mb-2">Stance Summary</h4>
              <p className="text-sm text-gray-700">{displayPoint.stance_summary}</p>
            </div>
          )}

          {displayPoint.sources && displayPoint.sources.length > 0 ? (
            <>
              <p className="text-sm text-gray-600 mb-4">
                The following sources were used to determine this stance point:
              </p>

              <div className="space-y-3">
                {displayPoint.sources.map((source, index) => (
                  <a
                    key={index}
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block p-4 border border-gray-200 rounded-lg hover:bg-blue-50 hover:border-blue-300 transition-all"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <p className="font-semibold text-blue-600 hover:text-blue-800">
                            {source.title}
                          </p>
                          <ExternalLink size={14} className="text-blue-400 flex-shrink-0" />
                        </div>
                        {source.excerpt && (
                          <p className="text-sm text-gray-700 mb-2 line-clamp-2">
                            {source.excerpt}
                          </p>
                        )}
                        <div className="flex gap-4 text-xs text-gray-600">
                          <span className="capitalize font-medium">{source.source_type}</span>
                          <span>•</span>
                          <span>{new Date(source.published_date).toLocaleDateString()}</span>
                        </div>
                      </div>
                    </div>
                  </a>
                ))}
              </div>
            </>
          ) : (
            <div className="p-4 bg-gray-50 rounded-lg border border-gray-200 text-center">
              <p className="text-gray-600 text-sm">
                No source data available for this stance point yet. Run the tracker to collect source data from Vectorize pipelines.
              </p>
            </div>
          )}

          {!hoveredPoint && selectedPoint && (
            <button
              onClick={() => setSelectedPoint(null)}
              className="mt-4 text-sm text-blue-600 hover:text-blue-800 font-medium"
            >
              ✕ Close
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload || payload.length === 0) return null;

  return (
    <div className="bg-white p-4 border border-gray-200 rounded-lg shadow-lg">
      <p className="font-semibold text-gray-900 mb-2">{payload[0].payload.dateLabel}</p>
      {payload.map((entry: any, index: number) => {
        const candidate = entry.name;
        const confidence = entry.value;
        const candidateKey = entry.dataKey.replace('_confidence', '');
        const point = payload[0].payload[`${candidateKey}_data`];

        if (!point) return null;

        const position = determineStancePosition(point.stance, point.stance_summary || '');
        const positionColor = STANCE_COLORS[position];
        const positionLabel = position === 'support' ? 'Supports' : position === 'oppose' ? 'Opposes' : 'Neutral/Unclear';

        return (
          <div key={index} className="mt-2 pb-2 border-b border-gray-100 last:border-0">
            <p style={{ color: entry.color }} className="font-medium">
              {candidate}
            </p>
            <div className="flex items-center gap-2 mt-1">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: positionColor }}></div>
              <p className="text-sm text-gray-700">{positionLabel}</p>
            </div>
            <p className="text-sm text-gray-900 font-semibold mt-1">Confidence: {(confidence * 100).toFixed(0)}%</p>
          </div>
        );
      })}
    </div>
  );
}

function StanceDetailCard({ point, onClose }: { point: StancePoint; onClose: () => void }) {
  return (
    <div className="bg-white rounded-lg shadow-lg p-6 border-l-4 border-blue-500">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-xl font-bold">{point.candidate}</h3>
          <p className="text-sm text-gray-900">
            {new Date(point.timestamp).toLocaleDateString()}
          </p>
        </div>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600"
        >
          ✕
        </button>
      </div>

      <div className="space-y-4">
        <div>
          <h4 className="font-semibold mb-2 text-gray-900">Summary</h4>
          <p className="text-gray-700">{point.stance_summary}</p>
        </div>

        <div>
          <h4 className="font-semibold mb-2 text-gray-900">Detailed Stance</h4>
          <p className="text-gray-700">{point.stance}</p>
        </div>

        <div>
          <p className="text-sm">
            <span className="font-semibold">Confidence:</span>{' '}
            {(point.confidence * 100).toFixed(0)}%
          </p>
        </div>

        {point.change_from_previous && (
          <div className="bg-yellow-50 border border-yellow-200 rounded p-3">
            <div className="flex items-start gap-2">
              <Info size={18} className="text-yellow-600 mt-0.5" />
              <div>
                <p className="font-semibold text-yellow-800">Stance Change Detected</p>
                <p className="text-sm text-yellow-700 mt-1">
                  {point.change_from_previous.change_description}
                </p>
                <p className="text-sm text-yellow-600 mt-1">
                  Magnitude: {(point.change_from_previous.change_magnitude * 100).toFixed(0)}%
                </p>
              </div>
            </div>
          </div>
        )}

        {point.sources && point.sources.length > 0 && (
          <div>
            <h4 className="font-semibold mb-2 text-gray-900">Sources ({point.sources.length})</h4>
            <div className="space-y-2">
              {point.sources.map((source, index) => (
                <a
                  key={index}
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block p-3 border border-gray-200 rounded hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1">
                      <p className="font-medium text-blue-600 hover:text-blue-800">
                        {source.title}
                      </p>
                      {source.excerpt && (
                        <p className="text-sm text-gray-800 mt-1 line-clamp-2">
                          {source.excerpt}
                        </p>
                      )}
                      <div className="flex gap-3 mt-2 text-xs text-gray-800">
                        <span className="capitalize">{source.source_type}</span>
                        <span>
                          {new Date(source.published_date).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                    <ExternalLink size={16} className="text-gray-400 flex-shrink-0" />
                  </div>
                </a>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
