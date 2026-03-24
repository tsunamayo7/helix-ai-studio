/* Helix AI Studio — Alpine.js ストア & WebSocket 管理 */

document.addEventListener('alpine:init', () => {

    // Markdown レンダラー設定
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            highlight: function (code, lang) {
                if (typeof hljs !== 'undefined' && lang && hljs.getLanguage(lang)) {
                    return hljs.highlight(code, { language: lang }).value;
                }
                return typeof hljs !== 'undefined' ? hljs.highlightAuto(code).value : code;
            },
            breaks: true,
            gfm: true,
        });
    }

    Alpine.store('app', {
        // ── WebSocket ──
        ws: null,
        connected: false,
        reconnectAttempts: 0,
        maxReconnectDelay: 30000,
        reconnectTimer: null,

        // ── チャット状態 ──
        messages: [],
        isStreaming: false,
        currentStreamText: '',

        // ── モデル選択 ──
        provider: 'ollama',
        model: '',
        availableModels: [],

        // ── 会話 ──
        conversations: [],
        currentConversationId: null,

        // ── Mem0 ──
        mem0Enabled: true,

        // ── サイドバー ──
        sidebarOpen: true,

        // ── WebSocket 接続 ──
        connectWs() {
            const wsUrl = `ws://${location.host}/ws/chat`;
            try {
                this.ws = new WebSocket(wsUrl);
            } catch (e) {
                console.error('WebSocket 接続エラー:', e);
                this.scheduleReconnect();
                return;
            }

            this.ws.onopen = () => {
                this.connected = true;
                this.reconnectAttempts = 0;
                console.log('WebSocket 接続完了');
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleWsMessage(data);
                } catch (e) {
                    console.error('メッセージ解析エラー:', e);
                }
            };

            this.ws.onclose = () => {
                this.connected = false;
                console.log('WebSocket 切断');
                this.scheduleReconnect();
            };

            this.ws.onerror = (err) => {
                console.error('WebSocket エラー:', err);
            };
        },

        scheduleReconnect() {
            if (this.reconnectTimer) return;
            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), this.maxReconnectDelay);
            console.log(`${delay}ms 後に再接続...`);
            this.reconnectTimer = setTimeout(() => {
                this.reconnectTimer = null;
                this.reconnectAttempts++;
                this.connectWs();
            }, delay);
        },

        // ── メッセージ処理 ──
        handleWsMessage(data) {
            switch (data.type) {
                case 'chunk':
                    this.currentStreamText += data.content || '';
                    this.updateLastAssistantMessage();
                    break;
                case 'done':
                    this.isStreaming = false;
                    if (data.conversation_id) {
                        this.currentConversationId = data.conversation_id;
                    }
                    this.loadConversations();
                    break;
                case 'error':
                    this.isStreaming = false;
                    this.messages.push({
                        role: 'error',
                        content: data.content || '不明なエラーが発生しました',
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
            if (last && last.role === 'assistant') {
                last.content = this.currentStreamText;
            }
        },

        // ── メッセージ送信 ──
        async sendMessage(content) {
            if (!content.trim() || this.isStreaming) return;
            if (!this.connected) {
                alert('サーバーに接続されていません。再接続を待ってください。');
                return;
            }

            // ユーザーメッセージ追加
            this.messages.push({
                role: 'user',
                content: content.trim(),
                timestamp: new Date().toLocaleTimeString('ja-JP'),
            });

            // アシスタントプレースホルダー追加
            this.currentStreamText = '';
            this.messages.push({
                role: 'assistant',
                content: '',
                timestamp: new Date().toLocaleTimeString('ja-JP'),
            });
            this.isStreaming = true;

            // WebSocket 送信
            this.ws.send(JSON.stringify({
                action: 'chat',
                conversation_id: this.currentConversationId,
                provider: this.provider,
                model: this.model,
                content: content.trim(),
                mem0_enabled: this.mem0Enabled,
            }));
        },

        // ── モデル一覧読み込み ──
        async loadModels() {
            try {
                const res = await fetch('/api/models');
                if (res.ok) {
                    const data = await res.json();
                    // プロバイダに対応するモデル一覧を取得
                    const providerModels = data[this.provider] || [];
                    this.availableModels = providerModels.map(m =>
                        typeof m === 'string' ? m : (m.name || m.id || '')
                    ).filter(n => n);
                    if (this.availableModels.length > 0 && !this.availableModels.includes(this.model)) {
                        this.model = this.availableModels[0];
                    }
                }
            } catch (e) {
                console.error('モデル読み込みエラー:', e);
                this.availableModels = [];
            }
        },

        // ── 会話一覧読み込み ──
        async loadConversations() {
            try {
                const res = await fetch('/api/conversations');
                if (res.ok) {
                    const data = await res.json();
                    this.conversations = data.conversations || [];
                }
            } catch (e) {
                console.error('会話一覧読み込みエラー:', e);
            }
        },

        // ── 新規会話 ──
        async newConversation() {
            this.currentConversationId = null;
            this.messages = [];
            this.currentStreamText = '';
            this.isStreaming = false;
        },

        // ── 会話切替 ──
        async switchConversation(id) {
            try {
                const res = await fetch(`/api/conversations/${id}`);
                if (res.ok) {
                    const data = await res.json();
                    this.currentConversationId = id;
                    this.messages = (data.messages || []).map(m => ({
                        role: m.role,
                        content: m.content,
                        timestamp: m.timestamp || '',
                    }));
                }
            } catch (e) {
                console.error('会話読み込みエラー:', e);
            }
        },

        // ── 会話削除 ──
        async deleteConversation(id) {
            if (!confirm('この会話を削除しますか？')) return;
            try {
                const res = await fetch(`/api/conversations/${id}`, { method: 'DELETE' });
                if (res.ok) {
                    this.conversations = this.conversations.filter(c => c.id !== id);
                    if (this.currentConversationId === id) {
                        this.newConversation();
                    }
                }
            } catch (e) {
                console.error('会話削除エラー:', e);
            }
        },

        // ── 初期化 ──
        init() {
            this.connectWs();
            this.loadModels();
            this.loadConversations();
        },
    });
});

// ── ユーティリティ ──

function renderMarkdown(text) {
    if (!text) return '';
    if (typeof marked === 'undefined') return escapeHtml(text);
    const html = marked.parse(text);
    return addCopyButtons(html);
}

function addCopyButtons(html) {
    return html.replace(/<pre><code(.*?)>/g, (match, attrs) => {
        return `<pre><button class="copy-btn" onclick="copyCode(this)">コピー</button><code${attrs}>`;
    });
}

function copyCode(btn) {
    const code = btn.nextElementSibling;
    if (code) {
        navigator.clipboard.writeText(code.textContent).then(() => {
            btn.textContent = 'コピー済み';
            setTimeout(() => { btn.textContent = 'コピー'; }, 1500);
        });
    }
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
    if (el) {
        requestAnimationFrame(() => {
            el.scrollTop = el.scrollHeight;
        });
    }
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleDateString('ja-JP', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}
