'use client';

import { useState, useEffect } from 'react';
import LocationInput from '@/components/LocationInput';
import CandidateInput from '@/components/CandidateInput';
import TopicInput from '@/components/TopicInput';
import TimeSettings from '@/components/TimeSettings';
import StanceTimeline from '@/components/StanceTimeline';
import { Location, FrequencyType, TimelineData, TrackingSession } from '@/types';
import { Play, Pause, RefreshCw, ChevronDown, Save, Trash2, Plus } from 'lucide-react';

interface Session {
  id: string;
  name: string;
  created_at: string;
  country: string;
  state?: string;
  city?: string;
  topic: string;
  candidates: string[];
  frequency: 'hourly' | 'daily' | 'weekly';
  status: 'active' | 'paused' | 'completed';
  timespan_start: string;
  timespan_end: string;
}

export default function Home() {
  const [trackerName, setTrackerName] = useState('');
  const [location, setLocation] = useState<Location>({
    country: '',
    state: '',
    city: '',
  });
  const [topic, setTopic] = useState('');
  const [candidates, setCandidates] = useState<string[]>([]);
  const [timespan, setTimespan] = useState({
    start: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    end: new Date().toISOString().split('T')[0],
  });
  const [frequency, setFrequency] = useState<FrequencyType>('daily');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [timelineData, setTimelineData] = useState<TimelineData[]>([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<'idle' | 'active' | 'paused'>('idle');
  const [message, setMessage] = useState<string>('');
  const [existingSessions, setExistingSessions] = useState<Session[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [showSessionDropdown, setShowSessionDropdown] = useState(false);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [processingStatus, setProcessingStatus] = useState<{
    isProcessing: boolean;
    currentCandidate: string;
    currentIndex: number;
    total: number;
  } | null>(null);

  const showMessage = (msg: string, duration = 3000) => {
    setMessage(msg);
    setTimeout(() => setMessage(''), duration);
  };

  useEffect(() => {
    fetchExistingSessions();
  }, []);

  const fetchExistingSessions = async () => {
    try {
      setSessionsLoading(true);
      const response = await fetch('/api/sessions');
      if (!response.ok) throw new Error('Failed to fetch sessions');

      const data = await response.json();
      setExistingSessions(data.sessions || []);
    } catch (error) {
      console.error('Error fetching sessions:', error);
      setExistingSessions([]);
    } finally {
      setSessionsLoading(false);
    }
  };

  const autoSaveCurrentSession = async () => {
    if (!sessionId) {
      console.log('Auto-save skipped: no session loaded');
      return;
    }

    // Only validate critical fields - allow partial saves for candidate updates
    if (!trackerName || !topic) {
      console.log('Auto-save skipped: missing tracker name or topic');
      return;
    }

    console.log('Auto-saving session...', { sessionId, candidates: candidates.length });

    try {
      console.log('>>> Sending PATCH request to /api/sessions');
      const response = await fetch('/api/sessions', {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache',
        },
        cache: 'no-store',
        body: JSON.stringify({
          id: sessionId,
          name: trackerName,
          country: location.country,
          state: location.state,
          city: location.city,
          topic,
          candidates,
          timespanStart: timespan.start,
          timespanEnd: timespan.end,
          frequency,
        }),
      });

      console.log('<<< Received response:', response.status, response.statusText);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        console.error('Auto-save failed with status', response.status, ':', errorData);
      } else {
        console.log('Auto-saved session before switching');
        // Refresh the sessions list to get the updated data from the database
        await fetchExistingSessions();
        console.log('Refreshed sessions list after auto-save');
      }
    } catch (error) {
      console.error('Auto-save failed:', error);
    }
  };

  const loadSessionData = async (session: Session) => {
    try {
      console.log('=== SWITCHING SESSIONS ===');
      console.log('Current session before switch:', { sessionId, candidates });
      console.log('Target session:', { id: session.id, name: session.name, candidates: session.candidates });

      // Auto-save the current session before switching to a new one
      await autoSaveCurrentSession();

      console.log('Auto-save completed, now loading new session');

      const sessionCandidates = Array.isArray(session.candidates) ? session.candidates : [];

      setSessionId(session.id);
      setTrackerName(session.name);
      setLocation({
        country: session.country,
        state: session.state || '',
        city: session.city || '',
      });
      setTopic(session.topic);
      setCandidates(sessionCandidates);
      setFrequency(session.frequency);
      setStatus(session.status as 'active' | 'paused');
      setTimespan({
        start: session.timespan_start.split('T')[0],
        end: session.timespan_end.split('T')[0],
      });
      setSelectedSessionId(session.id);
      setShowSessionDropdown(false);

      // Fetch stances for this session using the session's candidates
      await fetchStances(session.id, sessionCandidates);
      showMessage(`Loaded session: ${session.name}`);
    } catch (error) {
      console.error('Error loading session:', error);
      showMessage('Failed to load session');
    }
  };

  const createSession = async () => {
    if (!trackerName || !location.country || !topic || candidates.length === 0) {
      showMessage('Please fill in all required fields including tracker name');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: trackerName,
          country: location.country,
          state: location.state,
          city: location.city,
          topic,
          candidates,
          timespanStart: timespan.start,
          timespanEnd: timespan.end,
          frequency,
        }),
      });

      if (!response.ok) throw new Error('Failed to create session');

      const data = await response.json();
      const session = data.session;
      setSessionId(session.id);
      setSelectedSessionId(session.id);
      setStatus('active');
      showMessage('Tracking session created successfully!');

      // Refresh sessions list
      await fetchExistingSessions();

      // Schedule the session
      await fetch('/api/scheduler', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'start',
          sessionId: session.id,
          frequency,
        }),
      });

      // Trigger initial run
      runTracking(session.id);
    } catch (error) {
      console.error('Error creating session:', error);
      showMessage('Failed to create session');
    } finally {
      setLoading(false);
    }
  };

  const runTracking = async (sid?: string) => {
    const targetSessionId = sid || sessionId;
    if (!targetSessionId) return;

    setLoading(true);
    const totalCandidates = candidates.length;

    try {
      // Process each candidate
      for (let i = 0; i < candidates.length; i++) {
        const candidate = candidates[i];

        // Update processing status
        setProcessingStatus({
          isProcessing: true,
          currentCandidate: candidate,
          currentIndex: i + 1,
          total: totalCandidates,
        });

        await fetch('/api/stances', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            sessionId: targetSessionId,
            candidate,
            topic,
            location,
            timeRange: {
              start: new Date(timespan.start),
              end: new Date(timespan.end),
            },
          }),
        });
      }

      // Fetch updated stances
      await fetchStances(targetSessionId);
      showMessage('Tracking completed!', 3000);

      // Clear processing status after a brief delay
      setTimeout(() => setProcessingStatus(null), 2000);
    } catch (error) {
      console.error('Error running tracking:', error);
      showMessage('Failed to run tracking');
      setProcessingStatus(null);
    } finally {
      setLoading(false);
    }
  };

  const fetchStances = async (sid: string, candidatesList?: string[]) => {
    try {
      const response = await fetch(`/api/stances?sessionId=${sid}`);
      if (!response.ok) throw new Error('Failed to fetch stances');

      const data = await response.json();

      // Use provided candidates list or fall back to state
      const candidatesToUse = candidatesList || candidates;

      // Group stances by candidate
      const grouped = candidatesToUse.map((candidate) => ({
        candidate,
        points: data.stances.filter((s: any) => s.candidate === candidate),
      }));

      setTimelineData(grouped);
    } catch (error) {
      console.error('Error fetching stances:', error);
    }
  };

  const toggleStatus = async () => {
    if (!sessionId) return;

    const newStatus = status === 'active' ? 'paused' : 'active';

    try {
      await fetch('/api/sessions', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: sessionId, status: newStatus }),
      });

      if (newStatus === 'paused') {
        await fetch('/api/scheduler', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'stop', sessionId }),
        });
      } else {
        await fetch('/api/scheduler', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'start', sessionId, frequency }),
        });
      }

      setStatus(newStatus);
      showMessage(`Tracking ${newStatus === 'active' ? 'resumed' : 'paused'}`);
    } catch (error) {
      console.error('Error toggling status:', error);
      showMessage('Failed to update status');
    }
  };

  const saveSession = async () => {
    if (!sessionId) return;

    setLoading(true);
    try {
      const response = await fetch('/api/sessions', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: sessionId,
          name: trackerName,
          country: location.country,
          state: location.state,
          city: location.city,
          topic,
          candidates,
          timespanStart: timespan.start,
          timespanEnd: timespan.end,
          frequency,
        }),
      });

      if (!response.ok) throw new Error('Failed to update session');

      showMessage('Session saved successfully!');
      await fetchExistingSessions();
    } catch (error) {
      console.error('Error saving session:', error);
      showMessage('Failed to save session');
    } finally {
      setLoading(false);
    }
  };

  const deleteSession = async () => {
    if (!sessionId) return;

    const confirmed = confirm('Are you sure you want to delete this tracking session? This action cannot be undone.');
    if (!confirmed) return;

    setLoading(true);
    try {
      const response = await fetch(`/api/sessions?id=${sessionId}`, {
        method: 'DELETE',
      });

      if (!response.ok) throw new Error('Failed to delete session');

      showMessage('Session deleted successfully');

      // Reset form
      setSessionId(null);
      setSelectedSessionId(null);
      setTrackerName('');
      setLocation({ country: '', state: '', city: '' });
      setTopic('');
      setCandidates([]);
      setTimelineData([]);
      setStatus('idle');

      await fetchExistingSessions();
    } catch (error) {
      console.error('Error deleting session:', error);
      showMessage('Failed to delete session');
    } finally {
      setLoading(false);
    }
  };

  const createNewSession = async () => {
    // Auto-save the current session before creating a new one
    await autoSaveCurrentSession();

    // Reset form to create a new session
    setSessionId(null);
    setSelectedSessionId(null);
    setTrackerName('');
    setLocation({ country: '', state: '', city: '' });
    setTopic('');
    setCandidates([]);
    setTimelineData([]);
    setStatus('idle');
    setTimespan({
      start: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      end: new Date().toISOString().split('T')[0],
    });

    showMessage('Ready to create a new tracking session');
  };

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <header className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900">Stance Tracker</h1>
          <p className="text-gray-900 mt-2">
            Track candidate positions on issues over time using AI-powered memory
          </p>
        </header>

        {message && (
          <div className="mb-4 p-4 bg-blue-100 border border-blue-300 text-blue-800 rounded-lg">
            {message}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow p-6 space-y-6">
              {/* Tracker Name Input */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Tracker Name
                </label>
                <input
                  type="text"
                  value={trackerName}
                  onChange={(e) => setTrackerName(e.target.value)}
                  placeholder="e.g., Presidential Climate Stance 2024"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <hr />

              {/* Session Selector */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Load Existing Session
                </label>
                <div className="relative">
                  <button
                    onClick={() => setShowSessionDropdown(!showSessionDropdown)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg flex items-center justify-between hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <span className="text-gray-700">
                      {selectedSessionId
                        ? existingSessions.find((s) => s.id === selectedSessionId)?.name ||
                          'Select a session'
                        : sessionsLoading
                        ? 'Loading sessions...'
                        : existingSessions.length > 0
                        ? 'Select a session'
                        : 'No sessions found'}
                    </span>
                    <ChevronDown size={18} className="text-gray-400" />
                  </button>

                  {showSessionDropdown && (
                    <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-300 rounded-lg shadow-lg z-10">
                      {sessionsLoading ? (
                        <div className="p-3 text-center text-gray-500 text-sm">
                          Loading sessions...
                        </div>
                      ) : existingSessions.length > 0 ? (
                        <div className="max-h-64 overflow-y-auto">
                          {existingSessions.map((session) => (
                            <button
                              key={session.id}
                              onClick={() => loadSessionData(session)}
                              className="w-full text-left px-4 py-3 hover:bg-blue-50 border-b border-gray-100 last:border-b-0 focus:outline-none"
                            >
                              <div className="text-base font-bold text-gray-900 mb-1">
                                {session.name}
                              </div>
                              <div className="text-sm text-gray-700 mb-1">
                                {session.topic} • {session.candidates.join(', ')}
                              </div>
                              <div className="text-xs text-gray-500">
                                {session.country}{session.state ? `, ${session.state}` : ''}{session.city ? `, ${session.city}` : ''}
                              </div>
                              <div className="text-xs text-gray-500 mt-1 flex items-center gap-3">
                                <span>Created: {new Date(session.created_at).toLocaleDateString()}</span>
                                <span>•</span>
                                <span className="capitalize">
                                  Status: <span className={`font-semibold ${session.status === 'active' ? 'text-green-600' : session.status === 'paused' ? 'text-yellow-600' : 'text-gray-600'}`}>{session.status}</span>
                                </span>
                              </div>
                            </button>
                          ))}
                        </div>
                      ) : (
                        <div className="p-3 text-center text-gray-500 text-sm">
                          No sessions available
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* New Session Button - shown when a session is loaded */}
              {sessionId && (
                <button
                  onClick={createNewSession}
                  disabled={loading}
                  className="w-full px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300 font-medium flex items-center justify-center gap-2 border-2 border-green-700"
                >
                  <Plus size={18} />
                  Create New Session
                </button>
              )}

              <hr />

              <LocationInput value={location} onChange={setLocation} />
              <hr />
              <TopicInput value={topic} onChange={setTopic} />
              <hr />
              <CandidateInput candidates={candidates} onChange={setCandidates} />
              <hr />
              <TimeSettings
                timespan={timespan}
                frequency={frequency}
                onTimespanChange={setTimespan}
                onFrequencyChange={setFrequency}
              />
              <div className="pt-4 space-y-3">
                {!sessionId ? (
                  <button
                    onClick={createSession}
                    disabled={loading || !location.country || !topic || candidates.length === 0}
                    className="w-full px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium flex items-center justify-center gap-2"
                  >
                    <Play size={20} />
                    Start Tracking
                  </button>
                ) : (
                  <div className="space-y-3">
                    <button
                      onClick={saveSession}
                      disabled={loading}
                      className="w-full px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 font-medium flex items-center justify-center gap-2"
                    >
                      <Save size={18} />
                      Save Changes
                    </button>

                    <div className="flex gap-2">
                      <button
                        onClick={toggleStatus}
                        disabled={loading}
                        className="flex-1 px-4 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:bg-gray-300 font-medium flex items-center justify-center gap-2"
                      >
                        {status === 'active' ? (
                          <>
                            <Pause size={18} />
                            Pause
                          </>
                        ) : (
                          <>
                            <Play size={18} />
                            Resume
                          </>
                        )}
                      </button>
                      <button
                        onClick={() => runTracking()}
                        disabled={loading}
                        className="flex-1 px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300 font-medium flex items-center justify-center gap-2"
                      >
                        <RefreshCw size={18} />
                        Run Now
                      </button>
                    </div>

                    <button
                      onClick={deleteSession}
                      disabled={loading}
                      className="w-full px-4 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:bg-gray-300 font-medium flex items-center justify-center gap-2"
                    >
                      <Trash2 size={18} />
                      Delete Session
                    </button>

                    <div className="text-center text-sm text-gray-900">
                      Status: <span className="font-semibold capitalize">{status}</span>
                      <br />
                      Frequency: <span className="font-semibold capitalize">{frequency}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="lg:col-span-2">
            {/* Processing Status Bar */}
            {processingStatus && processingStatus.isProcessing && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg shadow-sm p-4 mb-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900">
                        Processing Candidate {processingStatus.currentIndex} of {processingStatus.total}
                      </p>
                      <p className="text-sm text-gray-600">
                        Analyzing: <span className="font-medium">{processingStatus.currentCandidate}</span>
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-gray-500">
                      {Math.round((processingStatus.currentIndex / processingStatus.total) * 100)}% complete
                    </p>
                  </div>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                    style={{ width: `${(processingStatus.currentIndex / processingStatus.total) * 100}%` }}
                  ></div>
                </div>
              </div>
            )}

            {loading && !timelineData.length ? (
              <div className="bg-white rounded-lg shadow p-8">
                <div className="text-center">
                  <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
                  <p className="mt-4 text-gray-600">Processing stance data...</p>
                </div>
              </div>
            ) : timelineData.length > 0 ? (
              <StanceTimeline data={timelineData} />
            ) : (
              <div className="bg-white rounded-lg shadow p-8">
                <div className="text-center text-gray-900">
                  <p className="text-lg font-medium">No data yet</p>
                  <p className="mt-2">
                    Configure your tracking settings and click "Start Tracking" to begin.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        <footer className="mt-12 pt-6 border-t border-gray-200">
          <div className="text-sm text-gray-900 space-y-2">
            <p>
              <strong>Powered by:</strong> Hindsight memory system and AI stance extraction
            </p>
            <p>
              This application demonstrates advanced memory capabilities including entity resolution,
              temporal search, and opinion tracking.
            </p>
          </div>
        </footer>
      </div>
    </main>
  );
}
