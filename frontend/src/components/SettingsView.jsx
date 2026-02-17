import React, { useState, useEffect } from 'react';
import { useI18n } from '../i18n';

const API_BASE = '';

export default function SettingsView({ token }) {
  const { t, lang, setLang } = useI18n();
  const [settings, setSettings] = useState(null);
  const [gpuInfo, setGpuInfo] = useState(null);
  const [ragStatus, setRagStatus] = useState(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [editPin, setEditPin] = useState('');
  const [editJwtExpiry, setEditJwtExpiry] = useState(168);
  const [editTimeout, setEditTimeout] = useState(90);

  useEffect(() => {
    fetchSettings();
    fetchGpuInfo();
    fetchRagStatus();
    const gpuInterval = setInterval(fetchGpuInfo, 5000);
    return () => clearInterval(gpuInterval);
  }, [token]);

  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

  async function fetchSettings() {
    try {
      const res = await fetch(`${API_BASE}/api/settings`, { headers });
      if (res.ok) {
        const data = await res.json();
        setSettings(data);
        setEditJwtExpiry(data.jwt_expiry_hours || 168);
        setEditTimeout(data.claude_timeout_minutes || 90);
      }
    } catch (e) { console.error('Settings fetch error:', e); }
  }

  async function fetchGpuInfo() {
    try {
      const res = await fetch(`${API_BASE}/api/monitor/gpu`, { headers });
      if (res.ok) setGpuInfo(await res.json());
    } catch (e) { console.error('GPU fetch error:', e); }
  }

  async function fetchRagStatus() {
    try {
      const res = await fetch(`${API_BASE}/api/rag/status`, { headers });
      if (res.ok) setRagStatus(await res.json());
    } catch (e) { console.error('RAG status fetch error:', e); }
  }

  async function saveSettings() {
    setSaving(true);
    setMessage('');
    const body = {};
    if (editPin) body.pin = editPin;
    body.jwt_expiry_hours = editJwtExpiry;
    body.claude_timeout_minutes = editTimeout;
    try {
      const res = await fetch(`${API_BASE}/api/settings`, {
        method: 'PUT', headers, body: JSON.stringify(body),
      });
      if (res.ok) {
        setMessage(t('common.saved'));
        setEditPin('');
      } else {
        setMessage(t('common.saveFailed'));
      }
    } catch (e) { setMessage(t('common.error') + ': ' + e.message); }
    setSaving(false);
    setTimeout(() => setMessage(''), 3000);
  }

  if (!settings) return <div className="flex-1 flex items-center justify-center text-gray-500">{t('common.loading')}</div>;

  return (
    <div className="flex-1 overflow-y-auto min-h-0 px-4 py-4 space-y-4">
      {/* v9.6.0: Language */}
      <Section title={t('web.settings.language')}>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setLang('ja')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              lang === 'ja' ? 'bg-emerald-700 text-white' : 'bg-gray-800 text-gray-400 hover:text-gray-200'
            }`}
          >
            {t('web.settings.langJa')}
          </button>
          <button
            onClick={() => setLang('en')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              lang === 'en' ? 'bg-emerald-700 text-white' : 'bg-gray-800 text-gray-400 hover:text-gray-200'
            }`}
          >
            {t('web.settings.langEn')}
          </button>
        </div>
      </Section>

      {/* Claude Model */}
      <Section title={t('web.settings.claudeModel')}>
        <InfoRow label={t('web.settings.defaultModel')} value={settings.claude_model_id || t('web.settings.notSet')} />
        <div className="flex items-center justify-between gap-3">
          <label className="text-gray-300 text-sm shrink-0">{t('web.settings.timeout')}</label>
          <select
            value={editTimeout}
            onChange={e => setEditTimeout(Number(e.target.value))}
            onWheel={e => e.currentTarget.blur()}
            className="bg-gray-800 text-gray-200 text-sm rounded-lg px-3 py-1.5 border border-gray-700 focus:border-emerald-500 outline-none max-w-[200px]"
          >
            <option value={10}>{t('web.settings.timeoutMin', { min: 10 })}</option>
            <option value={30}>{t('web.settings.timeoutMin', { min: 30 })}</option>
            <option value={60}>{t('web.settings.timeoutHour', { min: 60, hour: 1 })}</option>
            <option value={90}>{t('web.settings.timeoutHour', { min: 90, hour: 1.5 })}</option>
            <option value={120}>{t('web.settings.timeoutHour', { min: 120, hour: 2 })}</option>
            <option value={180}>{t('web.settings.timeoutHour', { min: 180, hour: 3 })}</option>
          </select>
        </div>
      </Section>

      {/* P1/P3 Engine */}
      <Section title={t('web.settings.p1p3Engine')} badge={t('web.settings.desktopOnly')}>
        <InfoRow
          label="orchestrator_engine"
          value={settings.orchestrator_engine || 'claude-opus-4-6'}
        />
        <div className="text-[10px] text-gray-500 mt-1">
          {(settings.orchestrator_engine || '').startsWith('claude-') ? `\u2601 ${t('web.settings.claudeApi')}` : `\uD83D\uDDA5 ${t('web.settings.localLlm')}`}
        </div>
      </Section>

      {/* mixAI Model Assignment */}
      <Section title={t('web.settings.modelAssignment')} badge={t('web.settings.desktopOnly')}>
        {['coding', 'research', 'reasoning', 'vision', 'translation'].map(cat => (
          <InfoRow
            key={cat}
            label={cat}
            value={settings.model_assignments?.[cat] || t('web.settings.unassigned')}
          />
        ))}
      </Section>

      {/* Project */}
      <Section title={t('web.settings.projectInfo')} badge={t('web.settings.desktopOnly')}>
        <InfoRow label={t('web.settings.projectDir')} value={settings.project_dir || t('web.settings.notSet')} />
        <InfoRow label={t('web.settings.ollamaHost')} value={settings.ollama_host || 'http://localhost:11434'} />
      </Section>

      {/* RAG */}
      {ragStatus && (
        <Section title={t('web.settings.rag')}>
          <InfoRow label={t('web.settings.ragDatabase')} value={ragStatus.available ? t('web.settings.ragAvailable') : t('web.settings.ragNotBuilt')} />
          {ragStatus.available && (
            <>
              <InfoRow label={t('web.settings.ragSemantic')} value={t('web.settings.ragCount', { count: ragStatus.semantic_count || 0 })} />
              <InfoRow label={t('web.settings.ragEpisodic')} value={t('web.settings.ragCount', { count: ragStatus.episodic_count || 0 })} />
              <InfoRow label={t('web.settings.ragDocChunk')} value={t('web.settings.ragCount', { count: ragStatus.document_chunk_count || 0 })} />
              <InfoRow label={t('web.settings.ragDocSummary')} value={t('web.settings.ragCount', { count: ragStatus.document_summary_count || 0 })} />
            </>
          )}
        </Section>
      )}

      {/* GPU Monitor */}
      <Section title={t('web.settings.gpuMonitor')}>
        {gpuInfo && gpuInfo.gpus && gpuInfo.gpus.length > 0 ? (
          <div className="space-y-2">
            {gpuInfo.gpus.map((gpu, i) => (
              <GpuCard key={i} gpu={gpu} />
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-sm">
            {gpuInfo?.error ? t('web.settings.gpuError', { error: gpuInfo.error }) : t('web.settings.gpuLoading')}
          </p>
        )}
      </Section>

      {/* Security */}
      <Section title={t('web.settings.security')}>
        <InputRow
          label={t('web.settings.pinChange')}
          type="password"
          value={editPin}
          onChange={setEditPin}
          placeholder={t('web.settings.pinPlaceholder')}
        />
        <div className="flex items-center justify-between gap-3">
          <label className="text-gray-300 text-sm shrink-0">{t('web.settings.jwtExpiry')}</label>
          <select
            value={editJwtExpiry}
            onChange={e => setEditJwtExpiry(Number(e.target.value))}
            onWheel={e => e.currentTarget.blur()}
            className="bg-gray-800 text-gray-200 text-sm rounded-lg px-3 py-1.5 border border-gray-700 focus:border-emerald-500 outline-none max-w-[200px]"
          >
            <option value={24}>{t('web.settings.jwtHours', { hours: 24, days: 1 })}</option>
            <option value={72}>{t('web.settings.jwtHours', { hours: 72, days: 3 })}</option>
            <option value={168}>{t('web.settings.jwtHours', { hours: 168, days: 7 })}</option>
            <option value={336}>{t('web.settings.jwtHours', { hours: 336, days: 14 })}</option>
            <option value={720}>{t('web.settings.jwtHours', { hours: 720, days: 30 })}</option>
          </select>
        </div>
        <InfoRow label={t('web.settings.maxConnections')} value={`${settings.max_connections || 3}`} />
      </Section>

      {/* Save Button */}
      <div className="flex items-center gap-3 pt-2 pb-8">
        <button
          onClick={saveSettings}
          disabled={saving}
          className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-600 text-white rounded-lg font-medium transition-colors"
        >
          {saving ? t('common.saving') : t('web.settings.saveButton')}
        </button>
        {message && (
          <span className={`text-sm ${message.includes(t('common.error')) ? 'text-red-400' : 'text-emerald-400'}`}>
            {message}
          </span>
        )}
      </div>
    </div>
  );
}

function Section({ title, badge, children }) {
  return (
    <div className="bg-gray-900 rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2">
        <h3 className="text-emerald-400 font-semibold text-sm">{title}</h3>
        {badge && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-500 border border-gray-700">
            {badge}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

function InputRow({ label, type = 'text', value, onChange, placeholder }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <label className="text-gray-300 text-sm shrink-0">{label}</label>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="bg-gray-800 text-gray-200 text-sm rounded-lg px-3 py-1.5 border border-gray-700 focus:border-emerald-500 outline-none max-w-[200px]"
      />
    </div>
  );
}

function InfoRow({ label, value }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-gray-400 text-sm">{label}</span>
      <span className="text-gray-300 text-sm font-mono truncate max-w-[200px]">{value}</span>
    </div>
  );
}

function GpuCard({ gpu }) {
  const { t } = useI18n();
  const vramPercent = gpu.memory_total > 0 ? (gpu.memory_used / gpu.memory_total * 100) : 0;
  const barColor = vramPercent > 90 ? 'bg-red-500' : vramPercent > 70 ? 'bg-amber-500' : 'bg-emerald-500';

  return (
    <div className="bg-gray-800 rounded-lg p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-gray-200 text-sm font-medium">{gpu.name}</span>
        <span className="text-gray-400 text-xs">{gpu.utilization}% util</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
          <div className={`h-full ${barColor} rounded-full transition-all duration-500`}
               style={{ width: `${vramPercent}%` }} />
        </div>
        <span className="text-gray-400 text-xs shrink-0">
          {(gpu.memory_used / 1024).toFixed(1)}/{(gpu.memory_total / 1024).toFixed(1)} GB
        </span>
      </div>
      <div className="text-gray-500 text-xs">
        {t('web.settings.gpuTemp', { temp: gpu.temperature, power: gpu.power_draw })}
      </div>
    </div>
  );
}
