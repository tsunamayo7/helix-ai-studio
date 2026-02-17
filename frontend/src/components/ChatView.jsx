import React, { useRef, useEffect, useState } from 'react';
import MarkdownRenderer from './MarkdownRenderer';
import { useI18n } from '../i18n';

export default function ChatView({ messages, isExecuting }) {
  const { t } = useI18n();
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isExecuting]);

  return (
    <main className="flex-1 overflow-y-auto px-4 py-4 space-y-4 min-h-0">
      {messages.length === 0 && (
        <div className="flex flex-col items-center justify-center h-full text-gray-500">
          <div className="w-20 h-20 rounded-2xl bg-gray-900 flex items-center justify-center text-3xl mb-4">
            H
          </div>
          <p className="text-lg font-medium">Helix AI Studio</p>
          <p className="text-sm mt-1">{t('web.chat.startMessage')}</p>
        </div>
      )}

      {messages.map((msg, idx) => (
        <MessageBubble key={idx} message={msg} />
      ))}

      {isExecuting && messages[messages.length - 1]?.role !== 'assistant' && (
        <div className="flex justify-start">
          <div className="bg-gray-800 rounded-2xl px-4 py-3">
            <div className="flex gap-1">
              <span className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </main>
  );
}

function MessageBubble({ message }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  const isAssistant = message.role === 'assistant';
  const isSystem = message.role === 'system';

  function handleCopyAll() {
    navigator.clipboard.writeText(message.content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className={`flex ${isAssistant || isSystem ? 'justify-start' : 'justify-end'} group`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 ${
          message.role === 'user'
            ? 'bg-emerald-700 text-white'
            : message.isError
            ? 'bg-red-900/50 border border-red-800 text-red-200'
            : isSystem
            ? 'bg-amber-900/30 border border-amber-800/50 text-amber-200'
            : 'bg-gray-800 text-gray-100'
        }`}
      >
        {isAssistant ? (
          <>
            <MarkdownRenderer content={message.content} />
            <div className="flex justify-end mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={handleCopyAll}
                className="text-[10px] text-gray-500 hover:text-gray-300 px-2 py-0.5"
              >
                {copied ? `\u2713 ${t('web.chat.copiedAnswer')}` : t('web.chat.copyAnswer')}
              </button>
            </div>
          </>
        ) : (
          <p className="whitespace-pre-wrap text-sm">{message.content}</p>
        )}
        {message.streaming && (
          <span className="inline-block w-2 h-4 ml-1 bg-emerald-400 animate-pulse" />
        )}
      </div>
    </div>
  );
}
