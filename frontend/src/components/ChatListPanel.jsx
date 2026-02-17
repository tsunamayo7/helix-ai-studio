import React, { useState, useEffect } from 'react';
import { useI18n } from '../i18n';

const MAX_CHATS = 500;

export default function ChatListPanel({ token, activeTab, activeChatId,
                                        onSelectChat, onNewChat, onClose }) {
  const { t, lang } = useI18n();
  const [chats, setChats] = useState([]);
  const [loading, setLoading] = useState(false);

  const headers = { 'Authorization': `Bearer ${token}` };

  useEffect(() => {
    fetchChats();
  }, [activeTab]);

  async function fetchChats() {
    setLoading(true);
    try {
      const res = await fetch(`/api/chats?tab=${activeTab}`, { headers });
      if (res.ok) {
        const data = await res.json();
        setChats(data.chats || []);
      }
    } catch (e) { console.error(e); }
    setLoading(false);
  }

  async function handleNewChat() {
    try {
      const res = await fetch(`/api/chats?tab=${activeTab}&context_mode=session`, {
        method: 'POST', headers,
      });
      if (res.ok) {
        const chat = await res.json();
        onNewChat(chat);
        fetchChats();
      }
    } catch (e) { console.error(e); }
  }

  async function handleDelete(chatId, e) {
    e.stopPropagation();
    if (!confirm(t('web.chatList.deleteConfirm'))) return;
    try {
      await fetch(`/api/chats/${chatId}`, { method: 'DELETE', headers });
      fetchChats();
      if (activeChatId === chatId) onNewChat(null);
    } catch (e) { console.error(e); }
  }

  function formatDate(iso) {
    const d = new Date(iso);
    const now = new Date();
    const locale = lang === 'en' ? 'en-US' : 'ja-JP';
    if (d.toDateString() === now.toDateString()) {
      return d.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
    }
    return d.toLocaleDateString(locale, { month: 'short', day: 'numeric' });
  }

  return (
    <div className="fixed inset-0 z-40 flex">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      <div className="relative w-72 bg-gray-900 h-full flex flex-col border-r border-gray-800 z-50">
        <div className="shrink-0 flex items-center justify-between p-4 border-b border-gray-800">
          <h2 className="text-gray-100 font-medium">{t('web.chatList.title')}</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-lg">&times;</button>
        </div>

        <button
          onClick={handleNewChat}
          className="shrink-0 mx-3 mt-3 px-4 py-2.5 bg-emerald-700 hover:bg-emerald-600
                     text-white rounded-lg text-sm font-medium transition-colors"
        >
          {t('web.chatList.newChat')}
        </button>

        <div className="flex-1 overflow-y-auto mt-2 min-h-0">
          {chats.map(chat => (
            <button
              key={chat.id}
              onClick={() => { onSelectChat(chat); onClose(); }}
              className={`w-full text-left px-4 py-3 flex items-start gap-2 hover:bg-gray-800/50
                border-b border-gray-800/30 group
                ${activeChatId === chat.id ? 'bg-emerald-900/20' : ''}`}
            >
              <div className="flex-1 min-w-0">
                <p className={`text-sm truncate ${
                  activeChatId === chat.id ? 'text-emerald-300' : 'text-gray-300'
                }`}>
                  {chat.title}
                </p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-[10px] text-gray-600">{formatDate(chat.updated_at)}</span>
                  <span className="text-[10px] text-gray-600">{chat.message_count}{t('web.chatList.items')}</span>
                  <span className={`text-[10px] px-1 rounded ${
                    chat.context_mode === 'full' ? 'bg-amber-900/50 text-amber-400' :
                    chat.context_mode === 'session' ? 'bg-emerald-900/50 text-emerald-400' :
                    'bg-gray-800 text-gray-500'
                  }`}>
                    {chat.context_mode === 'full' ? t('web.chatList.contextFull') :
                     chat.context_mode === 'session' ? t('web.chatList.contextSession') : t('web.chatList.contextSingle')}
                  </span>
                </div>
              </div>
              <button
                onClick={(e) => handleDelete(chat.id, e)}
                className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-red-400 text-xs p-1"
              >
                &times;
              </button>
            </button>
          ))}
          {chats.length === 0 && !loading && (
            <p className="text-gray-600 text-sm text-center py-8">{t('web.chatList.noChats')}</p>
          )}
        </div>

        <div className="shrink-0 px-4 py-2 border-t border-gray-800 text-[10px] text-gray-600">
          {t('web.chatList.chatCount', { count: chats.length, max: MAX_CHATS })}
        </div>
      </div>
    </div>
  );
}
