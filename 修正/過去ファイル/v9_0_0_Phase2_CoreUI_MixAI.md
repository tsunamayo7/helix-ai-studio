# Helix AI Studio v9.0.0 Phase 2: コアUI + mixAI対応
## 実装指示書（Claude Code CLI用）

**作成日**: 2026-02-15
**対象**: Phase 2 — iOS UIバグ修正 + mixAI WebSocket + タブ切替 + ファイルブラウザ
**想定期間**: 3-4日
**前提**: Phase 1 完了済み（soloAI WebSocket動作確認済み）
**原則**: 既存PyQt6コードの変更ゼロ。Phase 1のファイルへの修正 + 新規ファイル追加。

---

## 1. Phase 2 の目標

Phase 2完了時に達成されるべき状態:

1. **[バグ修正]** iOSビューポート問題の解消（ヘッダー〜入力バーが1画面に収まる）
2. **[コア]** soloAI / mixAI のタブ切替UIが動作
3. **[コア]** mixAIの3Phase実行がWebSocketでリアルタイム表示（進捗バー + ローカルLLMステータス）
4. **[コア]** ファイルブラウザでプロジェクトディレクトリのファイル一覧/選択
5. **[改善]** モバイルレスポンシブの全体的な改善

---

## 2. バグ修正: iOSビューポート問題

### 2.1 問題

iPhoneのSafariで、ヘッダー→チャットエリア→入力バーが1画面に収まらず、スクロールが必要になる。原因はiOS Safariのビューポート計算（`100vh`がアドレスバーを含むため実際の表示領域より大きい）。

### 2.2 修正対象

**`frontend/src/App.jsx`** — ルートコンテナのスタイル修正

```jsx
// 修正前
<div className="flex flex-col h-screen bg-gray-950">

// 修正後: dvhユニット + フォールバック
<div className="flex flex-col bg-gray-950" style={{ height: '100dvh' }}>
```

**`frontend/src/styles/globals.css`** — ビューポート修正追加

```css
/* iOS Safari ビューポート修正 */
html, body, #root {
  height: 100dvh;
  height: -webkit-fill-available;
  overflow: hidden;
}

/* フォールバック（dvh非対応ブラウザ） */
@supports not (height: 100dvh) {
  html, body, #root {
    height: 100vh;
  }
}
```

**`frontend/index.html`** — viewport meta修正

```html
<!-- 修正前 -->
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />

<!-- 修正後: interactive-widget=resizes-content追加 -->
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, interactive-widget=resizes-content" />
```

**`frontend/src/components/ChatView.jsx`** — スクロールエリア修正

```jsx
// 修正前
<main className="flex-1 overflow-y-auto px-4 py-4 space-y-4">

// 修正後: min-h-0を追加（flex子要素のオーバーフロー修正）
<main className="flex-1 overflow-y-auto px-4 py-4 space-y-4 min-h-0">
```

**`frontend/src/components/InputBar.jsx`** — safe-area改善

```jsx
// 修正前
<div className="border-t border-gray-800 bg-gray-900 px-4 py-3 safe-area-inset-bottom">

// 修正後: flexの縮小を防止
<div className="shrink-0 border-t border-gray-800 bg-gray-900 px-4 py-3 safe-area-inset-bottom">
```

---

## 3. タブ切替UI

### 3.1 概要

soloAI / mixAI を切り替えるタブバーをヘッダーの下に配置。

### 3.2 新規コンポーネント: `frontend/src/components/TabBar.jsx`

```jsx
import React from 'react';

const TABS = [
  { id: 'soloAI', label: 'soloAI', desc: 'Claude直接対話' },
  { id: 'mixAI', label: 'mixAI', desc: '3Phase統合実行' },
];

export default function TabBar({ activeTab, onTabChange }) {
  return (
    <div className="shrink-0 flex border-b border-gray-800 bg-gray-900">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={`flex-1 py-2.5 text-center transition-colors relative ${
            activeTab === tab.id
              ? 'text-emerald-400'
              : 'text-gray-500 hover:text-gray-300'
          }`}
        >
          <span className="text-sm font-medium">{tab.label}</span>
          <span className="block text-[10px] mt-0.5 opacity-60">{tab.desc}</span>
          {activeTab === tab.id && (
            <div className="absolute bottom-0 left-4 right-4 h-0.5 bg-emerald-400 rounded-full" />
          )}
        </button>
      ))}
    </div>
  );
}
```

### 3.3 App.jsx の修正

```jsx
import TabBar from './components/TabBar';
import MixAIView from './components/MixAIView';

export default function App() {
  const { token, isAuthenticated, login, logout } = useAuth();
  const [activeTab, setActiveTab] = useState('soloAI');
  const soloAI = useWebSocket(token, 'solo');
  const mixAI = useWebSocket(token, 'mix');  // Phase 2で追加

  if (!isAuthenticated) {
    return <LoginScreen onLogin={login} />;
  }

  // アクティブタブに応じてフック切替
  const current = activeTab === 'soloAI' ? soloAI : mixAI;

  return (
    <div className="flex flex-col bg-gray-950" style={{ height: '100dvh' }}>
      <header className="shrink-0 flex items-center justify-between px-4 py-3 bg-gray-900 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-emerald-600 flex items-center justify-center text-white font-bold text-sm">H</div>
          <span className="text-lg font-semibold text-gray-100">Helix AI Studio</span>
        </div>
        <StatusIndicator status={current.status} />
      </header>

      <TabBar activeTab={activeTab} onTabChange={setActiveTab} />

      {activeTab === 'soloAI' ? (
        <>
          <ChatView messages={soloAI.messages} isExecuting={soloAI.isExecuting} />
          <InputBar onSend={soloAI.sendMessage} disabled={soloAI.isExecuting} />
        </>
      ) : (
        <MixAIView mixAI={mixAI} />
      )}
    </div>
  );
}
```

---

## 4. mixAI WebSocket対応

### 4.1 バックエンド: WebSocketエンドポイント追加

**`src/web/server.py`** に `/ws/mix` エンドポイントを追加:

```python
@app.websocket("/ws/mix")
async def websocket_mix(websocket: WebSocket, token: str = Query(...)):
    """
    mixAI WebSocketエンドポイント。
    3Phase実行の進捗をリアルタイム配信。

    クライアント → サーバー:
      {"action": "execute", "prompt": "...", "model_id": "...",
       "model_assignments": {...}, "project_dir": "...", "attached_files": [...]}
      {"action": "cancel"}

    サーバー → クライアント:
      {"type": "phase_changed", "phase": 1, "description": "Phase 1: Claude計画立案中..."}
      {"type": "streaming", "chunk": "...", "done": false}
      {"type": "llm_started", "category": "coding", "model": "devstral-2:123b"}
      {"type": "llm_finished", "category": "coding", "success": true, "elapsed": 12.5}
      {"type": "phase2_progress", "completed": 2, "total": 5}
      {"type": "streaming", "chunk": "...", "done": true}  // 最終回答
      {"type": "error", "error": "..."}
    """
    # JWT認証（soloAIと同じ）
    client_ip = websocket.client.host
    if not auth_manager.check_ip(client_ip):
        await websocket.close(code=4003, reason="IP not allowed")
        return

    payload = auth_manager.verify_token(token)
    if payload is None:
        await websocket.close(code=4001, reason="Invalid token")
        return

    client_id = str(uuid.uuid4())
    connected = await ws_manager.connect(websocket, client_id)
    if not connected:
        await websocket.close(code=4029, reason="Too many connections")
        return

    try:
        await ws_manager.send_status(client_id, "connected", "mixAI WebSocket ready")

        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "ping":
                await ws_manager.send_to(client_id, {"type": "pong"})
            elif action == "execute":
                await _handle_mix_execute(client_id, data)
            elif action == "cancel":
                await ws_manager.send_status(client_id, "cancelled", "キャンセルは現在未対応です")
            else:
                await ws_manager.send_error(client_id, f"Unknown action: {action}")

    except WebSocketDisconnect:
        logger.info(f"mixAI WebSocket disconnected: {client_id}")
    except Exception as e:
        logger.error(f"mixAI WebSocket error: {e}")
    finally:
        await ws_manager.disconnect(client_id)
```

### 4.2 mixAI実行ハンドラ

```python
async def _handle_mix_execute(client_id: str, data: dict):
    """
    mixAI 3Phase実行ハンドラ。

    MixAIOrchestratorはQThread(PyQt6)前提のため、Web版では
    直接Claude CLIとOllama APIを呼び出す軽量版を実装する。

    Phase 1: Claude CLI → 計画JSON + claude_answer
    Phase 2: Ollama API → ローカルLLM順次実行
    Phase 3: Claude CLI → 比較統合 → 最終回答

    重要: MixAIOrchestratorのコードは参照のみで変更しない。
    同等ロジックをasyncioベースで再実装する。
    """
    from ..utils.subprocess_utils import run_hidden
    import httpx

    prompt = data.get("prompt", "")
    model_id = data.get("model_id", "claude-opus-4-6")
    model_assignments = data.get("model_assignments", {})
    project_dir = data.get("project_dir", "")
    attached_files = data.get("attached_files", [])
    timeout = data.get("timeout", 600)

    if not prompt:
        await ws_manager.send_error(client_id, "Prompt is empty")
        return

    ws_manager.set_active_task(client_id, "mixAI")

    try:
        # ═══ Phase 1: Claude計画立案 ═══
        await ws_manager.send_to(client_id, {
            "type": "phase_changed",
            "phase": 1,
            "description": "Phase 1: Claude計画立案中...",
        })

        phase1_result = await _run_claude_cli_async(
            prompt=_build_phase1_prompt(prompt),
            model_id=model_id,
            project_dir=project_dir,
            timeout=timeout,
        )

        # Phase 1結果パース
        claude_answer = phase1_result.get("claude_answer", "")
        llm_instructions = phase1_result.get("local_llm_instructions", {})
        complexity = phase1_result.get("complexity", "low")
        skip_phase2 = phase1_result.get("skip_phase2", False)

        # Phase 1のClaude回答をストリーミング送信
        if claude_answer:
            await ws_manager.send_to(client_id, {
                "type": "streaming",
                "chunk": f"**[Phase 1 Claude回答]**\n{claude_answer[:500]}...\n\n",
                "done": False,
            })

        # complexityがlowまたはskip_phase2の場合、Phase 2-3スキップ
        if skip_phase2 or complexity == "low":
            await ws_manager.send_streaming(client_id, claude_answer, done=True)
            await ws_manager.send_status(client_id, "completed", "Phase 2-3スキップ（低複雑度）")
            return

        # ═══ Phase 2: ローカルLLM順次実行 ═══
        await ws_manager.send_to(client_id, {
            "type": "phase_changed",
            "phase": 2,
            "description": "Phase 2: ローカルLLM順次実行中...",
        })

        tasks = _build_phase2_tasks(llm_instructions, model_assignments)
        phase2_results = []
        total_tasks = len(tasks)

        for i, task in enumerate(tasks):
            # LLM開始通知
            await ws_manager.send_to(client_id, {
                "type": "llm_started",
                "category": task["category"],
                "model": task["model"],
            })

            # Ollama API呼び出し
            import time as _time
            start = _time.time()
            try:
                result = await _run_ollama_async(
                    model=task["model"],
                    prompt=task["prompt"],
                    timeout=task.get("timeout", 300),
                )
                elapsed = _time.time() - start
                phase2_results.append({
                    "category": task["category"],
                    "model": task["model"],
                    "response": result,
                    "success": True,
                    "elapsed": elapsed,
                })

                await ws_manager.send_to(client_id, {
                    "type": "llm_finished",
                    "category": task["category"],
                    "success": True,
                    "elapsed": round(elapsed, 1),
                })
            except Exception as e:
                elapsed = _time.time() - start
                phase2_results.append({
                    "category": task["category"],
                    "model": task["model"],
                    "response": str(e),
                    "success": False,
                    "elapsed": elapsed,
                })
                await ws_manager.send_to(client_id, {
                    "type": "llm_finished",
                    "category": task["category"],
                    "success": False,
                    "elapsed": round(elapsed, 1),
                })

            # 進捗通知
            await ws_manager.send_to(client_id, {
                "type": "phase2_progress",
                "completed": i + 1,
                "total": total_tasks,
            })

        # ═══ Phase 3: Claude比較統合 ═══
        await ws_manager.send_to(client_id, {
            "type": "phase_changed",
            "phase": 3,
            "description": "Phase 3: Claude比較統合中...",
        })

        phase3_prompt = _build_phase3_prompt(prompt, claude_answer, phase2_results)
        phase3_result = await _run_claude_cli_async(
            prompt=phase3_prompt,
            model_id=model_id,
            project_dir=project_dir,
            timeout=timeout,
        )

        # 最終回答抽出
        if isinstance(phase3_result, dict):
            final_answer = phase3_result.get("final_answer", str(phase3_result))
        else:
            final_answer = str(phase3_result)

        await ws_manager.send_streaming(client_id, final_answer, done=True)
        await ws_manager.send_status(client_id, "completed", "3Phase実行完了")

    except Exception as e:
        await ws_manager.send_error(client_id, f"mixAI execution error: {str(e)}")
    finally:
        ws_manager.set_active_task(client_id, None)
```

### 4.3 ヘルパー関数（server.pyに追加）

```python
async def _run_claude_cli_async(prompt: str, model_id: str,
                                  project_dir: str = "", timeout: int = 600) -> dict:
    """Claude CLIを非同期で実行"""
    from ..utils.subprocess_utils import run_hidden

    cmd = ["claude", "-p", "--output-format", "json", "--model", model_id,
           "--dangerously-skip-permissions"]

    run_cwd = project_dir if project_dir and os.path.isdir(project_dir) else None

    result = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: run_hidden(
            cmd, input=prompt, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=timeout,
            env={**os.environ, "FORCE_COLOR": "0", "PYTHONIOENCODING": "utf-8"},
            cwd=run_cwd,
        )
    )

    stdout = result.stdout or ""
    if result.returncode == 0:
        try:
            data = json.loads(stdout)
            text = data.get("result", stdout)
        except json.JSONDecodeError:
            text = stdout.strip()

        # JSON構造の抽出を試行
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except (json.JSONDecodeError, ValueError):
            pass

        return {"claude_answer": text, "complexity": "low", "skip_phase2": True}
    else:
        raise RuntimeError(f"Claude CLI error (code {result.returncode})")


async def _run_ollama_async(model: str, prompt: str,
                              timeout: int = 300, host: str = "http://localhost:11434") -> str:
    """Ollama APIを非同期で呼び出し"""
    import httpx

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
        resp = await client.post(
            f"{host}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
        )
        resp.raise_for_status()
        return resp.json().get("response", "")


def _build_phase1_prompt(user_prompt: str) -> str:
    """Phase 1用プロンプト構築（MixAIOrchestratorの_execute_phase1相当）"""
    return f"""ユーザーの質問に対して、以下の2つを提供してください:

1. あなた自身の回答 (claude_answer)
2. ローカルLLMへの指示 (local_llm_instructions)

JSON形式で出力してください:
{{
  "claude_answer": "あなたの直接回答",
  "complexity": "low|medium|high",
  "skip_phase2": false,
  "local_llm_instructions": {{
    "coding": {{"skip": false, "prompt": "コーディング観点での分析指示", "expected_output": "コード例", "timeout_seconds": 300}},
    "research": {{"skip": false, "prompt": "調査観点での分析指示", "expected_output": "調査結果", "timeout_seconds": 300}},
    "reasoning": {{"skip": false, "prompt": "推論観点での分析指示", "expected_output": "推論結果", "timeout_seconds": 300}}
  }}
}}

complexity=lowの場合はskip_phase2=trueとしてください。

ユーザーの質問:
{user_prompt}"""


def _build_phase2_tasks(llm_instructions: dict, model_assignments: dict) -> list:
    """Phase 2タスクリスト構築"""
    tasks = []
    for category, spec in llm_instructions.items():
        if isinstance(spec, dict) and not spec.get("skip", True):
            model = model_assignments.get(category)
            if not model:
                continue
            prompt = spec.get("prompt", "").strip()
            if not prompt:
                continue
            tasks.append({
                "category": category,
                "model": model,
                "prompt": prompt,
                "timeout": spec.get("timeout_seconds", 300),
            })
    return tasks


def _build_phase3_prompt(user_prompt: str, claude_answer: str,
                          phase2_results: list) -> str:
    """Phase 3用プロンプト構築"""
    results_text = ""
    for r in phase2_results:
        if r["success"]:
            results_text += f"\n### {r['category']} ({r['model']})\n{r['response'][:5000]}\n"

    return f"""以下の情報を統合して、最高品質の最終回答を作成してください。

## ユーザーの質問
{user_prompt}

## Phase 1 Claude回答
{claude_answer[:8000]}

## Phase 2 ローカルLLM結果
{results_text}

## 指示
全ての情報を統合し、最終回答をJSON形式で出力してください:
{{"final_answer": "統合された最終回答"}}"""
```

### 4.4 依存パッケージ追加

```bash
pip install httpx --break-system-packages
```

---

## 5. フロントエンド: mixAIビュー

### 5.1 `frontend/src/hooks/useWebSocket.js` の修正

WebSocketフックをタブ対応に拡張（endpointパラメータ追加）:

```javascript
// 修正: useWebSocket(token) → useWebSocket(token, endpoint)
export function useWebSocket(token, endpoint = 'solo') {
  // ...
  // WebSocket URLを動的に構築
  const wsUrl = `${protocol}//${host}/ws/${endpoint}?token=${token}`;
  // ...

  // mixAI用の追加ステート
  const [phaseInfo, setPhaseInfo] = useState({ phase: 0, description: '' });
  const [llmStatus, setLlmStatus] = useState([]);  // [{category, model, status, elapsed}]
  const [phase2Progress, setPhase2Progress] = useState({ completed: 0, total: 0 });

  // handleMessage拡張
  function handleMessage(data) {
    switch (data.type) {
      // ... 既存のstreaming/status/error/pong

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
    }
  }

  // mixAI用送信関数
  const sendMixMessage = useCallback((prompt, options = {}) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    setMessages(prev => [...prev, { role: 'user', content: prompt }]);
    setIsExecuting(true);
    setPhaseInfo({ phase: 0, description: '' });
    setLlmStatus([]);
    setPhase2Progress({ completed: 0, total: 0 });

    wsRef.current.send(JSON.stringify({
      action: 'execute',
      prompt,
      model_id: options.modelId || 'claude-opus-4-6',
      model_assignments: options.modelAssignments || {},
      project_dir: options.projectDir || '',
      attached_files: options.attachedFiles || [],
      timeout: options.timeout || 600,
    }));
  }, []);

  return {
    status, messages, sendMessage, sendMixMessage, isExecuting,
    phaseInfo, llmStatus, phase2Progress,  // mixAI用追加
  };
}
```

### 5.2 新規コンポーネント: `frontend/src/components/MixAIView.jsx`

```jsx
import React from 'react';
import ChatView from './ChatView';
import InputBar from './InputBar';
import PhaseIndicator from './PhaseIndicator';
import LLMStatusPanel from './LLMStatusPanel';

export default function MixAIView({ mixAI }) {
  const { messages, sendMixMessage, isExecuting, phaseInfo, llmStatus, phase2Progress } = mixAI;

  return (
    <>
      {/* Phase進捗表示（実行中のみ表示） */}
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

      {/* チャットエリア */}
      <ChatView messages={messages} isExecuting={isExecuting} />

      {/* 入力バー */}
      <InputBar
        onSend={(prompt) => sendMixMessage(prompt, {
          modelAssignments: {
            coding: "devstral-2:123b",
            research: "command-a:latest",
            reasoning: "nemotron-3-nano:30b",
          },
        })}
        disabled={isExecuting}
        placeholder="mixAI: 3Phase統合実行 (Ctrl+Enter で送信)"
      />
    </>
  );
}
```

### 5.3 新規コンポーネント: `frontend/src/components/PhaseIndicator.jsx`

```jsx
import React from 'react';

const PHASES = [
  { id: 1, label: 'P1', name: 'Claude計画' },
  { id: 2, label: 'P2', name: 'ローカルLLM' },
  { id: 3, label: 'P3', name: 'Claude統合' },
];

export default function PhaseIndicator({ phase, description }) {
  return (
    <div className="flex items-center gap-2">
      {PHASES.map((p) => (
        <div key={p.id} className="flex items-center gap-1">
          <div
            className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
              phase === p.id
                ? 'bg-emerald-500 text-white animate-pulse'
                : phase > p.id
                ? 'bg-emerald-700 text-emerald-200'
                : 'bg-gray-700 text-gray-500'
            }`}
          >
            {phase > p.id ? '✓' : p.label}
          </div>
          <span className={`text-xs hidden sm:inline ${
            phase === p.id ? 'text-emerald-400' : 'text-gray-500'
          }`}>
            {p.name}
          </span>
          {p.id < 3 && <div className="w-4 h-px bg-gray-700" />}
        </div>
      ))}
      {description && (
        <span className="ml-2 text-xs text-gray-400 truncate">{description}</span>
      )}
    </div>
  );
}
```

### 5.4 新規コンポーネント: `frontend/src/components/LLMStatusPanel.jsx`

```jsx
import React from 'react';

export default function LLMStatusPanel({ llmStatus, progress }) {
  return (
    <div className="mt-2 space-y-1">
      {/* プログレスバー */}
      <div className="flex items-center gap-2">
        <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-emerald-500 rounded-full transition-all duration-500"
            style={{ width: progress.total ? `${(progress.completed / progress.total) * 100}%` : '0%' }}
          />
        </div>
        <span className="text-xs text-gray-400 shrink-0">
          {progress.completed}/{progress.total}
        </span>
      </div>

      {/* LLMステータス一覧 */}
      <div className="flex flex-wrap gap-1">
        {llmStatus.map((s, i) => (
          <div
            key={i}
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] ${
              s.status === 'running'
                ? 'bg-amber-900/50 text-amber-300'
                : s.status === 'done'
                ? 'bg-emerald-900/50 text-emerald-300'
                : 'bg-red-900/50 text-red-300'
            }`}
          >
            {s.status === 'running' && <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />}
            {s.status === 'done' && <span>✓</span>}
            {s.status === 'error' && <span>✗</span>}
            <span>{s.category}</span>
            {s.elapsed > 0 && <span className="opacity-60">{s.elapsed}s</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## 6. ファイルブラウザAPI

### 6.1 バックエンド: `src/web/api_routes.py` に追加

```python
# ファイルブラウザ用

ALLOWED_EXTENSIONS = {'.py', '.js', '.jsx', '.ts', '.tsx', '.md', '.txt',
                       '.json', '.yaml', '.yml', '.toml', '.cfg', '.ini',
                       '.html', '.css', '.sql', '.sh', '.bat', '.ps1',
                       '.csv', '.xml', '.env', '.gitignore', '.dockerfile'}
MAX_BROWSE_DEPTH = 3
EXCLUDED_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv',
                  '.mypy_cache', '.pytest_cache', 'dist', 'build', '.egg-info'}


class FileItem(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int = 0
    extension: str = ""


@router.get("/api/files/browse", response_model=list[FileItem])
async def browse_files(
    dir_path: str = "",
    payload: dict = Depends(verify_jwt),
):
    """
    ディレクトリ内のファイル一覧を取得。
    セキュリティ: パストラバーサル防止 + ホワイトリスト拡張子のみ。
    """
    # config/config.jsonからproject_dirを取得
    project_dir = _get_project_dir()
    if not project_dir:
        raise HTTPException(status_code=400, detail="Project directory not configured")

    # パストラバーサル防止
    if dir_path:
        target = Path(project_dir) / dir_path
        try:
            target.resolve().relative_to(Path(project_dir).resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="Path traversal detected")
    else:
        target = Path(project_dir)

    if not target.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")

    items = []
    try:
        for entry in sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            if entry.name.startswith('.') and entry.name not in ('.env', '.gitignore'):
                continue
            if entry.is_dir() and entry.name in EXCLUDED_DIRS:
                continue

            item = FileItem(
                name=entry.name,
                path=str(entry.relative_to(Path(project_dir))),
                is_dir=entry.is_dir(),
                size=entry.stat().st_size if entry.is_file() else 0,
                extension=entry.suffix.lower() if entry.is_file() else "",
            )
            items.append(item)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    return items


def _get_project_dir() -> str | None:
    """config/config.jsonからproject_dirを取得"""
    try:
        config_path = Path("config/config.json")
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get("project_dir", "")
    except Exception:
        pass
    return None
```

---

## 7. InputBar改善（placeholder対応）

```jsx
// InputBar.jsxにplaceholderプロパティを追加
export default function InputBar({ onSend, disabled, placeholder }) {
  // ...
  <textarea
    placeholder={placeholder || "メッセージを入力... (Ctrl+Enter で送信)"}
    // ...
  />
}
```

---

## 8. テスト項目チェックリスト

| # | テスト項目 | 方法 | 期待結果 |
|---|----------|------|---------|
| 1 | iOSビューポート | iPhoneでアクセス | ヘッダー〜入力バーが1画面に収まる |
| 2 | タブ切替 | soloAI/mixAIタブをタップ | 画面が切り替わる |
| 3 | soloAI動作維持 | soloAIタブでメッセージ送信 | Phase 1と同じ動作 |
| 4 | mixAI Phase進捗 | mixAIタブで質問送信 | P1→P2→P3の進捗表示 |
| 5 | ローカルLLMステータス | mixAI Phase 2中 | カテゴリ別ステータス表示 |
| 6 | mixAI最終回答 | 3Phase完了後 | 統合回答がチャットに表示 |
| 7 | ファイルブラウザAPI | `/api/files/browse` | ファイル一覧JSON |
| 8 | モデル設定永続化 | 設定保存→リロード | 設定が維持される |
| 9 | WS再接続 | iPhoneのバックグラウンド→復帰 | 自動再接続 |
| 10 | 同時接続 | PyQt6 + iPhone同時使用 | 両方正常動作 |

---

## 9. 新規ファイルサマリー

| 種別 | ファイル | 内容 |
|------|---------|------|
| 修正 | `frontend/src/App.jsx` | タブ切替 + dvhビューポート修正 |
| 修正 | `frontend/src/styles/globals.css` | iOS Safari修正 |
| 修正 | `frontend/index.html` | viewport meta修正 |
| 修正 | `frontend/src/hooks/useWebSocket.js` | mixAI対応拡張 |
| 修正 | `frontend/src/components/ChatView.jsx` | min-h-0修正 |
| 修正 | `frontend/src/components/InputBar.jsx` | shrink-0 + placeholder |
| 修正 | `src/web/server.py` | /ws/mix エンドポイント + mixAI実行ロジック |
| 修正 | `src/web/api_routes.py` | ファイルブラウザAPI追加 |
| 新規 | `frontend/src/components/TabBar.jsx` | soloAI/mixAIタブ切替 |
| 新規 | `frontend/src/components/MixAIView.jsx` | mixAIメインビュー |
| 新規 | `frontend/src/components/PhaseIndicator.jsx` | P1→P2→P3進捗表示 |
| 新規 | `frontend/src/components/LLMStatusPanel.jsx` | ローカルLLMステータス |

**既存PyQt6コードへの変更**: ゼロ

---

## 10. Phase 3 への橋渡し

Phase 2完了後、Phase 3 で追加する機能:

1. **情報収集タブ（RAG監視）** — RAG構築進捗のリアルタイム表示
2. **GPUモニター** — nvidia-smi経由のGPU使用率グラフ
3. **設定画面** — Web UI用の設定パネル（PIN変更、モデル選択等）
4. **PWA + プッシュ通知** — 実行完了時の通知
5. **BIBLE更新** — v9.0.0としてBIBLE文書更新
