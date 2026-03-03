import type { PipelineStage } from '../types.ts';

const STAGES: { key: PipelineStage; label: string }[] = [
  { key: 'received', label: 'Received' },
  { key: 'classified', label: 'Classified' },
  { key: 'verified', label: 'Verified' },
  { key: 'routed', label: 'Routed' },
  { key: 'resolved', label: 'Resolved' },
];

const STAGE_ORDER: PipelineStage[] = ['received', 'classified', 'verified', 'routed', 'resolved'];

function stageIndex(stage: PipelineStage): number {
  return STAGE_ORDER.indexOf(stage);
}

interface PipelineProps {
  currentStage: PipelineStage;
  isProcessing: boolean;
  currentStep?: number;
}

export function Pipeline({ currentStage, isProcessing, currentStep }: PipelineProps) {
  const currentIdx = stageIndex(currentStage);

  return (
    <div className="flex items-center gap-1 px-4 py-3 bg-slate-800/50 border-b border-slate-700/50">
      {STAGES.map((stage, i) => {
        const idx = stageIndex(stage.key);
        const isActive = idx === currentIdx && isProcessing;
        const isComplete = idx < currentIdx || (stage.key === 'resolved' && currentStage === 'resolved');
        let dotClass = 'bg-slate-600'; // pending
        if (isComplete) dotClass = 'bg-green-500';
        else if (isActive) dotClass = 'bg-blue-500 animate-pulse';

        let labelClass = 'text-slate-500';
        if (isComplete) labelClass = 'text-green-400';
        else if (isActive) labelClass = 'text-blue-400';

        return (
          <div key={stage.key} className="flex items-center gap-1">
            {i > 0 && (
              <div className={`w-8 h-0.5 ${isComplete ? 'bg-green-500/50' : 'bg-slate-700'}`} />
            )}
            <div className="flex items-center gap-1.5">
              <div className={`w-3 h-3 rounded-full ${dotClass} transition-colors duration-300`} />
              <span className={`text-xs font-medium ${labelClass} transition-colors duration-300`}>
                {stage.label}
              </span>
            </div>
          </div>
        );
      })}
      {isProcessing && currentStep != null && (
        <span className="text-xs text-slate-400 ml-auto">Step {currentStep} / ~7</span>
      )}
    </div>
  );
}
