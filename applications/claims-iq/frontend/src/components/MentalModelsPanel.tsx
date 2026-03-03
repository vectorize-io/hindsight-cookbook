import { useState, useRef, useEffect } from 'react';
import type { MentalModel } from '../types.ts';

interface MentalModelsPanelProps {
  models: MentalModel[];
  isRefreshing: boolean;
}

export function MentalModelsPanel({ models, isRefreshing }: MentalModelsPanelProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const prevCountsRef = useRef<Record<string, number>>({});
  const [updatedIds, setUpdatedIds] = useState<Set<string>>(new Set());

  // Track observation count changes and flash "Updated" badge
  useEffect(() => {
    const prev = prevCountsRef.current;
    const newUpdated = new Set<string>();

    for (const model of models) {
      const currentCount = model.observations?.length ?? 0;
      const prevCount = prev[model.id] ?? 0;
      if (prevCount > 0 && currentCount > prevCount) {
        newUpdated.add(model.id);
      }
    }

    // Save current counts
    const nextCounts: Record<string, number> = {};
    for (const model of models) {
      nextCounts[model.id] = model.observations?.length ?? 0;
    }
    prevCountsRef.current = nextCounts;

    if (newUpdated.size > 0) {
      setUpdatedIds(newUpdated);
      const timer = setTimeout(() => setUpdatedIds(new Set()), 5000);
      return () => clearTimeout(timer);
    }
  }, [models]);

  return (
    <div className="bg-slate-800/60 rounded-lg border border-slate-700/50 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-300">Mental Models</h2>
        {isRefreshing && (
          <span className="text-xs text-purple-400 animate-pulse">Refreshing...</span>
        )}
      </div>

      {models.length === 0 ? (
        <p className="text-xs text-slate-500">No mental models loaded. Use a memory mode to build them.</p>
      ) : (
        <div className="space-y-2">
          {models.map((model) => {
            const expanded = expandedId === model.id;
            const hasContent = model.observations && model.observations.length > 0;
            const fillPct = hasContent ? Math.min(100, (model.observations?.length ?? 0) * 15) : 0;

            return (
              <div
                key={model.id}
                className="rounded border border-slate-700/40 bg-slate-900/30 cursor-pointer"
                onClick={() => setExpandedId(expanded ? null : model.id)}
              >
                <div className="flex items-center gap-2 p-2">
                  {/* Fill indicator */}
                  <div className="w-4 h-4 rounded-full border border-slate-600 relative overflow-hidden">
                    <div
                      className="absolute bottom-0 left-0 right-0 bg-purple-500 transition-all duration-500"
                      style={{ height: `${fillPct}%` }}
                    />
                  </div>
                  <span className="text-xs font-medium text-slate-200 flex-1">{model.name}</span>
                  {updatedIds.has(model.id) && (
                    <span className="text-xs font-semibold text-green-400 bg-green-500/15 px-1.5 py-0.5 rounded animate-pulse">
                      Updated
                    </span>
                  )}
                  <span className="text-xs text-slate-500">{expanded ? '\u25B2' : '\u25BC'}</span>
                </div>

                {expanded && (
                  <div className="px-2 pb-2 border-t border-slate-700/30">
                    <p className="text-xs text-slate-400 mt-1 italic">{model.source_query}</p>
                    {model.content ? (
                      <p className="text-xs text-slate-300 mt-2 whitespace-pre-wrap max-h-48 overflow-y-auto">
                        {model.content}
                      </p>
                    ) : hasContent ? (
                      <div className="text-xs text-slate-400 mt-2">
                        {(model.observations as Array<Record<string, string>>).map((obs, i) => (
                          <p key={i} className="mb-1">{typeof obs === 'string' ? obs : JSON.stringify(obs)}</p>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-slate-500 mt-2">No content yet. Process some claims first.</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
