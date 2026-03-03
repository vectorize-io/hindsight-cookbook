import { useState, useEffect, useRef } from 'react';
import type { AgentAction, MemoryInjection, ClaimResult } from '../types.ts';

const TOOL_ICONS: Record<string, string> = {
  classify_claim: '\u{1F50D}',    // magnifying glass
  lookup_policy: '\u{1F4CB}',     // clipboard
  check_coverage: '\u{1F6E1}',    // shield
  check_fraud_indicators: '\u{1F6A8}', // rotating light
  check_prior_claims: '\u{1F4C2}', // open folder
  get_adjuster: '\u{1F464}',      // bust
  submit_decision: '\u{2705}',    // check mark
  thinking: '\u{1F4AD}',          // thought bubble
};

function getResultStyle(result: string): string {
  if (result.startsWith('DECISION ACCEPTED') || result.startsWith('COVERED')) {
    return 'border-green-500/30 bg-green-900/10';
  }
  if (result.startsWith('DECISION REJECTED') || result.startsWith('NOT COVERED')) {
    return 'border-red-500/30 bg-red-900/10';
  }
  if (result.startsWith('FRAUD RISK: HIGH') || result.startsWith('FRAUD RISK: MEDIUM')) {
    return 'border-yellow-500/30 bg-yellow-900/10';
  }
  return 'border-slate-700/30 bg-slate-800/30';
}

function getResultTextColor(result: string): string {
  if (result.startsWith('DECISION ACCEPTED') || result.startsWith('COVERED')) return 'text-green-300';
  if (result.startsWith('DECISION REJECTED') || result.startsWith('NOT COVERED')) return 'text-red-300';
  if (result.startsWith('FRAUD RISK: HIGH') || result.startsWith('FRAUD RISK: MEDIUM')) return 'text-yellow-300';
  return 'text-slate-300';
}

/** Parse rejection text into error lines and learning signal lines. */
function parseRejection(text: string): { errors: string[]; hints: string[] } {
  const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
  const errors: string[] = [];
  const hints: string[] = [];
  let inHints = false;
  for (const line of lines) {
    if (line.startsWith('DECISION REJECTED')) continue; // skip header
    if (/hint|learn|suggest|next time|should|consider|try/i.test(line)) {
      inHints = true;
    }
    if (inHints) {
      hints.push(line);
    } else {
      errors.push(line);
    }
  }
  return { errors, hints };
}

/** Count how many DECISION REJECTED entries precede this action (to show attempt number). */
function countPriorRejections(actions: AgentAction[], currentIdx: number): number {
  let count = 0;
  for (let i = 0; i < currentIdx; i++) {
    if (actions[i].toolName === 'submit_decision' && actions[i].toolResult.startsWith('DECISION REJECTED')) {
      count++;
    }
  }
  return count;
}

interface RejectionCalloutProps {
  action: AgentAction;
  attemptNumber: number;
}

function RejectionCallout({ action, attemptNumber }: RejectionCalloutProps) {
  const { errors, hints } = parseRejection(action.toolResult);

  return (
    <div className="rounded-lg border-2 border-red-500/50 bg-red-950/20 p-3 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-base">{'\u274C'}</span>
        <span className="text-sm font-bold text-red-400">REJECTED</span>
        <span className="text-xs text-red-400/70 font-medium">Attempt #{attemptNumber}</span>
        <span className="text-xs text-slate-500 ml-auto">step {action.step} &middot; {action.timing.toFixed(1)}s</span>
      </div>

      {/* Error lines */}
      {errors.length > 0 && (
        <div className="space-y-1">
          {errors.map((err, i) => (
            <p key={i} className="text-xs text-red-300">{err}</p>
          ))}
        </div>
      )}

      {/* Learning signal / hints */}
      {hints.length > 0 && (
        <div className="border-t border-amber-500/30 pt-2 mt-1">
          <p className="text-xs font-semibold text-amber-400 mb-1">Learning Signal</p>
          {hints.map((hint, i) => (
            <p key={i} className="text-xs text-amber-300/80">{hint}</p>
          ))}
        </div>
      )}

      {/* Tool args */}
      {action.toolArgs && Object.keys(action.toolArgs).length > 0 && (
        <div className="text-xs text-slate-500 bg-slate-900/50 rounded p-2 font-mono">
          {Object.entries(action.toolArgs).map(([k, v]) => (
            <div key={k}>{k}: {JSON.stringify(v)}</div>
          ))}
        </div>
      )}
    </div>
  );
}

interface ActionEntryProps {
  action: AgentAction;
  expanded: boolean;
  onToggle: () => void;
}

function ActionEntry({ action, expanded, onToggle }: ActionEntryProps) {
  const icon = TOOL_ICONS[action.toolName] ?? '\u{1F527}';
  const style = getResultStyle(action.toolResult);
  const textColor = getResultTextColor(action.toolResult);

  // Truncated result for compact view
  const truncated = action.toolResult.length > 100
    ? action.toolResult.slice(0, 100) + '...'
    : action.toolResult;

  return (
    <div
      className={`rounded-lg border p-3 cursor-pointer transition-colors ${style}`}
      onClick={onToggle}
    >
      <div className="flex items-start gap-2">
        <span className="text-base">{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-white">{action.toolName}</span>
            <span className="text-xs text-slate-500">step {action.step}</span>
            <span className="text-xs text-slate-600">{action.timing.toFixed(1)}s</span>
          </div>
          <p className={`text-xs mt-1 ${textColor} ${expanded ? '' : 'line-clamp-2'}`}>
            {expanded ? action.toolResult : truncated}
          </p>
          {expanded && action.toolArgs && Object.keys(action.toolArgs).length > 0 && (
            <div className="mt-2 text-xs text-slate-500 bg-slate-900/50 rounded p-2 font-mono">
              {Object.entries(action.toolArgs).map(([k, v]) => (
                <div key={k}>{k}: {JSON.stringify(v)}</div>
              ))}
            </div>
          )}
          {expanded && action.thinking && (
            <div className="mt-2 text-xs text-slate-400 italic bg-slate-900/30 rounded p-2">
              {action.thinking}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface MemoryCardProps {
  memoryInjection: MemoryInjection;
}

function MemoryCard({ memoryInjection }: MemoryCardProps) {
  const [expanded, setExpanded] = useState(false);
  const hasText = memoryInjection.text != null && memoryInjection.text.length > 0;
  const preview = hasText ? memoryInjection.text!.slice(0, 150) : '';
  const needsToggle = hasText && memoryInjection.text!.length > 150;

  const methodLabel = memoryInjection.method === 'recall' ? 'Memory Recalled' : 'Memory Reflected';

  return (
    <div className="rounded-lg border border-purple-500/40 bg-purple-950/20 p-3">
      <div className="flex items-center gap-2">
        <span className="text-base">{'\u{1F9E0}'}</span>
        <span className="text-sm font-semibold text-purple-300">{methodLabel}</span>
        <span className="text-xs text-slate-500 ml-auto">{memoryInjection.timing.toFixed(1)}s</span>
      </div>

      {hasText ? (
        <div className="mt-2">
          <p className={`text-xs text-purple-200/80 ${expanded ? 'whitespace-pre-wrap max-h-64 overflow-y-auto' : ''}`}>
            {expanded ? memoryInjection.text : preview + (needsToggle ? '...' : '')}
          </p>
          {needsToggle && (
            <button
              className="text-xs text-purple-400 hover:text-purple-300 mt-1 underline underline-offset-2"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? 'Show less' : 'Show full memory'}
            </button>
          )}
        </div>
      ) : (
        <p className="text-xs text-slate-500 mt-1">No relevant memories found</p>
      )}
    </div>
  );
}

const TOOL_LABELS: Record<string, string> = {
  classify_claim: 'Classify',
  lookup_policy: 'Policy',
  check_coverage: 'Coverage',
  check_fraud_indicators: 'Fraud',
  check_prior_claims: 'Prior Claims',
  get_adjuster: 'Adjuster',
  submit_decision: 'Submit',
};

function WorkflowPill({ tool, status }: { tool: string; status: 'match' | 'extra' | 'missing' }) {
  const label = TOOL_LABELS[tool] ?? tool;
  const colors = {
    match: 'bg-green-900/40 text-green-300 border-green-500/30',
    extra: 'bg-red-900/40 text-red-300 border-red-500/30',
    missing: 'bg-slate-800/60 text-slate-500 border-slate-600/30',
  };
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded border ${colors[status]}`}>
      {label}
    </span>
  );
}

interface ClaimScorecardProps {
  result: ClaimResult;
  actions: AgentAction[];
}

function ClaimScorecard({ result, actions }: ClaimScorecardProps) {
  const wastedSteps = Math.max(0, result.steps - result.optimalSteps);
  const hasRework = result.reworkCount > 0;
  const hasMistakes = result.mistakes.length > 0;

  // Header color
  let headerClass = 'border-green-500/40 bg-green-900/20';
  let headerIcon = '\u2705';
  let headerLabel = 'CORRECT';
  if (!result.correct) {
    headerClass = 'border-red-500/40 bg-red-900/20';
    headerIcon = '\u274C';
    headerLabel = 'INCORRECT';
  } else if (hasRework) {
    headerClass = 'border-amber-500/40 bg-amber-900/20';
    headerIcon = '\u26A0\uFE0F';
    headerLabel = 'CORRECT (with rework)';
  }

  // Build workflow comparison
  const expected = result.expectedWorkflow;
  const actual = result.actualWorkflow;
  const expectedSet = new Set(expected);
  const actualUnique = [...new Set(actual)];

  return (
    <div className={`rounded-lg border-2 p-3 space-y-2.5 ${headerClass}`}>
      {/* Header */}
      <div className="flex items-center gap-2">
        <span className="text-base">{headerIcon}</span>
        <span className="text-sm font-bold text-white">{headerLabel}</span>
        <span className="text-xs text-slate-400 ml-auto uppercase font-medium">{result.decision}</span>
      </div>

      {/* Steps */}
      <div className="flex items-center gap-3 text-xs">
        <div className="flex items-center gap-1.5">
          <span className="text-slate-400">Steps:</span>
          <span className="text-white font-medium">{result.steps}</span>
          <span className="text-slate-500">({result.optimalSteps} optimal{wastedSteps > 0 ? `, +${wastedSteps} extra` : ''})</span>
        </div>
        <div className="flex-1 bg-slate-700/50 rounded-full h-1.5">
          <div
            className={`h-1.5 rounded-full transition-all ${wastedSteps === 0 ? 'bg-green-500' : wastedSteps <= 2 ? 'bg-amber-500' : 'bg-red-500'}`}
            style={{ width: `${Math.min(100, (result.optimalSteps / result.steps) * 100)}%` }}
          />
        </div>
      </div>

      {/* Rework count */}
      {hasRework && (
        <p className="text-xs text-amber-300">
          {result.reworkCount} rejection{result.reworkCount > 1 ? 's' : ''} before accepted
        </p>
      )}

      {/* Mistakes */}
      {hasMistakes && (
        <div className="space-y-1">
          <p className="text-xs font-semibold text-red-400">Mistakes:</p>
          {result.mistakes.map((m, i) => (
            <p key={i} className="text-xs text-red-300/80 pl-2 border-l-2 border-red-500/30">
              {m.description}
            </p>
          ))}
        </div>
      )}

      {/* Workflow comparison */}
      <div className="space-y-1.5">
        <p className="text-xs text-slate-400">Expected workflow:</p>
        <div className="flex flex-wrap gap-1">
          {expected.map((tool, i) => (
            <WorkflowPill
              key={`exp-${i}`}
              tool={tool}
              status={actual.includes(tool) ? 'match' : 'missing'}
            />
          ))}
        </div>
        {actualUnique.some(t => !expectedSet.has(t)) && (
          <>
            <p className="text-xs text-slate-400">Extra tools used:</p>
            <div className="flex flex-wrap gap-1">
              {actualUnique.filter(t => !expectedSet.has(t) && t !== 'thinking').map((tool, i) => (
                <WorkflowPill key={`extra-${i}`} tool={tool} status="extra" />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

interface ActivityLogProps {
  actions: AgentAction[];
  memoryInjection: MemoryInjection | null;
  isThinking: boolean;
  isStoringMemory: boolean;
  result?: ClaimResult;
}

export function ActivityLog({ actions, memoryInjection, isThinking, isStoringMemory, result }: ActivityLogProps) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new actions arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [actions.length, isThinking]);

  return (
    <div className="bg-slate-800/40 rounded-lg border border-slate-700/50 flex flex-col h-full">
      <div className="px-3 py-2 border-b border-slate-700/50">
        <h2 className="text-sm font-semibold text-slate-300">Activity Log</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {/* Memory injection event */}
        {memoryInjection && <MemoryCard memoryInjection={memoryInjection} />}

        {/* Actions */}
        {actions.map((action, i) => {
          // Render rejection callout for DECISION REJECTED
          if (action.toolName === 'submit_decision' && action.toolResult.startsWith('DECISION REJECTED')) {
            const attemptNumber = countPriorRejections(actions, i) + 1;
            return <RejectionCallout key={i} action={action} attemptNumber={attemptNumber} />;
          }

          return (
            <ActionEntry
              key={i}
              action={action}
              expanded={expandedIdx === i}
              onToggle={() => setExpandedIdx(expandedIdx === i ? null : i)}
            />
          );
        })}

        {/* Thinking indicator */}
        {isThinking && (
          <div className="rounded-lg border border-blue-500/20 bg-blue-900/10 p-3 animate-pulse">
            <div className="flex items-center gap-2">
              <span className="text-base">{'\u{1F4AD}'}</span>
              <span className="text-sm text-blue-300">Agent thinking...</span>
            </div>
          </div>
        )}

        {/* Storing memory indicator */}
        {isStoringMemory && (
          <div className="rounded-lg border border-purple-500/20 bg-purple-900/10 p-3 animate-pulse">
            <div className="flex items-center gap-2">
              <span className="text-base">{'\u{1F4BE}'}</span>
              <span className="text-sm text-purple-300">Storing to memory...</span>
            </div>
          </div>
        )}

        {/* Claim Scorecard */}
        {result && actions.length > 0 && (
          <ClaimScorecard result={result} actions={actions} />
        )}

        {/* Empty state */}
        {actions.length === 0 && !isThinking && !memoryInjection && (
          <div className="flex items-center justify-center h-32 text-slate-500 text-sm">
            Tool calls will appear here as the agent processes a claim.
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
