/**
 * ResultsDashboard — tabbed view of ATHENA analysis results.
 * Tabs: Overview | SWOT | Positioning | GTM | Report | Deck
 */
import React, { useState } from 'react';
import type { ResultsResponse } from '../types/athena';
import { SwotMatrix } from './SwotMatrix';

type Tab = 'overview' | 'swot' | 'positioning' | 'gtm' | 'report' | 'deck';

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'overview',    label: 'Overview',    icon: '📋' },
  { id: 'swot',        label: 'SWOT',        icon: '🔲' },
  { id: 'positioning', label: 'Positioning', icon: '🎯' },
  { id: 'gtm',         label: 'GTM',         icon: '🚀' },
  { id: 'report',      label: 'Report',      icon: '📄' },
  { id: 'deck',        label: 'Deck',        icon: '🎞️' },
];

interface ResultsDashboardProps {
  results: ResultsResponse;
  target: string;
}

export const ResultsDashboard: React.FC<ResultsDashboardProps> = ({ results, target }) => {
  const [activeTab, setActiveTab] = useState<Tab>('overview');

  const strategy = results.strategy_result;
  const presenter = results.presenter_result;
  const scout = results.scout_result;

  return (
    <div className="w-full">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">{target}</h2>
          <p className="text-sm text-gray-400 mt-1">Analysis complete</p>
        </div>
        {presenter?.report_url && (
          <a
            href={presenter.report_url}
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500
              text-white text-sm font-semibold transition-colors"
          >
            Download Report
          </a>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 p-1 bg-gray-900 rounded-xl overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium
              whitespace-nowrap transition-all duration-200 flex-shrink-0
              ${
                activeTab === tab.id
                  ? 'bg-indigo-600 text-white'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800'
              }`}
          >
            <span>{tab.icon}</span> {tab.label}
          </button>
        ))}
      </div>

      {/* Tab panels */}
      <div className="min-h-[300px]">
        {/* Overview */}
        {activeTab === 'overview' && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            {[
              { label: 'Competitors', value: scout?.competitors?.length ?? 0, icon: '🏢' },
              { label: 'Trends',      value: scout?.market_trends?.length ?? 0, icon: '📈' },
              { label: 'Segments',    value: scout?.customer_segments?.length ?? 0, icon: '👥' },
              { label: 'Slides',      value: presenter?.deck_slides?.length ?? 0, icon: '🎞️' },
            ].map((stat) => (
              <div
                key={stat.label}
                className="p-4 rounded-xl bg-gray-900 border border-gray-700 text-center"
              >
                <div className="text-2xl mb-1">{stat.icon}</div>
                <div className="text-2xl font-bold text-white">{stat.value}</div>
                <div className="text-xs text-gray-400">{stat.label}</div>
              </div>
            ))}
          </div>
        )}

        {/* SWOT */}
        {activeTab === 'swot' && strategy?.swot && (
          <SwotMatrix swot={strategy.swot} />
        )}

        {/* Positioning */}
        {activeTab === 'positioning' && (
          <div className="space-y-4">
            {(strategy?.positioning_options ?? []).map((opt, i) => (
              <div key={i} className="p-4 rounded-xl bg-gray-900 border border-gray-700">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold text-white">{opt.name ?? `Option ${i + 1}`}</h4>
                  {opt.investment_level && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-900 text-indigo-300">
                      {opt.investment_level}
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-300">{opt.description}</p>
              </div>
            ))}
            {!strategy?.positioning_options?.length && (
              <p className="text-gray-500 text-sm">No positioning options available.</p>
            )}
          </div>
        )}

        {/* GTM */}
        {activeTab === 'gtm' && strategy?.gtm && (
          <div className="space-y-4">
            {strategy.gtm.next_steps?.map((step, i) => (
              <div key={i} className="flex gap-3 p-3 rounded-xl bg-gray-900 border border-gray-700">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-700 flex items-center
                  justify-center text-xs font-bold text-white">
                  {i + 1}
                </span>
                <p className="text-sm text-gray-300">{step}</p>
              </div>
            ))}
            {strategy.gtm.channels && (
              <div className="p-4 rounded-xl bg-gray-900 border border-gray-700">
                <h4 className="font-semibold text-white mb-2">Channels</h4>
                <div className="flex flex-wrap gap-2">
                  {strategy.gtm.channels.map((c, i) => (
                    <span key={i} className="text-xs px-2 py-1 rounded-full bg-gray-800 text-gray-300">
                      {c}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Report */}
        {activeTab === 'report' && (
          <div className="p-4 rounded-xl bg-gray-900 border border-gray-700">
            {presenter?.report_markdown ? (
              <pre className="whitespace-pre-wrap text-sm text-gray-300 font-mono
                max-h-[500px] overflow-y-auto">
                {presenter.report_markdown}
              </pre>
            ) : (
              <p className="text-gray-500 text-sm">Report not yet generated.</p>
            )}
          </div>
        )}

        {/* Deck */}
        {activeTab === 'deck' && (
          <div className="space-y-4">
            {(presenter?.deck_slides ?? []).map((slide, i) => (
              <div key={i} className="p-4 rounded-xl bg-gray-900 border border-gray-700">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-400">#{i + 1}</span>
                  <h4 className="font-semibold text-white">{slide.title}</h4>
                </div>
                <ul className="space-y-1">
                  {(slide.bullets ?? []).map((b, j) => (
                    <li key={j} className="text-sm text-gray-300 flex items-start gap-2">
                      <span className="text-indigo-400 mt-0.5">•</span> {b}
                    </li>
                  ))}
                </ul>
                {slide.speaker_note && (
                  <p className="mt-3 text-xs text-gray-500 italic border-t border-gray-800 pt-2">
                    {slide.speaker_note}
                  </p>
                )}
              </div>
            ))}
            {!presenter?.deck_slides?.length && (
              <p className="text-gray-500 text-sm">Deck not yet generated.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ResultsDashboard;
