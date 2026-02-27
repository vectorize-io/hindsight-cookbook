import type { Claim, PipelineStage, ClaimResult } from '../types.ts';

const CATEGORY_COLORS: Record<string, string> = {
  auto: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  property: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
  liability: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
  health: 'bg-pink-500/20 text-pink-300 border-pink-500/30',
  water_damage: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  flood: 'bg-teal-500/20 text-teal-300 border-teal-500/30',
  fire: 'bg-red-500/20 text-red-300 border-red-500/30',
};

function OutcomeBanner({ result }: { result: ClaimResult }) {
  const extraSteps = result.steps - result.optimalSteps;

  let borderColor: string;
  let bgColor: string;
  let textColor: string;
  let icon: string;
  let label: string;

  if (!result.correct) {
    borderColor = 'border-red-500/50';
    bgColor = 'bg-red-950/30';
    textColor = 'text-red-300';
    icon = '\u274C';
    label = 'Incorrect decision';
  } else if (result.reworkCount > 0) {
    borderColor = 'border-amber-500/50';
    bgColor = 'bg-amber-950/30';
    textColor = 'text-amber-300';
    icon = '\u{1F504}';
    label = `Correct after ${result.reworkCount} rework${result.reworkCount > 1 ? 's' : ''}`;
  } else {
    borderColor = 'border-green-500/50';
    bgColor = 'bg-green-950/30';
    textColor = 'text-green-300';
    icon = '\u2705';
    label = `Correct in ${result.steps} steps`;
  }

  return (
    <div className={`rounded-lg border ${borderColor} ${bgColor} p-3`}>
      <div className="flex items-center gap-2">
        <span className="text-base">{icon}</span>
        <span className={`text-sm font-semibold ${textColor}`}>{label}</span>
      </div>
      {extraSteps > 0 && (
        <p className="text-xs text-slate-400 mt-1">
          +{extraSteps} step{extraSteps > 1 ? 's' : ''} vs optimal ({result.optimalSteps})
        </p>
      )}
    </div>
  );
}

interface ClaimCardProps {
  claim: Claim | null;
  stage: PipelineStage;
  result?: ClaimResult;
}

export function ClaimCard({ claim, stage, result }: ClaimCardProps) {
  if (!claim) {
    return (
      <div className="bg-slate-800/60 rounded-lg border border-slate-700/50 p-4 h-full flex items-center justify-center">
        <p className="text-slate-500 text-sm">No claim loaded. Click "Process Claim" to start.</p>
      </div>
    );
  }

  const categoryStyle = CATEGORY_COLORS[claim.category] ?? 'bg-slate-500/20 text-slate-300 border-slate-500/30';
  const resolved = stage === 'resolved';

  return (
    <div className={`bg-slate-800/60 rounded-lg border ${resolved ? 'border-green-500/30' : 'border-slate-700/50'} p-4 h-full flex flex-col gap-3`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-lg font-bold text-white">Claim #{claim.claimId}</span>
        <span className={`text-xs px-2 py-0.5 rounded-full border ${categoryStyle}`}>
          {claim.category.replace('_', ' ')}
        </span>
      </div>

      {/* Amount */}
      <div className="text-2xl font-mono font-bold text-emerald-400">
        ${claim.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </div>

      {/* Details */}
      <div className="space-y-2 text-sm flex-1">
        <div className="flex justify-between">
          <span className="text-slate-400">Claimant</span>
          <span className="text-slate-200">{claim.claimantName}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Policy</span>
          <span className="text-slate-200 font-mono">{claim.policyId}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Region</span>
          <span className="text-slate-200">{claim.region}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Incident</span>
          <span className="text-slate-200">{claim.incidentDate}</span>
        </div>
      </div>

      {/* Description */}
      <div className="bg-slate-900/50 rounded p-3 border border-slate-700/30">
        <p className="text-xs text-slate-400 mb-1">Description</p>
        <p className="text-sm text-slate-200 leading-relaxed">{claim.description}</p>
      </div>

      {/* Outcome Banner */}
      {resolved && result && (
        <OutcomeBanner result={result} />
      )}
    </div>
  );
}
