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
    <div className="px-4 py-3 border-t border-gray-800">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Mental Models</h3>
        {isRefreshing && (
          <span className="text-xs text-purple-400 animate-pulse">Refreshing...</span>
        )}
      </div>

      {models.length === 0 ? (
        <p className="text-xs text-gray-600">No mental models loaded. Use a memory mode to build them.</p>
      ) : (
        <div className="space-y-1.5">
          {models.map((model) => {
            const expanded = expandedId === model.id;
            const hasContent = model.observations && model.observations.length > 0;
            const fillPct = hasContent ? Math.min(100, (model.observations?.length ?? 0) * 15) : 0;

            return (
              <div
                key={model.id}
                className="rounded-lg border border-gray-800 bg-gray-900/50 cursor-pointer"
                onClick={() => setExpandedId(expanded ? null : model.id)}
              >
                <div className="flex items-center gap-2 px-3 py-2">
                  <div className="w-3.5 h-3.5 rounded-full border border-gray-600 relative overflow-hidden">
                    <div
                      className="absolute bottom-0 left-0 right-0 bg-purple-500 transition-all duration-500"
                      style={{ height: `${fillPct}%` }}
                    />
                  </div>
                  <span className="text-xs font-medium text-gray-300 flex-1">{model.name}</span>
                  {updatedIds.has(model.id) && (
                    <span className="text-[10px] font-semibold text-emerald-400 bg-emerald-500/15 px-1.5 py-0.5 rounded animate-pulse">
                      Updated
                    </span>
                  )}
                  <span className="text-xs text-gray-600">{expanded ? '\u25B2' : '\u25BC'}</span>
                </div>

                {expanded && (
                  <div className="px-3 pb-2 border-t border-gray-800">
                    <p className="text-xs text-gray-500 mt-1 italic">{model.source_query}</p>
                    {model.content ? (
                      <p className="text-xs text-gray-300 mt-2 whitespace-pre-wrap max-h-48 overflow-y-auto">
                        {model.content}
                      </p>
                    ) : hasContent ? (
                      <div className="text-xs text-gray-400 mt-2">
                        {(model.observations as Array<Record<string, string>>).map((obs, i) => (
                          <p key={i} className="mb-1">{typeof obs === 'string' ? obs : JSON.stringify(obs)}</p>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-gray-600 mt-2">No content yet. Process some customers first.</p>
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
