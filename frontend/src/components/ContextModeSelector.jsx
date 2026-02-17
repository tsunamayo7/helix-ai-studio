import React from 'react';
import { useI18n } from '../i18n';

export default function ContextModeSelector({ mode, onChange, tokenEstimate }) {
  const { t } = useI18n();

  const MODES = [
    { id: 'single', label: t('web.contextMode.single'), color: 'gray' },
    { id: 'session', label: t('web.contextMode.session'), color: 'emerald' },
    { id: 'full', label: t('web.contextMode.full'), color: 'amber' },
  ];

  return (
    <div className="flex items-center gap-1 px-1">
      {MODES.map(m => {
        const isActive = mode === m.id;
        const colorMap = {
          gray: isActive ? 'bg-gray-700 text-gray-200' : 'text-gray-600 hover:bg-gray-800',
          emerald: isActive ? 'bg-emerald-800 text-emerald-200' : 'text-gray-600 hover:bg-gray-800',
          amber: isActive ? 'bg-amber-800 text-amber-200' : 'text-gray-600 hover:bg-gray-800',
        };
        return (
          <button
            key={m.id}
            onClick={() => onChange(m.id)}
            className={`px-2 py-1 rounded text-[11px] transition-colors ${colorMap[m.color]}`}
          >
            {m.label}
          </button>
        );
      })}
      {tokenEstimate > 0 && (
        <span className={`text-[10px] ml-1 ${
          tokenEstimate > 50000 ? 'text-red-400' :
          tokenEstimate > 20000 ? 'text-amber-400' : 'text-gray-600'
        }`}>
          ~{(tokenEstimate / 1000).toFixed(1)}K
        </span>
      )}
    </div>
  );
}
