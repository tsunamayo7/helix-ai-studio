import React from 'react';
import { useI18n } from '../i18n';

export default function PhaseIndicator({ phase, description }) {
  const { t } = useI18n();

  const PHASES = [
    { id: 1, label: 'P1', name: t('web.phase.p1') },
    { id: 2, label: 'P2', name: t('web.phase.p2') },
    { id: 3, label: 'P3', name: t('web.phase.p3') },
  ];

  return (
    <div className="flex items-center gap-2">
      {PHASES.map((p) => (
        <div key={p.id} className="flex items-center gap-1">
          <div
            className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
              phase === p.id
                ? 'bg-emerald-500 text-white animate-pulse'
                : phase > p.id
                ? 'bg-emerald-700 text-emerald-200'
                : 'bg-gray-700 text-gray-500'
            }`}
          >
            {phase > p.id ? '\u2713' : p.label}
          </div>
          <span className={`text-xs hidden sm:inline ${
            phase === p.id ? 'text-emerald-400' : 'text-gray-500'
          }`}>
            {p.name}
          </span>
          {p.id < 3 && <div className="w-4 h-px bg-gray-700" />}
        </div>
      ))}
      {description && (
        <span className="ml-2 text-xs text-gray-400 truncate">{description}</span>
      )}
    </div>
  );
}
