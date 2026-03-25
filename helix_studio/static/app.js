/* Helix AI Studio — Alpine.js Stores & WebSocket */

document.addEventListener('alpine:init', () => {

    // ── i18n ストア ──────────────────────────────────────
    const TRANSLATIONS = {
        ja: {
            chat: 'チャット', pipeline: 'パイプライン', knowledge: 'ナレッジ',
            history: '履歴', settings: '設定', connected: '接続中', disconnected: '未接続',
            send: '送信', newChat: '新しい会話', deleteConfirm: 'この会話を削除しますか？',
            noConnection: 'サーバーに接続されていません。再接続を待ってください。',
            copied: 'コピー済み', copy: 'コピー',
        },
        en: {
            chat: 'Chat', pipeline: 'Pipeline', knowledge: 'Knowledge',
            history: 'History', settings: 'Settings', connected: 'Connected', disconnected: 'Disconnected',
            send: 'Send', newChat: 'New Chat', deleteConfirm: 'Delete this conversation?',
            noConnection: 'Not connected to server. Please wait for reconnection.',
            copied: 'Copied', copy: 'Copy',
        },
    };

    Alpine.store('i18n', {
        lang: localStorage.getItem('helix_lang') || 'ja',
        t(key) {
            return (TRANSLATIONS[this.lang] || TRANSLATIONS.ja)[key] || key;
        },
        setLang(lang) {
            this.lang = lang;
            localStorage.setItem('helix_lang', lang);
        },
    });

    // ── Markdown レンダラー ───────────────────────────────
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            highlight(code, lang) {
                if (typeof hljs !== 'undefined' && lang && hljs.getLanguage(lang)) {
                    return hljs.highlight(code, { language: lang }).value;
                }
                return typeof hljs !== 'undefined' ? hljs.highlightAuto(code).value : code;
            },
            breaks: true,
            gfm: true,
        });
    }

    // ── App ストア ────────────────────────────────────────
    Alpine.store('app', {
        // WebSocket
        ws: null,
        connected: false,
        reconnectAttempts: 0,
        maxReconnectDelay: 30000,
        reconnectTimer: null,

        // チャット
        messages: [],
        isStreaming: false,
        currentStreamText: '',

        // モデル選択
        provider: 'ollama',
        model: '',
        availableModels: [],

        // 会話
        conversations: [],
        currentConversationId: null,

        // Mem0 & RAG
        mem0Enabled: true,
        ragEnabled: true,

        // サイドバー
        sidebarOpen: true,

        // ── WebSocket ──
        connectWs() {
            const wsUrl = `ws://${location.host}/ws/chat`;
            try {
                this.ws = new WebSocket(wsUrl);
            } catch (e) {
                console.error('WebSocket error:', e);
                this.scheduleReconnect();
                return;
            }

            this.ws.onopen = () => {
                this.connected = true;
                this.reconnectAttempts = 0;
            };

            this.ws.onmessage = (event) => {
                try {
                    this.handleWsMessage(JSON.parse(event.data));
                } catch (e) {
                    console.error('Message parse error:', e);
                }
            };

            this.ws.onclose = () => {
                this.connected = false;
                this.scheduleReconnect();
            };

            this.ws.onerror = (err) => console.error('WebSocket error:', err);
        },

        scheduleReconnect() {
            if (this.reconnectTimer) return;
            const delay = Math.min(1000 * 2 ** this.reconnectAttempts, this.maxReconnectDelay);
            this.reconnectTimer = setTimeout(() => {
                this.reconnectTimer = null;
                this.reconnectAttempts++;
                this.connectWs();
            }, delay);
        },

        handleWsMessage(data) {
            switch (data.type) {
                case 'chunk':
                    this.currentStreamText += data.content || '';
                    this.updateLastAssistantMessage();
                    break;
                case 'done':
                    this.isStreaming = false;
                    if (this.messages.length > 0) {
                        const lastIdx = this.messages.length - 1;
                        const last = this.messages[lastIdx];
                        if (last?.role === 'assistant') {
                            this.messages[lastIdx] = {
                                ...last,
                                provider_label: data.provider_label || '',
                                model: data.model || '',
                                duration_ms: data.duration_ms || 0,
                            };
                        }
                    }
                    if (data.conversation_id) this.currentConversationId = data.conversation_id;
                    this.loadConversations();
                    break;
                case 'error':
                    this.isStreaming = false;
                    this.messages.push({
                        role: 'error',
                        content: data.content || 'Unknown error',
                        timestamp: new Date().toLocaleTimeString('ja-JP'),
                    });
                    break;
                case 'models':
                    this.availableModels = data.models || [];
                    if (this.availableModels.length > 0 && !this.model) {
                        this.model = this.availableModels[0];
                    }
                    break;
            }
        },

        updateLastAssistantMessage() {
            const last = this.messages[this.messages.length - 1];
            if (last?.role === 'assistant') last.content = this.currentStreamText;
        },

        async sendMessage(content) {
            if (!content.trim() || this.isStreaming) return;
            if (!this.connected) {
                alert(Alpine.store('i18n').t('noConnection'));
                return;
            }

            this.messages.push({
                role: 'user',
                content: content.trim(),
                timestamp: new Date().toLocaleTimeString('ja-JP'),
            });

            this.currentStreamText = '';
            this.messages.push({
                role: 'assistant',
                content: '',
                timestamp: new Date().toLocaleTimeString('ja-JP'),
                provider_label: '',
                model: this.model,
                duration_ms: 0,
            });
            this.isStreaming = true;

            this.ws.send(JSON.stringify({
                action: 'chat',
                conversation_id: this.currentConversationId,
                provider: this.provider,
                model: this.model,
                content: content.trim(),
                mem0_enabled: this.mem0Enabled,
                rag_enabled: this.ragEnabled,
            }));
        },

        async loadModels() {
            try {
                const res = await fetch('/api/models');
                if (!res.ok) return;
                const data = await res.json();
                const providerModels = data[this.provider] || [];

                this.availableModels = providerModels.map(m => {
                    if (typeof m === 'string') return { value: m, label: m };
                    const value = m.id || m.name || '';
                    let label = m.name || m.id || '';
                    if (m.description) label += ` — ${m.description}`;
                    else if (m.size) label += ` (${m.size})`;
                    return { value, label };
                }).filter(m => m.value);

                if (this.availableModels.length > 0) {
                    const values = this.availableModels.map(m => m.value);
                    if (!values.includes(this.model)) {
                        this.model = this.availableModels[0].value;
                    }
                }
            } catch (e) {
                console.error('Model load error:', e);
                this.availableModels = [];
            }
        },

        async loadConversations() {
            try {
                const res = await fetch('/api/conversations');
                if (!res.ok) return;
                const data = await res.json();
                this.conversations = Array.isArray(data) ? data : (data.conversations || []);
            } catch (e) {
                console.error('Conversation load error:', e);
            }
        },

        async newConversation() {
            this.currentConversationId = null;
            this.messages = [];
            this.currentStreamText = '';
            this.isStreaming = false;
        },

        async switchConversation(id) {
            try {
                const res = await fetch(`/api/conversations/${id}`);
                if (!res.ok) return;
                const data = await res.json();
                this.currentConversationId = id;
                this.messages = (data.messages || []).map(m => ({
                    role: m.role,
                    content: m.content,
                    timestamp: m.timestamp || '',
                }));
            } catch (e) {
                console.error('Conversation load error:', e);
            }
        },

        async deleteConversation(id) {
            if (!confirm(Alpine.store('i18n').t('deleteConfirm'))) return;
            try {
                const res = await fetch(`/api/conversations/${id}`, { method: 'DELETE' });
                if (!res.ok) return;
                this.conversations = this.conversations.filter(c => c.id !== id);
                if (this.currentConversationId === id) this.newConversation();
            } catch (e) {
                console.error('Conversation delete error:', e);
            }
        },

        init() {
            this.connectWs();
            this.loadModels();
            this.loadConversations();
        },
    });
});

// ── Utilities ──

function renderMarkdown(text) {
    if (!text) return '';
    if (typeof marked === 'undefined') return escapeHtml(text);
    return addCopyButtons(marked.parse(text));
}

function addCopyButtons(html) {
    return html.replace(/<pre><code(.*?)>/g, (_, attrs) =>
        `<pre><button class="copy-btn" onclick="copyCode(this)">Copy</button><code${attrs}>`);
}

function copyCode(btn) {
    const code = btn.nextElementSibling;
    if (!code) return;
    const i18n = Alpine?.store?.('i18n');
    navigator.clipboard.writeText(code.textContent).then(() => {
        btn.textContent = i18n?.t('copied') || 'Copied';
        setTimeout(() => { btn.textContent = i18n?.t('copy') || 'Copy'; }, 1500);
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
}

function scrollToBottom(selector) {
    const el = document.querySelector(selector);
    if (el) requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleDateString('ja-JP', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}
