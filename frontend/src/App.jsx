import React, { useState, useCallback, useEffect } from 'react';
import LoginScreen from './components/LoginScreen';
import ChatView from './components/ChatView';
import InputBar from './components/InputBar';
import StatusIndicator from './components/StatusIndicator';
import TabBar from './components/TabBar';
import MixAIView from './components/MixAIView';
import SettingsView from './components/SettingsView';
import FileManagerView from './components/FileManagerView';
import ChatListPanel from './components/ChatListPanel';
import { useAuth } from './hooks/useAuth';
import { useWebSocket } from './hooks/useWebSocket';
import { useI18n } from './i18n';

// v9.5.0: Pre-login chat viewing
function PreLoginView({ onLogin }) {
  const { t, lang } = useI18n();
  const [recentChats, setRecentChats] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPublicChats();
  }, []);

  async function fetchPublicChats() {
    try {
      const res = await fetch('/api/chats/public-list?limit=10');
      if (res.ok) {
        const data = await res.json();
        setRecentChats(data.chats || []);
      }
    } catch (e) {
      console.error('Failed to fetch public chats:', e);
    }
    setLoading(false);
  }

  function formatDate(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    const now = new Date();
    const locale = lang === 'en' ? 'en-US' : 'ja-JP';
    const isToday = d.toDateString() === now.toDateString();
    if (isToday) {
      return d.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
    }
    return d.toLocaleDateString(locale, { month: 'numeric', day: 'numeric' })
      + ' ' + d.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
  }

  function tabBadge(tab) {
    if (tab === 'mixAI') return { text: 'mixAI', color: 'bg-purple-900/50 text-purple-300' };
    return { text: 'soloAI', color: 'bg-cyan-900/50 text-cyan-300' };
  }

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      <div className="p-4 border-b border-gray-800 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-emerald-400">Helix AI Studio</h1>
          <p className="text-[10px] text-gray-600">v9.6.0 Global Ready</p>
        </div>
        <button
          onClick={onLogin}
          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white
                     text-sm font-medium rounded-lg transition-colors"
        >
          {t('web.preLogin.login')}
        </button>
      </div>

      <div className="flex-1 overflow-auto p-4">
        <h2 className="text-sm font-medium text-gray-400 mb-3">{t('web.preLogin.recentChats')}</h2>

        {loading && (
          <p className="text-gray-600 text-sm text-center py-8">{t('web.preLogin.loading')}</p>
        )}

        {!loading && recentChats.length === 0 && (
          <p className="text-gray-600 text-sm text-center py-8">
            {t('web.preLogin.noChats')}
          </p>
        )}

        <div className="space-y-2">
          {recentChats.map(chat => {
            const badge = tabBadge(chat.tab);
            return (
              <div key={chat.id}
                className="bg-gray-900 rounded-lg border border-gray-800 p-3
                           hover:border-gray-700 transition-colors">
                <div className="flex items-center justify-between mb-1">
                  <h3 className="text-sm font-medium text-gray-200 truncate flex-1">
                    {chat.title || t('common.untitled')}
                  </h3>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${badge.color} ml-2 shrink-0`}>
                    {badge.text}
                  </span>
                </div>

                <div className="flex items-center gap-2 text-[10px] text-gray-600 mb-2">
                  <span>{formatDate(chat.updated_at)}</span>
                  <span>&middot;</span>
                  <span>{t('web.preLogin.messagesCount', { count: chat.message_count })}</span>
                </div>

                {chat.assistant_preview && (
                  <p className="text-xs text-gray-500 line-clamp-2">
                    {chat.assistant_preview}...
                  </p>
                )}

                <button
                  onClick={onLogin}
                  className="mt-2 text-[10px] text-emerald-500 hover:text-emerald-400
                             transition-colors"
                >
                  {t('web.preLogin.loginToContinue')} &rarr;
                </button>
              </div>
            );
          })}
        </div>

        {recentChats.length > 0 && (
          <p className="text-[10px] text-gray-700 text-center mt-4">
            {t('web.preLogin.showingRecent', { count: recentChats.length })} &middot; {t('web.preLogin.loginRequired')}
          </p>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const { t, lang, setLang } = useI18n();
  const { token, isAuthenticated, login, logout } = useAuth();
  const [activeTab, setActiveTab] = useState('soloAI');
  const soloAI = useWebSocket(token, 'solo');
  const mixAI = useWebSocket(token, 'mix');

  const [showChatList, setShowChatList] = useState(false);
  const [showLogin, setShowLogin] = useState(false);
  const [contextMode, setContextMode] = useState('session');
  const [tokenEstimate, setTokenEstimate] = useState(0);

  if (!isAuthenticated) {
    if (showLogin) {
      return <LoginScreen onLogin={(tok) => { login(tok); setShowLogin(false); }} />;
    }
    return <PreLoginView onLogin={() => setShowLogin(true)} />;
  }

  const current = activeTab === 'soloAI' ? soloAI : mixAI;

  function handleSelectChat(chat) {
    const ws = activeTab === 'soloAI' ? soloAI : mixAI;
    ws.loadChat(chat.id);
    setContextMode(chat.context_mode || 'session');
    setTokenEstimate(chat.total_tokens_estimated || 0);
  }

  function handleNewChat(chat) {
    const ws = activeTab === 'soloAI' ? soloAI : mixAI;
    if (chat) {
      ws.loadChat(chat.id);
      setContextMode(chat.context_mode || 'session');
    } else {
      ws.loadChat(null);
    }
    setTokenEstimate(0);
  }

  async function handleModeChange(mode) {
    setContextMode(mode);
    const chatId = current.activeChatId;
    if (chatId) {
      try {
        await fetch(`/api/chats/${chatId}/mode`, {
          method: 'PUT',
          headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ mode }),
        });
      } catch (e) { console.error(e); }
    }
  }

  return (
    <div className="flex flex-col bg-gray-950" style={{ height: '100dvh' }}>
      <header className="shrink-0 flex items-center justify-between px-4 py-3 bg-gray-900 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <button onClick={() => setShowChatList(true)}
                  className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-white rounded-lg hover:bg-gray-800">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
            </svg>
          </button>
          <span className="text-lg font-semibold text-gray-100">Helix AI Studio</span>
        </div>
        <div className="flex items-center gap-2">
          {/* v9.6.0: EN/JP toggle */}
          <button
            onClick={() => setLang(lang === 'ja' ? 'en' : 'ja')}
            className="text-[10px] px-2 py-0.5 rounded bg-gray-800 text-gray-400 hover:text-gray-200 transition-colors"
          >
            {lang === 'ja' ? 'EN' : 'JP'}
          </button>
          {current.activeChatId && tokenEstimate > 0 && (
            <span className={`text-[10px] px-2 py-0.5 rounded ${
              tokenEstimate > 50000 ? 'bg-red-900/50 text-red-400' :
              tokenEstimate > 20000 ? 'bg-amber-900/50 text-amber-400' :
              'bg-gray-800 text-gray-500'
            }`}>
              ~{(tokenEstimate / 1000).toFixed(1)}K
            </span>
          )}
          <StatusIndicator status={current.status} />
        </div>
      </header>

      <TabBar activeTab={activeTab} onTabChange={setActiveTab} />

      {showChatList && (
        <ChatListPanel
          token={token}
          activeTab={activeTab}
          activeChatId={current.activeChatId}
          onSelectChat={handleSelectChat}
          onNewChat={handleNewChat}
          onClose={() => setShowChatList(false)}
        />
      )}

      {activeTab === 'settings' ? (
        <SettingsView token={token} />
      ) : activeTab === 'files' ? (
        <FileManagerView token={token} />
      ) : activeTab === 'soloAI' ? (
        <>
          <ChatView messages={soloAI.messages} isExecuting={soloAI.isExecuting} />
          <InputBar
            onSend={soloAI.sendMessage}
            disabled={soloAI.isExecuting}
            token={token}
            contextMode={contextMode}
            onModeChange={handleModeChange}
            tokenEstimate={tokenEstimate}
          />
        </>
      ) : (
        <MixAIView
          mixAI={mixAI}
          token={token}
          contextMode={contextMode}
          onModeChange={handleModeChange}
          tokenEstimate={tokenEstimate}
        />
      )}
    </div>
  );
}
