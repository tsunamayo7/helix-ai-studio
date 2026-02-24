import { useState, useEffect, useRef, useCallback } from 'react';

export function useWebSocket(token, endpoint = 'solo') {
  const [status, setStatus] = useState('disconnected');
  const [messages, setMessages] = useState([]);
  const [isExecuting, setIsExecuting] = useState(false);
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);

  // mixAI用の追加ステート
  const [phaseInfo, setPhaseInfo] = useState({ phase: 0, description: '' });
  const [llmStatus, setLlmStatus] = useState([]);
  const [phase2Progress, setPhase2Progress] = useState({ completed: 0, total: 0 });

  // v9.2.0: チャット管理
  const [activeChatId, setActiveChatId] = useState(null);
  const [chatTitle, setChatTitle] = useState('');

  // WebSocket接続
  useEffect(() => {
    if (!token) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/${endpoint}?token=${token}`;

    function connect() {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus('connected');
        console.log(`WebSocket connected (${endpoint})`);
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleMessage(data);
      };

      ws.onclose = (event) => {
        setStatus('disconnected');
        wsRef.current = null;
        if (event.code !== 4001 && event.code !== 4003) {
          reconnectRef.current = setTimeout(connect, 5000);
        }
      };

      ws.onerror = () => {
        setStatus('error');
      };
    }

    connect();

    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [token, endpoint]);

  // メッセージハンドラ
  function handleMessage(data) {
    switch (data.type) {
      case 'streaming':
        if (data.done) {
          setMessages(prev => {
            const updated = [...prev];
            const lastIdx = updated.length - 1;
            if (lastIdx >= 0 && updated[lastIdx].role === 'assistant' && updated[lastIdx].streaming) {
              updated[lastIdx] = {
                ...updated[lastIdx],
                content: data.chunk || updated[lastIdx].content,
                streaming: false,
              };
            } else {
              updated.push({ role: 'assistant', content: data.chunk, streaming: false });
            }
            return updated;
          });
          setIsExecuting(false);
        } else {
          setMessages(prev => {
            const updated = [...prev];
            const lastIdx = updated.length - 1;
            if (lastIdx >= 0 && updated[lastIdx].role === 'assistant' && updated[lastIdx].streaming) {
              updated[lastIdx] = {
                ...updated[lastIdx],
                content: updated[lastIdx].content + data.chunk,
              };
            } else {
              updated.push({ role: 'assistant', content: data.chunk, streaming: true });
            }
            return updated;
          });
        }
        break;

      case 'status':
        setStatus(data.status);
        if (data.status === 'executing') setIsExecuting(true);
        if (data.status === 'completed' || data.status === 'cancelled') setIsExecuting(false);
        break;

      case 'error':
        setMessages(prev => [
          ...prev,
          { role: 'system', content: `エラー: ${data.error}`, isError: true },
        ]);
        setIsExecuting(false);
        break;

      case 'pong':
        break;

      // v9.2.0: チャット管理メッセージ
      case 'chat_created':
        setActiveChatId(data.chat_id);
        break;

      case 'chat_title_updated':
        setChatTitle(data.title);
        break;

      case 'token_warning':
        setMessages(prev => [
          ...prev,
          { role: 'system', content: data.message, isError: false },
        ]);
        break;

      // mixAI用メッセージタイプ
      case 'phase_changed':
        setPhaseInfo({ phase: data.phase, description: data.description });
        setIsExecuting(true);
        break;

      case 'llm_started':
        setLlmStatus(prev => [
          ...prev,
          { category: data.category, model: data.model, status: 'running', elapsed: 0 },
        ]);
        break;

      case 'llm_finished':
        setLlmStatus(prev =>
          prev.map(s =>
            s.category === data.category
              ? { ...s, status: data.success ? 'done' : 'error', elapsed: data.elapsed }
              : s
          )
        );
        break;

      case 'phase2_progress':
        setPhase2Progress({ completed: data.completed, total: data.total });
        break;

      default:
        console.warn('Unknown WebSocket message type:', data.type);
    }
  }

  // cloudAI用メッセージ送信（v9.2.0: chat_id対応）
  const sendMessage = useCallback((prompt, options = {}) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('WebSocket not connected');
      return;
    }

    setMessages(prev => [...prev, { role: 'user', content: prompt }]);
    setIsExecuting(true);

    wsRef.current.send(JSON.stringify({
      action: 'execute',
      prompt,
      chat_id: options.chatId || activeChatId || null,
      model_id: options.modelId || '',
      project_dir: options.projectDir || '',
      timeout: options.timeout || 0,  // 0 = サーバー側で設定ファイルから読み取り
      use_mcp: options.useMcp !== false,
      auto_approve: options.autoApprove !== false,
      enable_rag: options.enableRag !== false,
      attached_files: options.attachedFiles || [],
    }));
  }, [activeChatId]);

  // mixAI用メッセージ送信（v9.2.0: chat_id対応）
  const sendMixMessage = useCallback((prompt, options = {}) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('WebSocket not connected');
      return;
    }

    setMessages(prev => [...prev, { role: 'user', content: prompt }]);
    setIsExecuting(true);
    setPhaseInfo({ phase: 0, description: '' });
    setLlmStatus([]);
    setPhase2Progress({ completed: 0, total: 0 });

    wsRef.current.send(JSON.stringify({
      action: 'execute',
      prompt,
      chat_id: options.chatId || activeChatId || null,
      model_id: options.modelId || '',
      model_assignments: options.modelAssignments || {},
      project_dir: options.projectDir || '',
      attached_files: options.attachedFiles || [],
      timeout: options.timeout || 0,  // 0 = サーバー側で設定ファイルから読み取り
      enable_rag: options.enableRag !== false,
    }));
  }, [activeChatId]);

  // v11.5.3: localAI用メッセージ送信
  const sendLocalMessage = useCallback((prompt, options = {}) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('WebSocket not connected');
      return;
    }

    setMessages(prev => [...prev, { role: 'user', content: prompt }]);
    setIsExecuting(true);

    wsRef.current.send(JSON.stringify({
      action: 'execute',
      prompt,
      chat_id: options.chatId || activeChatId || null,
      model: options.model || '',
      attached_files: options.attachedFiles || [],
      client_info: 'Web Client (localAI)',
    }));
  }, [activeChatId]);

  // v9.2.0: メッセージクリア + チャット切替
  const clearMessages = useCallback(() => {
    setMessages([]);
    setIsExecuting(false);
    setPhaseInfo({ phase: 0, description: '' });
    setLlmStatus([]);
    setPhase2Progress({ completed: 0, total: 0 });
  }, []);

  const loadChat = useCallback(async (chatId) => {
    setActiveChatId(chatId);
    if (!chatId) {
      clearMessages();
      setChatTitle('');
      return;
    }
    try {
      const res = await fetch(`/api/chats/${chatId}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setChatTitle(data.chat.title || '');
        const restored = (data.messages || []).map(m => ({
          role: m.role,
          content: m.content,
          isError: m.role === 'error',
          streaming: false,
        }));
        setMessages(restored);
      }
    } catch (e) { console.error('Failed to load chat:', e); }
  }, [token, clearMessages]);

  return {
    status,
    messages,
    sendMessage,
    sendMixMessage,
    sendLocalMessage,
    isExecuting,
    phaseInfo,
    llmStatus,
    phase2Progress,
    // v9.2.0
    activeChatId,
    setActiveChatId,
    chatTitle,
    clearMessages,
    loadChat,
  };
}
