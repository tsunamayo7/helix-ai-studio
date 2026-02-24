import React, { useState, useEffect, useCallback } from 'react';
import ChatView from './ChatView';
import InputBar from './InputBar';
import { useI18n } from '../i18n';

function ModelSelector({ token, selectedModel, onModelChange, disabled }) {
  const { t } = useI18n();
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchModels = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const res = await fetch('/api/config/ollama-models', {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setModels(data);
        // 最初のモデルを自動選択
        if (data.length > 0 && !selectedModel) {
          onModelChange(data[0].name);
        }
      }
    } catch (e) {
      console.error('Failed to fetch Ollama models:', e);
    }
    setLoading(false);
  }, [token, selectedModel, onModelChange]);

  useEffect(() => {
    fetchModels();
  }, []);

  return (
    <div className="shrink-0 flex items-center gap-2 px-4 py-2 bg-gray-900 border-b border-gray-800">
      <span className="text-xs text-gray-500 shrink-0">
        {t('web.localAI.model') || 'モデル:'}
      </span>
      <select
        value={selectedModel}
        onChange={(e) => onModelChange(e.target.value)}
        disabled={disabled || loading}
        className="flex-1 bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-lg
                   px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-emerald-500
                   disabled:opacity-50 max-w-xs"
      >
        {models.length === 0 && (
          <option value="">
            {loading
              ? (t('web.localAI.loadingModels') || 'モデル取得中...')
              : (t('web.localAI.noModels') || 'モデルなし（Ollama未起動？）')}
          </option>
        )}
        {models.map(m => (
          <option key={m.name} value={m.name}>{m.name}</option>
        ))}
      </select>
      <button
        onClick={fetchModels}
        disabled={disabled || loading}
        className="text-[10px] px-2 py-1 rounded bg-gray-700 text-gray-400
                   hover:bg-gray-600 hover:text-gray-200 transition-colors disabled:opacity-50"
      >
        {loading ? '...' : '🔄'}
      </button>
    </div>
  );
}

export default function LocalAIView({ localAI, token }) {
  const { t } = useI18n();
  const [selectedModel, setSelectedModel] = useState('');

  const handleSend = useCallback((prompt, options = {}) => {
    localAI.sendLocalMessage(prompt, {
      ...options,
      model: selectedModel,
    });
  }, [localAI, selectedModel]);

  // Ollamaが未起動の場合のエラー表示
  const hasOllamaError = localAI.messages.some(m =>
    m.role === 'error' &&
    (m.content?.includes('Ollama') || m.content?.includes('接続できません'))
  );

  return (
    <>
      {/* モデル選択バー */}
      <ModelSelector
        token={token}
        selectedModel={selectedModel}
        onModelChange={setSelectedModel}
        disabled={localAI.isExecuting}
      />

      {/* Ollama未起動警告 */}
      {hasOllamaError && (
        <div className="shrink-0 mx-4 mt-2 px-3 py-2 bg-yellow-900/30 border border-yellow-800/50 rounded-lg">
          <p className="text-xs text-yellow-300">
            ⚠️ {t('web.localAI.ollamaWarning') || 'Ollamaに接続できません。デスクトップアプリでOllamaが起動していることを確認してください。'}
          </p>
        </div>
      )}

      {/* チャット表示 */}
      <ChatView
        messages={localAI.messages}
        isExecuting={localAI.isExecuting}
      />

      {/* 入力バー */}
      <InputBar
        onSend={handleSend}
        disabled={localAI.isExecuting || !selectedModel}
        token={token}
        placeholder={t('web.localAI.inputPlaceholder') || 'ローカルLLMへメッセージを入力... (Ctrl+Enter で送信)'}
      />
    </>
  );
}
