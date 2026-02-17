import React from 'react';
import ChatView from './ChatView';
import InputBar from './InputBar';
import PhaseIndicator from './PhaseIndicator';
import LLMStatusPanel from './LLMStatusPanel';
import { useI18n } from '../i18n';

export default function MixAIView({ mixAI, token, contextMode, onModeChange, tokenEstimate }) {
  const { t } = useI18n();
  const { messages, sendMixMessage, isExecuting, phaseInfo, llmStatus, phase2Progress } = mixAI;

  return (
    <>
      {isExecuting && (
        <div className="shrink-0 px-4 py-2 bg-gray-900/80 border-b border-gray-800">
          <PhaseIndicator phase={phaseInfo.phase} description={phaseInfo.description} />
          {phaseInfo.phase === 2 && (
            <LLMStatusPanel
              llmStatus={llmStatus}
              progress={phase2Progress}
            />
          )}
        </div>
      )}

      <ChatView messages={messages} isExecuting={isExecuting} />

      <InputBar
        onSend={(prompt, options) => sendMixMessage(prompt, {
          modelAssignments: {
            coding: "devstral-2:123b",
            research: "command-a:latest",
            reasoning: "nemotron-3-nano:30b",
          },
          ...options,
        })}
        disabled={isExecuting}
        placeholder={t('web.inputBar.mixPlaceholder')}
        token={token}
        contextMode={contextMode}
        onModeChange={onModeChange}
        tokenEstimate={tokenEstimate}
      />
    </>
  );
}
