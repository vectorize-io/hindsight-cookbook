'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';

interface Recipe {
  name: string;
  emoji: string;
  description?: string;
  healthScore: number;
  timeMinutes: number;
  ingredients: string[];
  instructions: string;
  tags: string[];
  mealType?: string;
  date?: string;
}

interface DashboardProps {
  username: string;
  onEatNow: () => void;
  onOpenPreferences: () => void;
  onViewRecipe: (recipe: Recipe) => void;
  onLogout: () => void;
  refreshKey: number;
}

interface GoalProgressData {
  insight: string;
}

interface Meal {
  id: string;
  name: string;
  type: string;
  date: string;
  emoji: string;
  description?: string;
  healthScore?: number;
  timeMinutes?: number;
  ingredients?: string[];
  instructions?: string;
  tags?: string[];
}

interface UserPreferences {
  language?: string;
  cuisines?: string[];
  dietary?: string[];
  goals?: string[];
  dislikes?: string[];
}

export default function Dashboard({ username, onEatNow, onOpenPreferences, onViewRecipe, onLogout, refreshKey }: DashboardProps) {
  const [goalProgress, setGoalProgress] = useState<GoalProgressData | null>(null);
  const [meals, setMeals] = useState<Meal[]>([]);
  const [preferences, setPreferences] = useState<UserPreferences>({});
  const [loading, setLoading] = useState(true);

  const loadDashboardData = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setLoading(true);
    }
    try {
      const res = await fetch(`/api/dashboard?username=${encodeURIComponent(username)}`);
      const data = await res.json();
      setGoalProgress(data.goalProgress);
      setMeals(data.meals);
      setPreferences(data.preferences || {});
    } catch (e) {
      console.error('Failed to load dashboard:', e);
    }
    if (showLoading) {
      setLoading(false);
    }
  }, [username]);

  useEffect(() => {
    // Initial load
    loadDashboardData(true);

    // Set up auto-refresh every 5 seconds (background refresh)
    const interval = setInterval(() => {
      loadDashboardData(false); // Don't show loading spinner
    }, 5000);

    return () => clearInterval(interval);
  }, [refreshKey, loadDashboardData]);

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    if (date.toDateString() === today.toDateString()) return 'Today';
    if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';
    return date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  };

  return (
    <div className="min-h-screen px-4 py-6 max-w-md mx-auto">
      {/* Header */}
      <header className="flex items-start justify-between mb-8">
        <div className="flex-1">
          <h1 className="text-3xl font-bold bg-gradient-to-r from-orange-500 to-rose-500 bg-clip-text text-transparent">
            Let me cook 👨‍🍳
          </h1>
          <p className="text-gray-500 text-sm mt-1">
            <span className="font-medium text-gray-700">{username}</span>'s personal food memory{' '}
            <button
              onClick={onLogout}
              className="text-gray-400 hover:text-gray-600 underline cursor-pointer"
            >
              (logout)
            </button>
          </p>
        </div>
        <button
          onClick={onOpenPreferences}
          className="w-10 h-10 flex items-center justify-center rounded-full bg-white shadow-sm border border-gray-100 hover:bg-gray-50 transition-colors"
          title="Preferences"
        >
          ⚙️
        </button>
      </header>

      {/* Preferences Hint */}
      {(preferences.cuisines?.length || preferences.dietary?.length || preferences.goals?.length) && (
        <div className="mb-6 p-3 bg-orange-50 border border-orange-100 rounded-lg">
          <div className="flex items-start gap-2">
            <span className="text-sm">💡</span>
            <div className="flex-1">
              <p className="text-xs text-gray-600">
                {preferences.cuisines?.length ? (
                  <span className="mr-2">
                    <strong>Cuisines:</strong> {preferences.cuisines.join(', ')}
                  </span>
                ) : null}
                {preferences.dietary?.length ? (
                  <span className="mr-2">
                    <strong>Diet:</strong> {preferences.dietary.join(', ')}
                  </span>
                ) : null}
                {preferences.goals?.length ? (
                  <span>
                    <strong>Goals:</strong> {preferences.goals.join(', ')}
                  </span>
                ) : null}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Goal Progress */}
      {loading ? (
        <div className="flex justify-center mb-8">
          <div className="w-8 h-8 border-4 border-orange-200 border-t-orange-500 rounded-full animate-spin" />
        </div>
      ) : goalProgress?.insight ? (
        <motion.div
          className="mb-8 p-5 bg-gradient-to-br from-orange-50 to-rose-50 rounded-2xl border border-orange-100"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <div className="flex items-start gap-3">
            <span className="text-2xl">🎯</span>
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-gray-800 mb-2">Your Progress</h3>
              <p className="text-gray-700 text-sm leading-relaxed whitespace-pre-line">
                {goalProgress.insight}
              </p>
            </div>
          </div>
        </motion.div>
      ) : meals.length > 0 ? (
        <motion.div
          className="mb-8 p-4 bg-gray-50 rounded-2xl border border-gray-100"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <div className="flex items-start gap-3">
            <span className="text-2xl">🔄</span>
            <p className="flex-1 text-gray-500 text-sm">
              Analyzing your progress...
            </p>
          </div>
        </motion.div>
      ) : (
        <motion.div
          className="mb-8 p-6 bg-gradient-to-br from-orange-50 to-rose-50 rounded-2xl border border-orange-100 text-center"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <span className="text-4xl block mb-2">🎯</span>
          <p className="text-gray-600 text-sm">
            Log your first meal to start tracking your progress towards your goals!
          </p>
        </motion.div>
      )}

      {/* Eat Now Button */}
      <motion.button
        onClick={onEatNow}
        className="w-full py-4 bg-gradient-to-r from-orange-500 to-rose-500 text-white text-xl font-semibold rounded-2xl shadow-lg shadow-orange-200 mb-8"
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
      >
        🍽️ Eat Now
      </motion.button>

      {/* Recent Meals Timeline */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Recent Meals</h2>
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-16 bg-gray-100 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : meals.length === 0 ? (
          <div className="text-center py-8 text-gray-400">
            <p className="text-4xl mb-2">🍽️</p>
            <p>No meals logged yet</p>
            <p className="text-sm">Tap "Eat Now" to get started!</p>
          </div>
        ) : (
          <div className="space-y-3">
            {meals.map((meal, idx) => (
              <motion.button
                key={meal.id}
                onClick={() => {
                  if (meal.ingredients && meal.instructions) {
                    onViewRecipe({
                      name: meal.name,
                      emoji: meal.emoji,
                      description: meal.description,
                      healthScore: meal.healthScore || 0,
                      timeMinutes: meal.timeMinutes || 0,
                      ingredients: meal.ingredients || [],
                      instructions: meal.instructions || '',
                      tags: meal.tags || [],
                      mealType: meal.type,
                      date: formatDate(meal.date),
                    });
                  }
                }}
                className="w-full flex items-center gap-4 p-4 bg-white rounded-xl shadow-sm border border-gray-100 hover:border-orange-200 hover:shadow-md transition-all text-left"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.1 }}
              >
                <span className="text-3xl">{meal.emoji}</span>
                <div className="flex-1">
                  <p className="font-medium text-gray-800">{meal.name}</p>
                  <p className="text-sm text-gray-400">
                    {meal.type.charAt(0).toUpperCase() + meal.type.slice(1)} • {formatDate(meal.date)}
                  </p>
                </div>
                {meal.instructions && (
                  <span className="text-gray-300">→</span>
                )}
              </motion.button>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="text-center text-xs text-gray-400 mt-8 pb-4">
        Powered by <span className="font-semibold">Hindsight</span> Memory
      </footer>
    </div>
  );
}
