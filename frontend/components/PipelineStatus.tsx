/**
 * PipelineStatus — real-time ATHENA pipeline progress tracker.
 * Renders a vertical stepper with live WebSocket-driven state updates.
 */
import React from 'react';
import type { PipelineStage } from '../types/athena';

interface Stage {
  id: PipelineStage;
  label: string;
  icon: string;
  description: string;
}

const STAGES: Stage[] = [
  { id: 'SCOUT',     label: 'Scout Agent',    icon: '🔍', description: 'Gathering market intelligence' },
  { id: 'ANALYST',   label: 'Analyst',        icon: '📊', description: 'Structuring insights' },
  { id: 'STRATEGY',  label: 'Strategy Agent', icon: '♟️', description: 'Generating strategic analysis' },
  { id: 'PRESENTER', label: 'Presenter',      icon: '🎭', description: 'Producing reports & deck' },
];

type StageStatus = 'pending' | 'active' | 'done' | 'error';

function getStageStatus(stageId: PipelineStage, current: PipelineStage): StageStatus {
  const order: PipelineStage[] = ['PENDING', 'SCOUT', 'ANALYST', 'STRATEGY', 'PRESENTER', 'DONE'];
  const currentIdx = order.indexOf(current);
  const stageIdx   = order.indexOf(stageId);
  if (current === 'ERROR') return stageIdx < currentIdx ? 'error' : 'pending';
  if (stageIdx < currentIdx) return 'done';
  if (stageIdx === currentIdx) return 'active';
  return 'pending';
}

interface PipelineStatusProps {
  currentStage: PipelineStage;
  progress: number;          // 0–100
  message?: string;
  latsScores?: Record<string, number>;
}

export const PipelineStatus: React.FC<PipelineStatusProps> = ({
  currentStage,
  progress,
  message,
  latsScores = {},
}) => {
  return (
    <div className="w-full">
      {/* Progress bar */}
      <div className="mb-6">
        <div className="flex justify-between text-xs text-gray-400 mb-1">
          <span>{message || 'Processing...'}</span>
          <span>{progress}%</span>
        </div>
        <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-purple-500
              transition-all duration-700 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Stage stepper */}
      <div className="space-y-3">
        {STAGES.map((stage, idx) => {
          const status = getStageStatus(stage.id, currentStage);
          const latsScore = latsScores[stage.id.toLowerCase()];

          return (
            <div
              key={stage.id}
              className={`flex items-center gap-4 p-3 rounded-xl border transition-all duration-300
                ${
                  status === 'active'
                    ? 'bg-indigo-900/30 border-indigo-500/50'
                    : status === 'done'
                    ? 'bg-green-900/20 border-green-500/30'
                    : status === 'error'
                    ? 'bg-red-900/20 border-red-500/30'
                    : 'bg-gray-900/40 border-gray-700/40'
                }`}
            >
              {/* Icon */}
              <div
                className={`w-10 h-10 rounded-xl flex items-center justify-center text-xl flex-shrink-0
                  ${
                    status === 'active'
                      ? 'bg-indigo-600'
                      : status === 'done'
                      ? 'bg-green-700'
                      : status === 'error'
                      ? 'bg-red-700'
                      : 'bg-gray-800'
                  }`}
              >
                {status === 'done' ? '✅' : status === 'error' ? '❌' : stage.icon}
              </div>

              {/* Text */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span
                    className={`font-semibold text-sm
                      ${
                        status === 'active' ? 'text-indigo-300'
                        : status === 'done'  ? 'text-green-300'
                        : 'text-gray-500'
                      }`}
                  >
                    {stage.label}
                  </span>
                  {status === 'active' && (
                    <span className="flex gap-0.5">
                      {[0, 1, 2].map((i) => (
                        <span
                          key={i}
                          className="w-1 h-1 rounded-full bg-indigo-400 animate-bounce"
                          style={{ animationDelay: `${i * 150}ms` }}
                        />
                      ))}
                    </span>
                  )}
                  {/* LATS quality badge */}
                  {status === 'done' && latsScore !== undefined && (
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-mono
                        ${
                          latsScore >= 0.8 ? 'bg-green-800 text-green-200'
                          : latsScore >= 0.6 ? 'bg-yellow-800 text-yellow-200'
                          : 'bg-red-800 text-red-200'
                        }`}
                    >
                      LATS {(latsScore * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-500 truncate">{stage.description}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default PipelineStatus;
