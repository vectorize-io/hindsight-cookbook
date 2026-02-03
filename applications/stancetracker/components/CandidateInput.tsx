'use client';

import { useState } from 'react';
import { X, Plus } from 'lucide-react';

interface CandidateInputProps {
  candidates: string[];
  onChange: (candidates: string[]) => void;
}

export default function CandidateInput({ candidates, onChange }: CandidateInputProps) {
  const [inputValue, setInputValue] = useState('');

  const addCandidate = () => {
    if (inputValue.trim() && !candidates.includes(inputValue.trim())) {
      onChange([...candidates, inputValue.trim()]);
      setInputValue('');
    }
  };

  const removeCandidate = (index: number) => {
    onChange(candidates.filter((_, i) => i !== index));
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addCandidate();
    }
  };

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">Candidates to Track</h3>

      <div className="flex gap-2">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Enter candidate name"
          className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
        />
        <button
          type="button"
          onClick={addCandidate}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 flex items-center gap-2"
        >
          <Plus size={18} />
          Add
        </button>
      </div>

      {candidates.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm text-gray-900">Tracking {candidates.length} candidate{candidates.length !== 1 ? 's' : ''}:</p>
          <div className="flex flex-wrap gap-2">
            {candidates.map((candidate, index) => (
              <div
                key={index}
                className="flex items-center gap-2 px-3 py-1 bg-blue-100 text-blue-800 rounded-full"
              >
                <span>{candidate}</span>
                <button
                  type="button"
                  onClick={() => removeCandidate(index)}
                  className="hover:bg-blue-200 rounded-full p-1"
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {candidates.length === 0 && (
        <p className="text-sm text-gray-900 italic">No candidates added yet</p>
      )}
    </div>
  );
}
