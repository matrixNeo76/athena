/**
 * SwotMatrix — 2x2 SWOT analysis grid with expandable items.
 */
import React, { useState } from 'react';
import type { SWOTModel } from '../types/athena';

interface QuadrantProps {
  title: string;
  icon: string;
  items: string[];
  colorClass: string;
  borderClass: string;
}

const Quadrant: React.FC<QuadrantProps> = ({ title, icon, items, colorClass, borderClass }) => {
  const [expanded, setExpanded] = useState(true);
  const visible = expanded ? items : items.slice(0, 3);

  return (
    <div className={`p-4 rounded-xl border ${borderClass} bg-gray-900/60`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between mb-3 group"
      >
        <span className={`flex items-center gap-2 font-bold text-sm ${colorClass}`}>
          <span className="text-lg">{icon}</span>
          {title}
        </span>
        <span className="text-gray-600 text-xs group-hover:text-gray-400">
          {expanded ? '▲' : '▼'} {items.length}
        </span>
      </button>

      <ul className="space-y-1.5">
        {visible.map((item, i) => (
          <li key={i} className="flex items-start gap-2 text-xs text-gray-300">
            <span className={`mt-0.5 flex-shrink-0 w-1.5 h-1.5 rounded-full ${colorClass.replace('text-', 'bg-')}`} />
            <span>{item}</span>
          </li>
        ))}
      </ul>

      {!expanded && items.length > 3 && (
        <button
          onClick={() => setExpanded(true)}
          className="mt-2 text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          +{items.length - 3} more
        </button>
      )}
    </div>
  );
};

interface SwotMatrixProps {
  swot: SWOTModel;
}

export const SwotMatrix: React.FC<SwotMatrixProps> = ({ swot }) => {
  const quadrants = [
    {
      title: 'Strengths',
      icon: '💪',
      items: swot.strengths ?? [],
      colorClass: 'text-green-400',
      borderClass: 'border-green-700/40',
    },
    {
      title: 'Weaknesses',
      icon: '⚠️',
      items: swot.weaknesses ?? [],
      colorClass: 'text-yellow-400',
      borderClass: 'border-yellow-700/40',
    },
    {
      title: 'Opportunities',
      icon: '🚀',
      items: swot.opportunities ?? [],
      colorClass: 'text-blue-400',
      borderClass: 'border-blue-700/40',
    },
    {
      title: 'Threats',
      icon: '🛡️',
      items: swot.threats ?? [],
      colorClass: 'text-red-400',
      borderClass: 'border-red-700/40',
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4">
      {quadrants.map((q) => (
        <Quadrant key={q.title} {...q} />
      ))}
    </div>
  );
};

export default SwotMatrix;
