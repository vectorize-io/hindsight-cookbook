import { useEffect, useRef } from 'react';
import type { CustomerScenario } from '../types.ts';

interface CustomerChatProps {
  scenario: CustomerScenario | null;
  sentResponses: string[];
  customerReplies: string[];
}

export function CustomerChat({ scenario, sentResponses, customerReplies }: CustomerChatProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [sentResponses.length, customerReplies.length]);

  if (!scenario) {
    return (
      <div className="h-full flex flex-col">
        <div className="px-4 py-3 border-b border-gray-800">
          <h2 className="text-sm font-semibold text-gray-400">Customer Chat</h2>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-gray-600">
            <p className="text-sm">No active customer</p>
            <p className="text-xs mt-1">Click "Next Customer" to start</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Account banner */}
      <div className="px-4 py-3 border-b border-gray-800 bg-gray-900/50">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm font-semibold text-gray-200">{scenario.customerName}</span>
            <span className="text-xs text-gray-500 ml-2">#{scenario.accountId}</span>
          </div>
          <span className={`text-xs font-medium px-2 py-0.5 rounded ${categoryStyle(scenario.category)}`}>
            {scenario.category}
          </span>
        </div>
        <div className="flex gap-3 mt-1 text-xs text-gray-500">
          <span>{scenario.planName} plan</span>
          <span>{scenario.tenure}mo tenure</span>
          {scenario.contractMonths > 0 && <span>{scenario.contractMonths}mo contract</span>}
          <span>{scenario.area}</span>
        </div>
      </div>

      {/* Chat messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Customer's initial message */}
        <ChatBubble sender="customer" name={scenario.customerName}>
          {scenario.customerMessage}
        </ChatBubble>

        {/* Interleaved CSR responses and customer replies */}
        {sentResponses.map((msg, i) => (
          <div key={i} className="space-y-4">
            <ChatBubble sender="csr">{msg}</ChatBubble>
            {customerReplies[i] && (
              <ChatBubble sender="customer" name={scenario.customerName}>
                {customerReplies[i]}
              </ChatBubble>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function ChatBubble({
  sender,
  name,
  children,
}: {
  sender: 'customer' | 'csr';
  name?: string;
  children: React.ReactNode;
}) {
  if (sender === 'customer') {
    return (
      <div className="flex gap-3 max-w-[85%]">
        <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-xs font-bold text-gray-300 flex-shrink-0">
          {name ? name[0] : 'C'}
        </div>
        <div>
          {name && <p className="text-xs text-gray-500 mb-1">{name}</p>}
          <div className="bg-gray-800 rounded-2xl rounded-tl-sm px-4 py-2.5">
            <p className="text-sm text-gray-200 leading-relaxed">{children}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 max-w-[85%] ml-auto flex-row-reverse">
      <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-xs font-bold text-white flex-shrink-0">
        You
      </div>
      <div>
        <p className="text-xs text-gray-500 mb-1 text-right">You (CSR)</p>
        <div className="bg-blue-600/20 border border-blue-500/30 rounded-2xl rounded-tr-sm px-4 py-2.5">
          <p className="text-sm text-blue-100 leading-relaxed">{children}</p>
        </div>
      </div>
    </div>
  );
}

function categoryStyle(category: string): string {
  switch (category) {
    case 'billing': return 'bg-blue-500/20 text-blue-300';
    case 'credit': return 'bg-amber-500/20 text-amber-300';
    case 'technical': return 'bg-orange-500/20 text-orange-300';
    case 'retention': return 'bg-purple-500/20 text-purple-300';
    case 'outage': return 'bg-red-500/20 text-red-300';
    default: return 'bg-gray-500/20 text-gray-300';
  }
}
