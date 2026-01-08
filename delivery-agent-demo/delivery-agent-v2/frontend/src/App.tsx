import { useEffect, useState, useCallback } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { useGameStore } from './stores/gameStore';
import { PhaserGame } from './game/PhaserGame';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import type { Employee } from './types';

// Demo config type
interface DemoConfig {
  systemPrompt: string;
  llmModel: string;
  hindsight: {
    apiUrl: string;
    storeConversations: boolean;
    injectMemories: boolean;
    useReflect: boolean;
  };
  tools: { name: string; description: string }[];
}

// Building info type
interface BuildingInfo {
  floors: number;
  businesses: {
    name: string;
    floor: number;
    side: string;
    employees: { name: string; role: string }[];
  }[];
}

function ActionLogEntry({ action, expanded, onToggle }: {
  action: {
    step: number;
    toolName: string;
    toolArgs: Record<string, unknown>;
    toolResult: string;
    thinking?: string;
    memoryInjection?: { injected: boolean; count: number; context?: string; bankId?: string; query?: string; error?: string | null };
  };
  expanded: boolean;
  onToggle: () => void;
}) {
  const [memoryExpanded, setMemoryExpanded] = useState(false);
  const getToolIcon = (name: string) => {
    const icons: Record<string, string> = {
      'go_up': '⬆️',
      'go_down': '⬇️',
      'go_to_front': '➡️',
      'go_to_back': '⬅️',
      'get_employee_list': '📋',
      'deliver_package': '📦',
      'check_current_location': '📍',
    };
    return icons[name] || '🔧';
  };

  return (
    <div
      className="bg-slate-700/50 rounded-lg p-3 cursor-pointer hover:bg-slate-700 transition-colors"
      onClick={onToggle}
    >
      <div className="flex items-center gap-3">
        <span className="text-lg">{getToolIcon(action.toolName)}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-green-400 font-medium">{action.toolName}</span>
            {Object.keys(action.toolArgs).length > 0 && (
              <span className="text-slate-500 text-xs">
                ({Object.entries(action.toolArgs).map(([k, v]) => `${k}=${v}`).join(', ')})
              </span>
            )}
          </div>
          {!expanded && (
            <div className="text-slate-400 text-xs truncate mt-0.5">
              {action.toolResult}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-slate-500 text-xs font-mono">#{action.step}</span>
          <span className="text-slate-400 text-xs">{expanded ? '▼' : '▶'}</span>
        </div>
      </div>

      {expanded && (
        <div className="mt-3 space-y-2 text-sm">
          {action.memoryInjection && (
            <div className={`border rounded ${action.memoryInjection.count > 0 ? 'bg-purple-900/30 border-purple-500/30' : action.memoryInjection.error ? 'bg-red-900/30 border-red-500/30' : 'bg-slate-800/50 border-slate-600/30'}`}>
              <button
                onClick={(e) => { e.stopPropagation(); setMemoryExpanded(!memoryExpanded); }}
                className={`w-full text-left px-2 py-1.5 flex items-center justify-between ${action.memoryInjection.count > 0 ? 'text-purple-400' : action.memoryInjection.error ? 'text-red-400' : 'text-slate-400'}`}
              >
                <div className="text-xs uppercase flex items-center gap-2">
                  <span>Hindsight Memory</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] ${action.memoryInjection.count > 0 ? 'bg-purple-500/30' : action.memoryInjection.error ? 'bg-red-500/30' : 'bg-slate-600/30'}`}>
                    {action.memoryInjection.error ? 'Error' : `${action.memoryInjection.count} results`}
                  </span>
                </div>
                <span className="text-[10px]">{memoryExpanded ? '▼' : '▶'}</span>
              </button>
              {memoryExpanded && (
                <div className="px-2 pb-2">
                  {/* Debug info - bank and query */}
                  {(action.memoryInjection.bankId || action.memoryInjection.query) && (
                    <div className="text-[10px] text-slate-500 mb-2 font-mono space-y-0.5">
                      {action.memoryInjection.bankId && <div>Bank: {action.memoryInjection.bankId}</div>}
                      {action.memoryInjection.query && <div>Query: {action.memoryInjection.query.slice(0, 100)}...</div>}
                    </div>
                  )}
                  {action.memoryInjection.error ? (
                    <div className="text-red-300 text-xs font-mono">
                      {action.memoryInjection.error}
                    </div>
                  ) : action.memoryInjection.context ? (
                    <div className="text-purple-200 text-xs font-mono whitespace-pre-wrap max-h-32 overflow-y-auto">
                      {action.memoryInjection.context}
                    </div>
                  ) : (
                    <div className="text-slate-400 text-xs italic">
                      {action.memoryInjection.count === 0 ? 'No relevant memories found' : 'Memory context not available'}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
          {action.thinking && (
            <div className="bg-slate-800 rounded p-2">
              <div className="text-slate-500 text-xs uppercase mb-1">Thinking</div>
              <div className="text-slate-300 text-xs italic">{action.thinking}</div>
            </div>
          )}
          <div className="bg-slate-800 rounded p-2">
            <div className="text-slate-500 text-xs uppercase mb-1">Result</div>
            <div className="text-green-300 text-xs font-mono whitespace-pre-wrap">{action.toolResult}</div>
          </div>
        </div>
      )}
    </div>
  );
}

function App() {
  const { connected, isConnecting, startDelivery, cancelDelivery, resetMemory } = useWebSocket();
  const {
    agentFloor,
    agentSide,
    isThinking,
    isAnimating,
    thinkingText,
    deliveryStatus,
    deliverySteps,
    currentPackage,
    actions,
    deliveriesCompleted,
    totalSteps,
    history,
    bankId,
    includeBusiness,
    maxSteps,
    setIncludeBusiness,
    setMaxSteps,
    resetHistory,
  } = useGameStore();

  const [employees, setEmployees] = useState<Employee[]>([]);
  const [selectedRecipient, setSelectedRecipient] = useState<string>('');
  const [expandedAction, setExpandedAction] = useState<number | null>(null);
  const [demoConfig, setDemoConfig] = useState<DemoConfig | null>(null);
  const [buildingInfo, setBuildingInfo] = useState<BuildingInfo | null>(null);
  const [showDemoInfo, setShowDemoInfo] = useState(false);
  const [showBuildingLayout, setShowBuildingLayout] = useState(false);

  // Fetch employees, demo config, and building info on mount
  useEffect(() => {
    fetch('/api/building/employees')
      .then(res => res.json())
      .then(data => setEmployees(data.employees))
      .catch(console.error);

    fetch('/api/demo-config')
      .then(res => res.json())
      .then(data => setDemoConfig(data))
      .catch(console.error);

    fetch('/api/building')
      .then(res => res.json())
      .then(data => setBuildingInfo(data))
      .catch(console.error);
  }, []);

  // Auto-expand latest action when it changes
  useEffect(() => {
    if (actions.length > 0) {
      setExpandedAction(actions.length - 1);
    }
  }, [actions.length]);

  const handleStartDelivery = () => {
    if (selectedRecipient) {
      startDelivery(selectedRecipient, includeBusiness, maxSteps);
    }
  };

  const handleRandomDelivery = () => {
    if (employees.length > 0) {
      const randomEmployee = employees[Math.floor(Math.random() * employees.length)];
      setSelectedRecipient(randomEmployee.name);
      startDelivery(randomEmployee.name, includeBusiness, maxSteps);
    }
  };

  const handleResetMemory = () => {
    if (confirm('This will clear all agent memories and delivery history. Continue?')) {
      resetMemory();
      resetHistory();
    }
  };

  // Chart data - steps per delivery
  const chartData = history.map((h, i) => ({
    delivery: i + 1,
    steps: h.steps,
    success: h.success,
    optimal: getOptimalSteps(h.recipientName, employees),
  }));

  function getOptimalSteps(name: string, emps: Employee[]): number {
    const emp = emps.find(e => e.name === name);
    if (!emp) return 5;
    // Optimal: check location (1) + move floors + move sides + deliver (1)
    // From floor 1 middle: abs(emp.floor - 1) + (emp.side !== 'middle' ? 1 : 0) + 2
    return Math.abs(emp.floor - 1) + (emp.side !== 'middle' ? 1 : 0) + 2;
  }

  const avgSteps = history.length > 0
    ? (history.reduce((sum, h) => sum + h.steps, 0) / history.length).toFixed(1)
    : '-';

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-slate-100">
      {/* Header */}
      <header className="bg-slate-900/50 border-b border-slate-700 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-blue-400 font-mono">
              DELIVERY AGENT DEMO
            </h1>
            <p className="text-slate-500 text-sm">
              AI agent learning with Hindsight memory
            </p>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${
                connected ? 'bg-green-500 shadow-lg shadow-green-500/50' :
                isConnecting ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'
              }`} />
              <span className="text-sm text-slate-400">
                {connected ? 'Connected' : isConnecting ? 'Connecting...' : 'Disconnected'}
              </span>
            </div>
            {bankId && (
              <code className="text-xs bg-slate-800 px-2 py-1 rounded text-slate-400">
                {bankId}
              </code>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="p-6 max-w-7xl mx-auto">
        {/* Demo Info Collapsible */}
        <div className="mb-6">
          <button
            onClick={() => setShowDemoInfo(!showDemoInfo)}
            className="flex items-center gap-2 text-sm text-slate-400 hover:text-slate-300 transition-colors"
          >
            <span className={`transition-transform ${showDemoInfo ? 'rotate-90' : ''}`}>
              ▶
            </span>
            <span>Information about demo</span>
          </button>

          {showDemoInfo && demoConfig && (
            <div className="mt-3 bg-slate-800/50 rounded-xl p-4 border border-slate-700 space-y-4">
              {/* System Prompt */}
              <div>
                <h3 className="text-xs text-slate-500 uppercase tracking-wider mb-2">System Prompt</h3>
                <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700">
                  <code className="text-green-400 text-sm font-mono whitespace-pre-wrap">
                    {demoConfig.systemPrompt}
                  </code>
                </div>
              </div>

              {/* LLM Model */}
              <div>
                <h3 className="text-xs text-slate-500 uppercase tracking-wider mb-2">LLM Model</h3>
                <code className="text-blue-400 text-sm font-mono bg-slate-900/50 px-3 py-1.5 rounded border border-slate-700">
                  {demoConfig.llmModel}
                </code>
              </div>

              {/* Hindsight Settings */}
              <div>
                <h3 className="text-xs text-slate-500 uppercase tracking-wider mb-2">Hindsight Memory Settings</h3>
                <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700 space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400">API URL</span>
                    <code className="text-purple-400 font-mono text-xs">{demoConfig.hindsight.apiUrl}</code>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400">Inject Memories</span>
                    <span className={demoConfig.hindsight.injectMemories ? 'text-green-400' : 'text-red-400'}>
                      {demoConfig.hindsight.injectMemories ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400">Use Reflect</span>
                    <span className={demoConfig.hindsight.useReflect ? 'text-green-400' : 'text-slate-500'}>
                      {demoConfig.hindsight.useReflect ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400">Store Conversations</span>
                    <span className={demoConfig.hindsight.storeConversations ? 'text-green-400' : 'text-slate-500'}>
                      {demoConfig.hindsight.storeConversations ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Available Tools */}
              <div>
                <h3 className="text-xs text-slate-500 uppercase tracking-wider mb-2">Available Tools</h3>
                <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {demoConfig.tools.map(tool => (
                      <div key={tool.name} className="flex items-start gap-2 text-sm">
                        <code className="text-yellow-400 font-mono shrink-0">{tool.name}</code>
                        <span className="text-slate-500">-</span>
                        <span className="text-slate-400">{tool.description}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Building Layout - Collapsible */}
              <div>
                <button
                  onClick={() => setShowBuildingLayout(!showBuildingLayout)}
                  className="flex items-center gap-2 text-xs text-slate-500 uppercase tracking-wider mb-2 hover:text-slate-400 transition-colors"
                >
                  <span className={`transition-transform text-[10px] ${showBuildingLayout ? 'rotate-90' : ''}`}>
                    ▶
                  </span>
                  <span>Building Layout</span>
                </button>

                {showBuildingLayout && buildingInfo && (
                  <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700 space-y-4">
                    <div className="text-sm text-slate-400 mb-2">
                      {buildingInfo.floors} floors • {buildingInfo.businesses.length} businesses • {buildingInfo.businesses.reduce((acc, b) => acc + b.employees.length, 0)} employees
                    </div>

                    {/* Render floors from top to bottom */}
                    {[...Array(buildingInfo.floors)].map((_, i) => {
                      const floorNum = buildingInfo.floors - i;
                      const floorBusinesses = buildingInfo.businesses.filter(b => b.floor === floorNum);
                      const frontBiz = floorBusinesses.find(b => b.side === 'front');
                      const backBiz = floorBusinesses.find(b => b.side === 'back');

                      return (
                        <div key={floorNum} className="border border-slate-700 rounded-lg overflow-hidden">
                          <div className="bg-slate-700/50 px-3 py-1.5 text-xs font-medium text-slate-300">
                            Floor {floorNum}
                          </div>
                          <div className="grid grid-cols-2 divide-x divide-slate-700">
                            {/* Front side */}
                            <div className="p-2">
                              <div className="text-xs text-slate-500 uppercase mb-1">Front</div>
                              {frontBiz ? (
                                <div>
                                  <div className="text-sm font-medium text-cyan-400">{frontBiz.name}</div>
                                  <div className="mt-1 space-y-0.5">
                                    {frontBiz.employees.map(emp => (
                                      <div key={emp.name} className="text-xs text-slate-400">
                                        <span className="text-slate-300">{emp.name}</span>
                                        <span className="text-slate-500"> • {emp.role}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              ) : (
                                <div className="text-xs text-slate-500 italic">Empty</div>
                              )}
                            </div>
                            {/* Back side */}
                            <div className="p-2">
                              <div className="text-xs text-slate-500 uppercase mb-1">Back</div>
                              {backBiz ? (
                                <div>
                                  <div className="text-sm font-medium text-cyan-400">{backBiz.name}</div>
                                  <div className="mt-1 space-y-0.5">
                                    {backBiz.employees.map(emp => (
                                      <div key={emp.name} className="text-xs text-slate-400">
                                        <span className="text-slate-300">{emp.name}</span>
                                        <span className="text-slate-500"> • {emp.role}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              ) : (
                                <div className="text-xs text-slate-500 italic">Empty</div>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Game View */}
          <div className="lg:col-span-2 space-y-4">
            {/* Game Canvas */}
            <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-slate-300">Building View</h2>
                {currentPackage && (
                  <div className="flex items-center gap-2 bg-blue-500/20 text-blue-400 px-3 py-1 rounded-full text-sm">
                    <span>📦</span>
                    <span>{currentPackage.recipientName}</span>
                    {currentPackage.businessName && (
                      <span className="text-blue-300">@ {currentPackage.businessName}</span>
                    )}
                  </div>
                )}
              </div>

              <PhaserGame
                floor={agentFloor}
                side={agentSide}
                isThinking={isThinking && !isAnimating}
                packageText={currentPackage ? `${currentPackage.recipientName}${currentPackage.businessName ? ` @ ${currentPackage.businessName}` : ''}` : ''}
                deliverySuccess={deliveryStatus === 'success'}
                deliveryFailed={deliveryStatus === 'failed'}
                lastActionTool={actions.length > 0 ? actions[actions.length - 1].toolName : undefined}
              />

              {/* Status Bar */}
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-700">
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-slate-500">
                    Position: <span className="text-white font-mono">F{agentFloor} {agentSide}</span>
                  </span>
                  {deliveryStatus === 'running' && (
                    <span className="text-blue-400">
                      Step: <span className="font-mono">{deliverySteps}</span>
                    </span>
                  )}
                </div>
                <span className={`px-3 py-1 rounded-full text-xs font-medium uppercase tracking-wider ${
                  deliveryStatus === 'idle' ? 'bg-slate-600/50 text-slate-400' :
                  deliveryStatus === 'running' ? 'bg-blue-600/50 text-blue-300' :
                  deliveryStatus === 'success' ? 'bg-green-600/50 text-green-300' :
                  'bg-red-600/50 text-red-300'
                }`}>
                  {deliveryStatus}
                </span>
              </div>

              {/* Thinking Indicator */}
              {isThinking && !isAnimating && (
                <div className="mt-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
                  <div className="flex items-center gap-2 text-yellow-400 text-sm">
                    <div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse" />
                    <span className="font-medium">Agent is thinking...</span>
                  </div>
                  {thinkingText && (
                    <p className="text-yellow-300/80 text-xs mt-2 italic line-clamp-2">
                      {thinkingText}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Learning Curve Chart */}
            <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-slate-300">Learning Curve</h2>
                <span className="text-xs text-slate-500">
                  Avg: <span className="text-white font-mono">{avgSteps}</span> steps/delivery
                </span>
              </div>
              {history.length < 2 ? (
                <div className="h-32 flex items-center justify-center text-slate-500 text-sm">
                  Complete at least 2 deliveries to see learning progress
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={150}>
                  <LineChart data={chartData}>
                    <XAxis
                      dataKey="delivery"
                      stroke="#64748b"
                      fontSize={10}
                      tickLine={false}
                    />
                    <YAxis
                      stroke="#64748b"
                      fontSize={10}
                      tickLine={false}
                      domain={[0, 'auto']}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1e293b',
                        border: '1px solid #475569',
                        borderRadius: '8px',
                        fontSize: '12px',
                      }}
                      formatter={(value, name, props) => [
                        value ?? 0,
                        name === 'steps' ? (props.payload.success ? 'Steps (Success)' : 'Steps (Failed)') : 'Optimal'
                      ]}
                    />
                    <ReferenceLine y={3} stroke="#4ade80" strokeDasharray="3 3" label={{ value: 'Optimal', fill: '#4ade80', fontSize: 10 }} />
                    <Line
                      type="monotone"
                      dataKey="steps"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={(props) => {
                        const { cx, cy, payload } = props;
                        return (
                          <circle
                            cx={cx}
                            cy={cy}
                            r={4}
                            fill={payload.success ? '#3b82f6' : '#ef4444'}
                            stroke={payload.success ? '#3b82f6' : '#ef4444'}
                            strokeWidth={0}
                          />
                        );
                      }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Right Column - Controls & Logs */}
          <div className="space-y-4">
            {/* Controls */}
            <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
              <h2 className="text-lg font-semibold text-slate-300 mb-4">Controls</h2>

              {/* Recipient Select */}
              <div className="mb-4">
                <label className="block text-xs text-slate-500 uppercase tracking-wider mb-2">
                  Recipient
                </label>
                <select
                  value={selectedRecipient}
                  onChange={(e) => setSelectedRecipient(e.target.value)}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2.5 text-white focus:border-blue-500 focus:outline-none transition-colors"
                  disabled={deliveryStatus === 'running'}
                >
                  <option value="">Choose a recipient...</option>
                  {employees.map(emp => (
                    <option key={emp.name} value={emp.name}>
                      F{emp.floor} {emp.side} | {emp.business} | {emp.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Options */}
              <div className="mb-4 space-y-3">
                <label className="flex items-center gap-3 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={includeBusiness}
                    onChange={(e) => setIncludeBusiness(e.target.checked)}
                    className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
                  />
                  <span className="text-sm text-slate-400 group-hover:text-slate-300 transition-colors">
                    Include business name in prompt
                  </span>
                </label>

                <div>
                  <label className="block text-xs text-slate-500 uppercase tracking-wider mb-2">
                    Max Steps (optional)
                  </label>
                  <input
                    type="number"
                    value={maxSteps ?? ''}
                    onChange={(e) => setMaxSteps(e.target.value ? parseInt(e.target.value) : null)}
                    placeholder="No limit"
                    min={1}
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none transition-colors"
                  />
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2">
                <button
                  onClick={handleStartDelivery}
                  disabled={!connected || !selectedRecipient || deliveryStatus === 'running'}
                  className="flex-1 bg-gradient-to-r from-green-600 to-green-500 hover:from-green-500 hover:to-green-400 disabled:from-slate-600 disabled:to-slate-600 disabled:cursor-not-allowed px-4 py-2.5 rounded-lg font-medium transition-all shadow-lg shadow-green-500/20 disabled:shadow-none"
                >
                  {deliveryStatus === 'running' ? 'Running...' : 'Start Delivery'}
                </button>
                <button
                  onClick={cancelDelivery}
                  disabled={deliveryStatus !== 'running'}
                  className="bg-red-600/80 hover:bg-red-600 disabled:bg-slate-600/50 disabled:cursor-not-allowed px-4 py-2.5 rounded-lg font-medium transition-colors"
                >
                  Stop
                </button>
              </div>

              {/* Random Delivery Button */}
              <button
                onClick={handleRandomDelivery}
                disabled={!connected || deliveryStatus === 'running' || employees.length === 0}
                className="w-full mt-2 bg-gradient-to-r from-purple-600 to-blue-500 hover:from-purple-500 hover:to-blue-400 disabled:from-slate-600 disabled:to-slate-600 disabled:cursor-not-allowed px-4 py-2.5 rounded-lg font-medium transition-all shadow-lg shadow-purple-500/20 disabled:shadow-none"
              >
                Random Delivery
              </button>

              {/* Reset Memory */}
              <button
                onClick={handleResetMemory}
                disabled={deliveryStatus === 'running'}
                className="w-full mt-3 bg-slate-700/50 hover:bg-slate-700 border border-slate-600 text-slate-400 hover:text-slate-300 disabled:cursor-not-allowed px-4 py-2 rounded-lg text-sm transition-colors"
              >
                Reset Memory & History
              </button>
            </div>

            {/* Stats */}
            <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
              <h2 className="text-lg font-semibold text-slate-300 mb-4">Statistics</h2>
              <div className="grid grid-cols-3 gap-3">
                <div className="text-center p-3 bg-slate-700/30 rounded-lg">
                  <div className="text-2xl font-bold text-green-400">{deliveriesCompleted}</div>
                  <div className="text-xs text-slate-500 mt-1">Deliveries</div>
                </div>
                <div className="text-center p-3 bg-slate-700/30 rounded-lg">
                  <div className="text-2xl font-bold text-blue-400">{totalSteps}</div>
                  <div className="text-xs text-slate-500 mt-1">Total Steps</div>
                </div>
                <div className="text-center p-3 bg-slate-700/30 rounded-lg">
                  <div className="text-2xl font-bold text-yellow-400">
                    {history.length > 0 ? Math.round(history.filter(h => h.success).length / history.length * 100) : 0}%
                  </div>
                  <div className="text-xs text-slate-500 mt-1">Success</div>
                </div>
              </div>
            </div>

            {/* Action Log */}
            <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-slate-300">Action Log</h2>
                {actions.length > 0 && (
                  <span className="text-xs text-slate-500">{actions.length} actions</span>
                )}
              </div>
              <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                {actions.length === 0 ? (
                  <div className="text-center py-8 text-slate-500 text-sm">
                    <div className="text-2xl mb-2">📦</div>
                    Start a delivery to see agent actions
                  </div>
                ) : (
                  [...actions].reverse().map((action, i) => (
                    <ActionLogEntry
                      key={actions.length - 1 - i}
                      action={action}
                      expanded={expandedAction === actions.length - 1 - i}
                      onToggle={() => setExpandedAction(
                        expandedAction === actions.length - 1 - i ? null : actions.length - 1 - i
                      )}
                    />
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
