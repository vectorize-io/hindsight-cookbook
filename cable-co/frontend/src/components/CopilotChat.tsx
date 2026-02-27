import { useEffect, useRef, useState } from 'react';
import type { AgentAction, PendingSuggestion, MemoryRecall } from '../types.ts';

interface CsrMessage {
  message: string;
  index: number;
}

interface CopilotChatProps {
  actions: AgentAction[];
  pendingSuggestion: PendingSuggestion | null;
  memoryRecall: MemoryRecall | null;
  csrMessages: CsrMessage[];
  isThinking: boolean;
  isStoringMemory: boolean;
  isProcessing: boolean;
  onApprove: (suggestionId: string) => void;
  onReject: (suggestionId: string, feedback: string) => void;
  onSendMessage: (message: string) => void;
}

export function CopilotChat({
  actions, pendingSuggestion, memoryRecall, csrMessages,
  isThinking, isStoringMemory, isProcessing,
  onApprove, onReject, onSendMessage,
}: CopilotChatProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [inputText, setInputText] = useState('');

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [actions, pendingSuggestion, isThinking, csrMessages]);

  const isEmpty = actions.length === 0 && !memoryRecall && !isThinking && !pendingSuggestion;

  const handleSend = () => {
    if (inputText.trim() && isProcessing) {
      onSendMessage(inputText.trim());
      setInputText('');
    }
  };

  // Build interleaved list of actions and CSR messages
  const chatItems: Array<{ type: 'action'; action: AgentAction; key: string } | { type: 'csr'; message: string; key: string }> = [];
  let csrMsgIdx = 0;
  for (let i = 0; i < actions.length; i++) {
    // Insert any CSR messages that belong before this action
    while (csrMsgIdx < csrMessages.length && csrMessages[csrMsgIdx].index <= i) {
      chatItems.push({ type: 'csr', message: csrMessages[csrMsgIdx].message, key: `csr-${csrMsgIdx}` });
      csrMsgIdx++;
    }
    chatItems.push({ type: 'action', action: actions[i], key: `action-${i}` });
  }
  // Any remaining CSR messages after all actions
  while (csrMsgIdx < csrMessages.length) {
    chatItems.push({ type: 'csr', message: csrMessages[csrMsgIdx].message, key: `csr-${csrMsgIdx}` });
    csrMsgIdx++;
  }

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-3 border-b border-gray-800 bg-gray-900/50">
        <h2 className="text-sm font-semibold text-gray-400">AI Copilot</h2>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
        {isEmpty && (
          <div className="text-center text-gray-600 py-8">
            <p className="text-sm">Copilot is ready</p>
            <p className="text-xs mt-1">I'll suggest responses and actions when a customer connects</p>
          </div>
        )}

        {/* Memory recall */}
        {memoryRecall && memoryRecall.text && (
          <MemoryBubble recall={memoryRecall} />
        )}

        {/* Interleaved actions and CSR messages */}
        {chatItems.map((item) =>
          item.type === 'action' ? (
            <ResolvedMessage key={item.key} action={item.action} />
          ) : (
            <CsrBubble key={item.key}>
              <p className="text-xs text-blue-200">{item.message}</p>
            </CsrBubble>
          )
        )}

        {/* Pending suggestion */}
        {pendingSuggestion && (
          <PendingMessage
            suggestion={pendingSuggestion}
            onApprove={onApprove}
            onReject={onReject}
          />
        )}

        {/* Thinking */}
        {isThinking && !pendingSuggestion && (
          <CopilotBubble>
            <div className="flex items-center gap-2 text-gray-400">
              <span className="flex gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-bounce" style={{ animationDelay: '300ms' }} />
              </span>
              <span className="text-xs">Analyzing...</span>
            </div>
          </CopilotBubble>
        )}

        {/* Storing memory */}
        {isStoringMemory && (
          <CopilotBubble>
            <p className="text-xs text-purple-400">Saving feedback to memory...</p>
          </CopilotBubble>
        )}
      </div>

      {/* CSR text input */}
      <div className="px-4 py-3 border-t border-gray-800 bg-gray-900/50">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSend(); }}
            placeholder={isProcessing ? "Give the copilot feedback..." : "Start a customer scenario first"}
            disabled={!isProcessing}
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={!isProcessing || !inputText.trim()}
            className="px-4 py-2 text-xs font-medium rounded-lg bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 transition-colors"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

/** Copilot chat bubble wrapper */
function CopilotBubble({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex gap-3 max-w-[90%]">
      <div className="w-7 h-7 rounded-full bg-emerald-600/30 flex items-center justify-center text-xs flex-shrink-0">
        <span className="text-emerald-400 font-bold text-[10px]">AI</span>
      </div>
      <div className="flex-1 min-w-0">
        {children}
      </div>
    </div>
  );
}

/** CSR feedback bubble (shown after rejection) */
function CsrBubble({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex gap-3 max-w-[85%] ml-auto flex-row-reverse">
      <div className="w-7 h-7 rounded-full bg-blue-600/40 flex items-center justify-center text-[10px] font-bold text-blue-300 flex-shrink-0">
        You
      </div>
      <div className="bg-blue-600/10 border border-blue-500/20 rounded-xl rounded-tr-sm px-3 py-2">
        {children}
      </div>
    </div>
  );
}

function MemoryBubble({ recall }: { recall: MemoryRecall }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <CopilotBubble>
      <div
        className="bg-purple-950/30 border border-purple-500/20 rounded-xl rounded-tl-sm px-3 py-2 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <p className="text-xs text-purple-400 font-medium">
          I remember from past interactions ({recall.method}, {recall.timing.toFixed(1)}s)
          <span className="text-purple-500/50 ml-1">{expanded ? '\u25B2' : '\u25BC'}</span>
        </p>
        {expanded && recall.text && (
          <p className="text-xs text-purple-300/70 mt-2 whitespace-pre-wrap max-h-48 overflow-y-auto">
            {recall.text}
          </p>
        )}
      </div>
    </CopilotBubble>
  );
}

/** A resolved action — already approved or rejected */
function ResolvedMessage({ action }: { action: AgentAction }) {
  const [expanded, setExpanded] = useState(false);

  // Lookups — compact info line
  if (action.isLookup) {
    return (
      <CopilotBubble>
        <div
          className="bg-gray-800/50 rounded-xl rounded-tl-sm px-3 py-2 cursor-pointer"
          onClick={() => setExpanded(!expanded)}
        >
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">Looked up</span>
            <span className="text-xs text-gray-400 font-mono">{friendlyToolName(action.toolName)}</span>
            <span className="text-gray-600 text-xs ml-auto">{expanded ? '\u25B2' : '\u25BC'}</span>
          </div>
          {expanded && (
            <pre className="text-xs text-gray-400 whitespace-pre-wrap max-h-32 overflow-y-auto mt-2 bg-gray-900/50 rounded p-2">
              {formatToolResult(action.toolResult)}
            </pre>
          )}
        </div>
      </CopilotBubble>
    );
  }

  // Approved suggest_response
  if (action.toolName === 'suggest_response' && !action.rejected) {
    return (
      <CopilotBubble>
        <div className="bg-emerald-950/20 border border-emerald-500/20 rounded-xl rounded-tl-sm px-3 py-2">
          <p className="text-xs text-emerald-400 font-medium mb-1">Response sent to customer</p>
          <p className="text-sm text-gray-300 italic">"{action.toolArgs.message as string}"</p>
        </div>
      </CopilotBubble>
    );
  }

  // Rejected suggest_response
  if (action.toolName === 'suggest_response' && action.rejected) {
    return (
      <>
        <CopilotBubble>
          <div className="bg-red-950/20 border border-red-500/20 rounded-xl rounded-tl-sm px-3 py-2">
            <p className="text-xs text-red-400 font-medium mb-1">Suggested response (rejected)</p>
            <p className="text-sm text-gray-400 line-through italic">"{action.toolArgs.message as string}"</p>
          </div>
        </CopilotBubble>
        {action.rejectionFeedback && (
          <CsrBubble>
            <p className="text-xs text-blue-200">{action.rejectionFeedback}</p>
          </CsrBubble>
        )}
      </>
    );
  }

  // Approved action
  if (action.isAction && !action.rejected) {
    return (
      <CopilotBubble>
        <div className="bg-emerald-950/20 border border-emerald-500/20 rounded-xl rounded-tl-sm px-3 py-2">
          <div className="flex items-center gap-2">
            <span className="text-emerald-400 text-xs font-bold">{'\u2713'}</span>
            <span className="text-xs text-emerald-400 font-medium">Action approved</span>
          </div>
          <p className="text-sm text-gray-300 mt-1">{formatSuggestion(action.toolName, action.toolArgs)}</p>
          <p className="text-xs text-gray-500 mt-1">{action.toolResult}</p>
        </div>
      </CopilotBubble>
    );
  }

  // Rejected action
  if (action.isAction && action.rejected) {
    return (
      <>
        <CopilotBubble>
          <div className="bg-red-950/20 border border-red-500/20 rounded-xl rounded-tl-sm px-3 py-2">
            <div className="flex items-center gap-2">
              <span className="text-red-400 text-xs font-bold">{'\u2717'}</span>
              <span className="text-xs text-red-400 font-medium">Action rejected</span>
            </div>
            <p className="text-sm text-gray-400 mt-1">{formatSuggestion(action.toolName, action.toolArgs)}</p>
          </div>
        </CopilotBubble>
        {action.rejectionFeedback && (
          <CsrBubble>
            <p className="text-xs text-blue-200">{action.rejectionFeedback}</p>
          </CsrBubble>
        )}
      </>
    );
  }

  // Terminal / resolve
  return (
    <CopilotBubble>
      <div className="bg-gray-800/50 border border-gray-700/30 rounded-xl rounded-tl-sm px-3 py-2">
        <p className="text-xs text-gray-400 font-medium">Interaction resolved</p>
        <p className="text-xs text-gray-500 mt-1">{action.toolResult}</p>
      </div>
    </CopilotBubble>
  );
}

/** A pending suggestion waiting for CSR input */
function PendingMessage({
  suggestion, onApprove, onReject,
}: {
  suggestion: PendingSuggestion;
  onApprove: (id: string) => void;
  onReject: (id: string, feedback: string) => void;
}) {
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [feedback, setFeedback] = useState(suggestion.rejectionHint ?? '');
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setShowRejectInput(false);
    setFeedback(suggestion.rejectionHint ?? '');
  }, [suggestion.suggestionId, suggestion.rejectionHint]);

  useEffect(() => {
    if (showRejectInput && inputRef.current) {
      inputRef.current.focus();
    }
  }, [showRejectInput]);

  const isResponse = suggestion.toolName === 'suggest_response';

  return (
    <CopilotBubble>
      <div className="bg-amber-950/20 border border-amber-500/30 rounded-xl rounded-tl-sm px-3 py-3 space-y-2">
        {/* Header */}
        {isResponse ? (
          <>
            <p className="text-xs text-amber-400 font-medium">I suggest responding to the customer:</p>
            <div className="bg-gray-900/50 rounded-lg px-3 py-2 border border-gray-700/30">
              <p className="text-sm text-gray-200 leading-relaxed">{suggestion.toolArgs.message as string}</p>
            </div>
          </>
        ) : (
          <>
            <p className="text-xs text-amber-400 font-medium">I recommend this action:</p>
            <p className="text-sm text-gray-200 mt-1">{formatSuggestion(suggestion.toolName, suggestion.toolArgs)}</p>
          </>
        )}

        {/* Reasoning */}
        {suggestion.reasoning && (
          <p className="text-xs text-gray-500 italic">{suggestion.reasoning}</p>
        )}

        {/* Policy hint */}
        {suggestion.rejectionHint && !showRejectInput && (
          <div className="bg-amber-950/30 border border-amber-500/15 rounded px-2 py-1.5">
            <p className="text-xs text-amber-300/60">
              <span className="font-semibold">Policy note:</span> {suggestion.rejectionHint}
            </p>
          </div>
        )}

        {/* Reject input */}
        {showRejectInput && (
          <div className="space-y-2">
            <textarea
              ref={inputRef}
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder={isResponse ? "How should the response be different?" : "Explain why this action is wrong..."}
              className="w-full bg-gray-900 border border-red-500/30 rounded-lg p-2 text-xs text-gray-200 resize-none"
              rows={3}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && feedback.trim()) {
                  onReject(suggestion.suggestionId, feedback.trim());
                }
              }}
            />
            <div className="flex gap-2">
              <button
                onClick={() => { if (feedback.trim()) onReject(suggestion.suggestionId, feedback.trim()); }}
                disabled={!feedback.trim()}
                className="px-3 py-1.5 text-xs font-medium rounded-lg bg-red-600 hover:bg-red-700 text-white disabled:opacity-50"
              >
                Submit
              </button>
              <button
                onClick={() => setShowRejectInput(false)}
                className="px-3 py-1.5 text-xs font-medium rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-300"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Buttons */}
        {!showRejectInput && (
          <div className="flex gap-2">
            <button
              onClick={() => onApprove(suggestion.suggestionId)}
              className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white transition-colors"
            >
              {isResponse ? 'Send to Customer' : 'Approve'}
            </button>
            <button
              onClick={() => setShowRejectInput(true)}
              className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-red-600/80 hover:bg-red-700 text-white transition-colors"
            >
              {isResponse ? 'Revise' : 'Reject'}
            </button>
          </div>
        )}
      </div>
    </CopilotBubble>
  );
}

function formatSuggestion(toolName: string, args: Record<string, unknown>): string {
  switch (toolName) {
    case 'post_adjustment':
      return `Post ${args.adjustment_code} credit of $${args.amount} \u2014 "${args.memo}"`;
    case 'create_service_order':
      return `Create ${args.order_type} service order for ${args.account_id}`;
    case 'create_trouble_ticket':
      return `Create trouble ticket (${args.symptom_code}) for ${args.account_id}`;
    case 'schedule_dispatch':
      return `Schedule technician dispatch (slot ${args.slot_id}) for ticket ${args.ticket_id}`;
    case 'create_equipment_order':
      return `${args.action} ${args.equipment_type} for ${args.account_id}`;
    case 'apply_retention_offer':
      return `Apply retention offer ${args.offer_code} to ${args.account_id}`;
    default:
      return `${toolName}(${JSON.stringify(args)})`;
  }
}

function friendlyToolName(name: string): string {
  return name.replace(/_/g, ' ').replace(/^(get|check|run)\s/, '');
}

function formatToolResult(result: string): string {
  try {
    return JSON.stringify(JSON.parse(result), null, 2);
  } catch {
    return result;
  }
}
