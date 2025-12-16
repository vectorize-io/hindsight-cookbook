'use client';

import { FrequencyType } from '@/types';

interface TimeSettingsProps {
  timespan: {
    start: string;
    end: string;
  };
  frequency: FrequencyType;
  onTimespanChange: (timespan: { start: string; end: string }) => void;
  onFrequencyChange: (frequency: FrequencyType) => void;
}

export default function TimeSettings({
  timespan,
  frequency,
  onTimespanChange,
  onFrequencyChange,
}: TimeSettingsProps) {
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">Time Settings</h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label htmlFor="start-date" className="block text-sm font-medium mb-1 text-gray-900">
            Historical Start Date *
          </label>
          <input
            id="start-date"
            type="date"
            value={timespan.start}
            onChange={(e) => onTimespanChange({ ...timespan, start: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
            required
          />
        </div>

        <div>
          <label htmlFor="end-date" className="block text-sm font-medium mb-1 text-gray-900">
            End Date *
          </label>
          <input
            id="end-date"
            type="date"
            value={timespan.end}
            onChange={(e) => onTimespanChange({ ...timespan, end: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
            required
          />
        </div>
      </div>

      <div>
        <label htmlFor="frequency" className="block text-sm font-medium mb-1 text-gray-900">
          Update Frequency *
        </label>
        <select
          id="frequency"
          value={frequency}
          onChange={(e) => onFrequencyChange(e.target.value as FrequencyType)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
        >
          <option value="hourly">Hourly</option>
          <option value="daily">Daily</option>
          <option value="weekly">Weekly</option>
        </select>
        <p className="mt-1 text-sm text-gray-900">
          How often should we check for new information?
        </p>
      </div>
    </div>
  );
}
