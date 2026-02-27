/**
 * InputForm — ATHENA analysis request form.
 * Collects target, analysis type, and depth; POSTs to /api/v1/analysis/start.
 */
import React, { useState, FormEvent } from 'react';
import { startAnalysis } from '../lib/api';
import type { AnalysisType } from '../types/athena';

interface InputFormProps {
  /** Called with the new job_id after successful submission. */
  onJobCreated: (jobId: string) => void;
  /** Disable the form while a job is running. */
  disabled?: boolean;
}

const ANALYSIS_TYPES: { value: AnalysisType; label: string; icon: string }[] = [
  { value: 'company',  label: 'Company',       icon: '🏢' },
  { value: 'product',  label: 'Product',        icon: '📦' },
  { value: 'market',   label: 'Market Segment', icon: '🌍' },
];

const DEPTH_OPTIONS = [
  { value: 'quick',    label: 'Quick  (~30s)',  desc: 'Fast overview' },
  { value: 'standard', label: 'Standard (~2m)', desc: 'Balanced analysis' },
  { value: 'deep',     label: 'Deep   (~5m)',   desc: 'Full LATS search' },
];

export const InputForm: React.FC<InputFormProps> = ({ onJobCreated, disabled = false }) => {
  const [target, setTarget]           = useState('');
  const [type, setType]               = useState<AnalysisType>('company');
  const [depth, setDepth]             = useState<'quick' | 'standard' | 'deep'>('standard');
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!target.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await startAnalysis({ target: target.trim(), target_type: type, depth });
      onJobCreated(res.job_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to start analysis.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl mx-auto">
      {/* Target input */}
      <div className="mb-6">
        <label className="block text-sm font-semibold text-gray-300 mb-2">
          Target Name
        </label>
        <input
          type="text"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          placeholder="e.g. OpenAI, Stripe, AI SaaS market..."
          disabled={disabled || loading}
          required
          className={`w-full px-4 py-3 rounded-xl border text-white placeholder-gray-500
            bg-gray-900 border-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500
            transition-all duration-200 text-base
            ${(disabled || loading) ? 'opacity-50 cursor-not-allowed' : ''}`}
        />
      </div>

      {/* Analysis type */}
      <div className="mb-6">
        <label className="block text-sm font-semibold text-gray-300 mb-2">
          Analysis Type
        </label>
        <div className="grid grid-cols-3 gap-3">
          {ANALYSIS_TYPES.map(({ value, label, icon }) => (
            <button
              key={value}
              type="button"
              onClick={() => setType(value)}
              disabled={disabled || loading}
              className={`py-3 px-4 rounded-xl border text-sm font-medium transition-all duration-200
                flex flex-col items-center gap-1
                ${type === value
                  ? 'bg-indigo-600 border-indigo-500 text-white'
                  : 'bg-gray-900 border-gray-700 text-gray-400 hover:border-indigo-500 hover:text-white'}
                ${(disabled || loading) ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              <span className="text-xl">{icon}</span>
              <span>{label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Depth */}
      <div className="mb-8">
        <label className="block text-sm font-semibold text-gray-300 mb-2">
          Analysis Depth
        </label>
        <div className="grid grid-cols-3 gap-3">
          {DEPTH_OPTIONS.map(({ value, label, desc }) => (
            <button
              key={value}
              type="button"
              onClick={() => setDepth(value as typeof depth)}
              disabled={disabled || loading}
              className={`py-3 px-4 rounded-xl border text-sm transition-all duration-200
                flex flex-col items-start gap-0.5
                ${depth === value
                  ? 'bg-indigo-600 border-indigo-500 text-white'
                  : 'bg-gray-900 border-gray-700 text-gray-400 hover:border-indigo-500 hover:text-white'}
                ${(disabled || loading) ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              <span className="font-semibold">{label}</span>
              <span className="text-xs opacity-70">{desc}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-900/40 border border-red-500/40 text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={disabled || loading || !target.trim()}
        className={`w-full py-4 rounded-xl font-bold text-lg transition-all duration-200
          bg-gradient-to-r from-indigo-600 to-purple-600
          hover:from-indigo-500 hover:to-purple-500
          disabled:opacity-50 disabled:cursor-not-allowed
          text-white shadow-lg shadow-indigo-500/25`}
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white
              rounded-full animate-spin" />
            Starting Analysis...
          </span>
        ) : (
          <span>Analyse with ATHENA ⚡</span>
        )}
      </button>
    </form>
  );
};

export default InputForm;
