import { useEffect, useState } from 'react';
import type { KnowledgeRule } from '../types.ts';

interface KnowledgePanelProps {
  rules: KnowledgeRule[];
  mode: string;
}

function summarizeRule(feedback: string): string {
  const f = feedback.toLowerCase();
  if (f.includes('$25') && f.includes('limit')) return 'Credit limit is $25 per adjustment';
  if (f.includes('remote diagnostics') || f.includes('diagnostics first')) return 'Must run remote diagnostics before scheduling a technician dispatch';
  if (f.includes('automatic credits') && f.includes('outage')) return 'No manual outage credits during active outages \u2014 auto-credits apply';
  if (f.includes('one per 90 days') || f.includes('90 days')) return 'Only one billing adjustment per 90 days';
  if (f.includes('24') && f.includes('tenure') && f.includes('retention')) return 'Retention offers require 24+ months tenure';
  if (f.includes('contract') && (f.includes('etf') || f.includes('early termination'))) return 'Must disclose ETF before downgrading during contract';
  if (f.includes('trouble ticket') && f.includes('outage')) return "Don't create trouble tickets during area-wide outages";
  if (f.includes('dispatch') && f.includes('suspended') && f.includes('outage')) return 'Dispatch suspended during active outages';
  if (f.includes('rate code') || f.includes('rate_code')) return 'Must include rate code for plan changes';
  if (f.includes('disconnect reason') || f.includes('reason_code')) return 'Must include reason code for disconnects';
  if (f.includes('retention') && f.includes('eligibility check')) return 'Must check retention eligibility before pulling offers';
  if (f.includes('7') && f.includes('days') && f.includes('transfer')) return 'Transfers need 7+ business days lead time';
  return feedback.length > 80 ? feedback.slice(0, 77) + '...' : feedback;
}

export function KnowledgePanel({ rules, mode }: KnowledgePanelProps) {
  const [flashIndex, setFlashIndex] = useState<number | null>(null);

  useEffect(() => {
    if (rules.length > 0) {
      setFlashIndex(rules.length - 1);
      const timer = setTimeout(() => setFlashIndex(null), 2000);
      return () => clearTimeout(timer);
    }
  }, [rules.length]);

  const isNoMemory = mode === 'memory_off';

  return (
    <div className="px-4 py-3">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Agent Knowledge</h3>
        {isNoMemory && (
          <span className="text-[10px] text-amber-500/60">resets each customer</span>
        )}
      </div>

      {rules.length === 0 ? (
        <p className="text-xs text-gray-600 italic">(No learned policies yet)</p>
      ) : (
        <div className="space-y-1.5">
          {rules.map((rule, i) => (
            <div
              key={i}
              className={`flex items-start gap-1.5 text-xs transition-all duration-500 ${
                flashIndex === i ? 'bg-emerald-500/10 rounded px-1.5 py-1 -mx-1.5' : ''
              }`}
            >
              <span className="text-emerald-400 font-bold mt-0.5 flex-shrink-0">{'\u2713'}</span>
              <span className="text-gray-300">{summarizeRule(rule.feedback)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
