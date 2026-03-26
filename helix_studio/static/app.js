/* Helix AI Studio — Alpine.js Stores & WebSocket */

document.addEventListener('alpine:init', () => {

    // ── i18n ストア ──────────────────────────────────────
    const TRANSLATIONS = {
        ja: {
            // nav
            chat: 'チャット', pipeline: 'パイプライン', knowledge: 'ナレッジ',
            history: '履歴', settings: '設定',
            // connection
            connected: '接続中', disconnected: '未接続',
            // chat
            send: '送信', newChat: '新しい会話', newConversation: '新規会話',
            deleteConfirm: 'この会話を削除しますか？',
            noConnection: 'サーバーに接続されていません。再接続を待ってください。',
            copied: 'コピー済み', copy: 'コピー',
            subtitle: 'v2.0 — 統合AI開発環境',
            // chat header
            local: 'ローカル',
            cloudApi: 'Cloud API',
            cli: 'CLI',
            openaiCompat: 'OpenAI互換 API',
            noModels: 'モデルなし（設定を確認）',
            // chat body
            startChatTitle: 'AIとの対話を始めましょう',
            startChatDesc: 'Cloud AI とローカル LLM を切り替えながら、自由に対話できます。',
            error: 'エラー',
            seconds: '秒',
            inputPlaceholder: 'メッセージを入力... (Shift+Enter で改行)',
            attachFile: 'ファイルを添付',
            uploading: 'アップロード中...',
            // sidebar
            conversationHistory: '会話履歴',
            noConversations: '会話がありません',
            startNewChat: '新しいチャットを始めましょう',
            untitledConversation: '無題の会話',
            delete: '削除',
            // history
            conversationHistoryTitle: '会話履歴',
            conversationHistoryDesc: '過去の会話を日付順に表示',
            loading: '読み込み中...',
            noHistory: '履歴がありません',
            noHistoryDesc: 'チャットを始めると、ここに会話履歴が表示されます。',
            startChat: 'チャットを始める',
            messages: 'メッセージ',
            deleteConvConfirm: 'この会話を削除しますか？',
            historyLoadError: '履歴読み込みエラー:',
            // knowledge
            qdrantConnected: 'Qdrant 接続中',
            qdrantDisconnected: 'Qdrant 未接続',
            chunks: 'チャンク',
            searchTest: '検索テスト',
            dragDropDocuments: 'ドキュメントをドラッグ&ドロップ',
            clickToSelectFiles: 'またはクリックしてファイルを選択 (.txt, .md, .py, .json など)',
            uploading: 'アップロード中...',
            uploadFailed: 'アップロード失敗',
            uploadError: 'アップロードエラー: ',
            vectorSearchTest: 'ベクトル検索テスト',
            searchQueryPlaceholder: '検索クエリを入力...',
            search: '検索',
            searching: '検索中...',
            registeredDocuments: '登録済みドキュメント',
            noDocuments: 'ドキュメントが登録されていません',
            noDocumentsDesc: 'ファイルをアップロードするとRAG検索が有効になります',
            deleteDocConfirm: 'このドキュメントを削除しますか？',
            // pipeline
            aiPipeline: 'AIパイプライン',
            pipelineDesc: 'Cloud AI で計画 → ローカル LLM で実行 → Cloud AI で検証',
            taskDescription: 'タスクの説明',
            taskPlaceholder: '実行したいタスクを入力してください...',
            step1PlanModel: 'Step1 計画モデル',
            step2ExecModel: 'Step2 実行モデル',
            step3VerifyModel: 'Step3 検証モデル',
            default: 'デフォルト',
            single: '単体',
            crewai: 'CrewAI',
            compatLabel: '互換',
            planStep: '計画',
            execStep: '実行',
            verifyStep: '検証',
            crewAgentConfig: 'CrewAI エージェント構成',
            estimatedVram: '推定VRAM:',
            currentlyUsed: '現在使用中:',
            vramUsage: 'VRAM使用量',
            runPipeline: 'パイプライン実行',
            running: '実行中...',
            statusIdle: '待機中',
            statusRunning: '実行中',
            statusDone: '完了',
            statusError: 'エラー',
            resultPlaceholder: '結果がここに表示されます',
            executionHistory: '実行履歴',
            noExecutionHistory: 'まだ実行履歴がありません',
            pipelineError: 'パイプラインエラー:',
            modelLoadError: 'モデル読み込みエラー:',
            crewTeamLoadError: 'CrewAIチーム読み込みエラー:',
            vramStatusError: 'VRAM状態取得エラー:',
            // settings
            settingsTitle: '設定',
            settingsDesc: 'APIキー、接続先、デフォルトモデルの設定',
            cloudAiSettings: 'Cloud AI 設定',
            claudeApiKey: 'Claude API キー',
            openaiApiKey: 'OpenAI API キー',
            claudeConnTest: 'Claude 接続テスト',
            openaiConnTest: 'OpenAI 接続テスト',
            localAiSettings: 'ローカル AI 設定',
            ollamaUrl: 'Ollama URL',
            openaiCompatUrl: 'OpenAI 互換 API URL',
            openaiCompatKey: 'OpenAI 互換 API キー（任意）',
            ollamaConnTest: 'Ollama 接続テスト',
            compatConnTest: '互換API 接続テスト',
            mem0Settings: 'Mem0 設定（共有記憶）',
            mem0HttpUrl: 'Mem0 HTTP URL',
            userId: 'ユーザー ID',
            autoInjectMemory: '会話に記憶を自動注入',
            mem0ConnTest: 'Mem0 接続テスト',
            ragSettings: 'RAG ナレッジベース設定',
            qdrantUrl: 'Qdrant URL',
            embeddingModel: '埋め込みモデル (Ollama)',
            autoInjectKnowledge: '会話にナレッジを自動注入',
            ragAutoInjectDesc: 'アップロードしたドキュメントのチャンクをベクトル検索し、関連コンテキストをチャットに自動注入します。',
            gpuVramSettings: 'GPU / VRAM 設定',
            gpuVramTotal: 'GPU VRAM 合計 (GB)',
            gpuVramAutoDetect: '0 = 自動検出 (nvidia-smi)',
            gpuVramMultiDesc: 'マルチGPU環境の場合は合計値を入力（例: 96GB + 16GB = 112）。CrewAIのVRAM制限に使用されます。',
            gpuConfigMemo: 'GPU構成メモ',
            mcpSettings: 'MCP サーバー設定',
            helixPilotCmd: 'helix-pilot 起動コマンド',
            helixSandboxCmd: 'helix-sandbox 起動コマンド',
            defaultModels: 'デフォルトモデル',
            cloudDefaultModel: 'Cloud AI デフォルトモデル',
            localDefaultModel: 'ローカル AI デフォルトモデル',
            language: 'Language / 言語',
            saveSettings: '設定を保存',
            saving: '保存中...',
            saved: '保存しました',
            saveFailed: '保存に失敗しました',
            connectionError: '接続エラー',
            testing: 'テスト中...',
        },
        en: {
            // nav
            chat: 'Chat', pipeline: 'Pipeline', knowledge: 'Knowledge',
            history: 'History', settings: 'Settings',
            // connection
            connected: 'Connected', disconnected: 'Disconnected',
            // chat
            send: 'Send', newChat: 'New Chat', newConversation: 'New Conversation',
            deleteConfirm: 'Delete this conversation?',
            noConnection: 'Not connected to server. Please wait for reconnection.',
            copied: 'Copied', copy: 'Copy',
            subtitle: 'v2.0 — Integrated AI Development Environment',
            // chat header
            local: 'Local',
            cloudApi: 'Cloud API',
            cli: 'CLI',
            openaiCompat: 'OpenAI Compatible API',
            noModels: 'No models (check settings)',
            // chat body
            startChatTitle: 'Start a conversation with AI',
            startChatDesc: 'Switch between Cloud AI and local LLM to chat freely.',
            error: 'Error',
            seconds: 's',
            inputPlaceholder: 'Type a message... (Shift+Enter for newline)',
            attachFile: 'Attach file',
            uploading: 'Uploading...',
            // sidebar
            conversationHistory: 'Conversations',
            noConversations: 'No conversations',
            startNewChat: 'Start a new chat',
            untitledConversation: 'Untitled conversation',
            delete: 'Delete',
            // history
            conversationHistoryTitle: 'Conversation History',
            conversationHistoryDesc: 'Conversations sorted by date',
            loading: 'Loading...',
            noHistory: 'No history',
            noHistoryDesc: 'Start a chat and your conversation history will appear here.',
            startChat: 'Start a Chat',
            messages: 'messages',
            deleteConvConfirm: 'Delete this conversation?',
            historyLoadError: 'History load error:',
            // knowledge
            qdrantConnected: 'Qdrant Connected',
            qdrantDisconnected: 'Qdrant Disconnected',
            chunks: 'chunks',
            searchTest: 'Search Test',
            dragDropDocuments: 'Drag & drop documents here',
            clickToSelectFiles: 'or click to select files (.txt, .md, .py, .json, etc.)',
            uploading: 'Uploading...',
            uploadFailed: 'Upload failed',
            uploadError: 'Upload error: ',
            vectorSearchTest: 'Vector Search Test',
            searchQueryPlaceholder: 'Enter search query...',
            search: 'Search',
            searching: 'Searching...',
            registeredDocuments: 'Registered Documents',
            noDocuments: 'No documents registered',
            noDocumentsDesc: 'Upload files to enable RAG search',
            deleteDocConfirm: 'Delete this document?',
            // pipeline
            aiPipeline: 'AI Pipeline',
            pipelineDesc: 'Plan with Cloud AI → Execute with local LLM → Verify with Cloud AI',
            taskDescription: 'Task Description',
            taskPlaceholder: 'Enter the task you want to execute...',
            step1PlanModel: 'Step 1: Plan Model',
            step2ExecModel: 'Step 2: Exec Model',
            step3VerifyModel: 'Step 3: Verify Model',
            default: 'Default',
            single: 'Single',
            crewai: 'CrewAI',
            compatLabel: 'Compat',
            planStep: 'Plan',
            execStep: 'Execute',
            verifyStep: 'Verify',
            crewAgentConfig: 'CrewAI Agent Configuration',
            estimatedVram: 'Est. VRAM:',
            currentlyUsed: 'Currently used:',
            vramUsage: 'VRAM Usage',
            runPipeline: 'Run Pipeline',
            running: 'Running...',
            statusIdle: 'Idle',
            statusRunning: 'Running',
            statusDone: 'Done',
            statusError: 'Error',
            resultPlaceholder: 'Results will appear here',
            executionHistory: 'Execution History',
            noExecutionHistory: 'No execution history yet',
            pipelineError: 'Pipeline error:',
            modelLoadError: 'Model load error:',
            crewTeamLoadError: 'CrewAI team load error:',
            vramStatusError: 'VRAM status error:',
            // settings
            settingsTitle: 'Settings',
            settingsDesc: 'API keys, connections, and default model settings',
            cloudAiSettings: 'Cloud AI Settings',
            claudeApiKey: 'Claude API Key',
            openaiApiKey: 'OpenAI API Key',
            claudeConnTest: 'Claude Connection Test',
            openaiConnTest: 'OpenAI Connection Test',
            localAiSettings: 'Local AI Settings',
            ollamaUrl: 'Ollama URL',
            openaiCompatUrl: 'OpenAI Compatible API URL',
            openaiCompatKey: 'OpenAI Compatible API Key (optional)',
            ollamaConnTest: 'Ollama Connection Test',
            compatConnTest: 'Compat API Connection Test',
            mem0Settings: 'Mem0 Settings (Shared Memory)',
            mem0HttpUrl: 'Mem0 HTTP URL',
            userId: 'User ID',
            autoInjectMemory: 'Auto-inject memory into conversations',
            mem0ConnTest: 'Mem0 Connection Test',
            ragSettings: 'RAG Knowledge Base Settings',
            qdrantUrl: 'Qdrant URL',
            embeddingModel: 'Embedding Model (Ollama)',
            autoInjectKnowledge: 'Auto-inject knowledge into conversations',
            ragAutoInjectDesc: 'Vector-searches uploaded document chunks and auto-injects relevant context into chat.',
            gpuVramSettings: 'GPU / VRAM Settings',
            gpuVramTotal: 'GPU VRAM Total (GB)',
            gpuVramAutoDetect: '0 = Auto-detect (nvidia-smi)',
            gpuVramMultiDesc: 'For multi-GPU setups, enter total (e.g., 96GB + 16GB = 112). Used for CrewAI VRAM limits.',
            gpuConfigMemo: 'GPU Configuration Memo',
            mcpSettings: 'MCP Server Settings',
            helixPilotCmd: 'helix-pilot Launch Command',
            helixSandboxCmd: 'helix-sandbox Launch Command',
            defaultModels: 'Default Models',
            cloudDefaultModel: 'Cloud AI Default Model',
            localDefaultModel: 'Local AI Default Model',
            language: 'Language / 言語',
            saveSettings: 'Save Settings',
            saving: 'Saving...',
            saved: 'Saved',
            saveFailed: 'Failed to save',
            connectionError: 'Connection error',
            testing: 'Testing...',
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
                        timestamp: new Date().toLocaleTimeString(Alpine.store('i18n').lang === 'en' ? 'en-US' : 'ja-JP'),
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

            const locale = Alpine.store('i18n').lang === 'en' ? 'en-US' : 'ja-JP';
            this.messages.push({
                role: 'user',
                content: content.trim(),
                timestamp: new Date().toLocaleTimeString(locale),
            });

            this.currentStreamText = '';
            this.messages.push({
                role: 'assistant',
                content: '',
                timestamp: new Date().toLocaleTimeString(locale),
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
    const lang = Alpine?.store?.('i18n')?.lang || 'ja';
    const locale = lang === 'en' ? 'en-US' : 'ja-JP';
    return d.toLocaleDateString(locale, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}
