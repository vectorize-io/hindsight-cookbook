'use client';

interface TopicInputProps {
  value: string;
  onChange: (topic: string) => void;
}

export default function TopicInput({ value, onChange }: TopicInputProps) {
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">Issue/Topic</h3>

      <div>
        <label htmlFor="topic" className="block text-sm font-medium mb-1 text-gray-900">
          What issue would you like to track? *
        </label>
        <input
          id="topic"
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="e.g., Climate Change, Healthcare Reform, Education Policy"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
          required
        />
        <p className="mt-1 text-sm text-gray-900">
          Be specific for better tracking results
        </p>
      </div>
    </div>
  );
}
