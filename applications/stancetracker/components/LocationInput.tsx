'use client';

import { useState, useEffect } from 'react';
import { Location } from '@/types';

interface LocationInputProps {
  value: Location;
  onChange: (location: Location) => void;
}

export default function LocationInput({ value, onChange }: LocationInputProps) {
  const [country, setCountry] = useState(value.country || '');
  const [state, setState] = useState(value.state || '');
  const [city, setCity] = useState(value.city || '');

  // Sync internal state when value prop changes
  useEffect(() => {
    setCountry(value.country || '');
    setState(value.state || '');
    setCity(value.city || '');
  }, [value]);

  const handleChange = (field: keyof Location, newValue: string) => {
    const updated = { ...value, [field]: newValue };

    if (field === 'country') setCountry(newValue);
    if (field === 'state') setState(newValue);
    if (field === 'city') setCity(newValue);

    onChange(updated);
  };

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">Geographic Location</h3>

      <div>
        <label htmlFor="country" className="block text-sm font-medium mb-1 text-gray-900">
          Country *
        </label>
        <input
          id="country"
          type="text"
          value={country}
          onChange={(e) => handleChange('country', e.target.value)}
          placeholder="e.g., United States"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
          required
        />
      </div>

      <div>
        <label htmlFor="state" className="block text-sm font-medium mb-1 text-gray-900">
          State/Province/Territory
        </label>
        <input
          id="state"
          type="text"
          value={state}
          onChange={(e) => handleChange('state', e.target.value)}
          placeholder="e.g., California"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
        />
      </div>

      <div>
        <label htmlFor="city" className="block text-sm font-medium mb-1 text-gray-900">
          City
        </label>
        <input
          id="city"
          type="text"
          value={city}
          onChange={(e) => handleChange('city', e.target.value)}
          placeholder="e.g., San Francisco"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
        />
      </div>
    </div>
  );
}
