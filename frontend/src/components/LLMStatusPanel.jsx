import React from 'react';

export default function LLMStatusPanel({ llmStatus, progress }) {
  return (
    <div className="mt-2 space-y-1">
      {/* プログレスバー */}
      <div className="flex items-center gap-2">
        <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-emerald-500 rounded-full transition-all duration-500"
            style={{ width: progress.total ? `${(progress.completed / progress.total) * 100}%` : '0%' }}
          />
        </div>
        <span className="text-xs text-gray-400 shrink-0">
          {progress.completed}/{progress.total}
        </span>
      </div>

      {/* LLMステータス一覧 */}
      <div className="flex flex-wrap gap-1">
        {llmStatus.map((s, i) => (
          <div
            key={i}
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] ${
              s.status === 'running'
                ? 'bg-amber-900/50 text-amber-300'
                : s.status === 'done'
                ? 'bg-emerald-900/50 text-emerald-300'
                : 'bg-red-900/50 text-red-300'
            }`}
          >
            {s.status === 'running' && <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />}
            {s.status === 'done' && <span>{'\u2713'}</span>}
            {s.status === 'error' && <span>{'\u2717'}</span>}
            <span>{s.category}</span>
            {s.elapsed > 0 && <span className="opacity-60">{s.elapsed}s</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
