# Helix AI Studio v9.0.0 Phase 3: 設定・モニター・統合・完成
## 実装指示書（Claude Code CLI用）

**作成日**: 2026-02-15
**対象**: Phase 3 — 設定画面 + GPUモニター + PyQt6統合 + PWA強化 + BIBLE更新
**想定期間**: 2-3日
**前提**: Phase 1 + Phase 2 完了済み（soloAI/mixAI両方動作確認済み）
**原則**: 既存PyQt6コードへの変更は最小限（server起動トグル追加のみ）

---

## 1. Phase 3 の目標

Phase 3完了時に達成されるべき状態:

1. **[コア]** Web UIから設定変更が可能（Claudeモデル選択、mixAIモデル割当、PIN変更）
2. **[コア]** GPUモニターでリアルタイムVRAM/使用率表示
3. **[統合]** PyQt6の一般設定タブに「Web UIサーバー」トグル追加
4. **[統合]** APP_VERSIONを "9.0.0" に更新
5. **[完成]** PWAアイコン生成 + オフライン対応
6. **[完成]** BIBLE v9.0.0 ドキュメント更新

---

## 2. Web UI 設定画面

### 2.1 タブバー拡張

**`frontend/src/components/TabBar.jsx`** を3タブに変更:

```jsx
const TABS = [
  { id: 'soloAI', label: 'soloAI', desc: 'Claude直接対話' },
  { id: 'mixAI', label: 'mixAI', desc: '3Phase統合実行' },
  { id: 'settings', label: '設定', desc: 'Web UI設定' },
];
```

### 2.2 新規コンポーネント: `frontend/src/components/SettingsView.jsx`

```jsx
import React, { useState, useEffect, useCallback } from 'react';

const API_BASE = '';  // 相対パス（プロキシ経由）

export default function SettingsView({ token }) {
  const [settings, setSettings] = useState(null);
  const [models, setModels] = useState([]);
  const [ollamaModels, setOllamaModels] = useState([]);
  const [gpuInfo, setGpuInfo] = useState(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  // 設定読み込み
  useEffect(() => {
    fetchSettings();
    fetchModels();
    fetchOllamaModels();
    fetchGpuInfo();
    const gpuInterval = setInterval(fetchGpuInfo, 5000);  // 5秒間隔
    return () => clearInterval(gpuInterval);
  }, [token]);

  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

  async function fetchSettings() {
    try {
      const res = await fetch(`${API_BASE}/api/settings`, { headers });
      if (res.ok) setSettings(await res.json());
    } catch (e) { console.error('Settings fetch error:', e); }
  }

  async function fetchModels() {
    try {
      const res = await fetch(`${API_BASE}/api/config/models`, { headers });
      if (res.ok) setModels(await res.json());
    } catch (e) { console.error('Models fetch error:', e); }
  }

  async function fetchOllamaModels() {
    try {
      const res = await fetch(`${API_BASE}/api/config/ollama-models`, { headers });
      if (res.ok) setOllamaModels(await res.json());
    } catch (e) { console.error('Ollama models fetch error:', e); }
  }

  async function fetchGpuInfo() {
    try {
      const res = await fetch(`${API_BASE}/api/monitor/gpu`, { headers });
      if (res.ok) setGpuInfo(await res.json());
    } catch (e) { console.error('GPU fetch error:', e); }
  }

  async function saveSettings() {
    setSaving(true);
    setMessage('');
    try {
      const res = await fetch(`${API_BASE}/api/settings`, {
        method: 'PUT', headers, body: JSON.stringify(settings),
      });
      if (res.ok) setMessage('保存しました');
      else setMessage('保存に失敗しました');
    } catch (e) { setMessage('エラー: ' + e.message); }
    setSaving(false);
    setTimeout(() => setMessage(''), 3000);
  }

  if (!settings) return <div className="flex-1 flex items-center justify-center text-gray-500">読込中...</div>;

  return (
    <div className="flex-1 overflow-y-auto min-h-0 px-4 py-4 space-y-4">
      {/* ═══ Claudeモデル設定 ═══ */}
      <Section title="Claude モデル">
        <SelectRow
          label="デフォルトモデル"
          value={settings.claude_model_id}
          options={models.map(m => ({ value: m.id, label: m.display_name }))}
          onChange={v => setSettings({...settings, claude_model_id: v})}
        />
        <SelectRow
          label="タイムアウト"
          value={settings.timeout}
          options={[
            { value: 300, label: '5分' },
            { value: 600, label: '10分' },
            { value: 1200, label: '20分' },
            { value: 1800, label: '30分' },
          ]}
          onChange={v => setSettings({...settings, timeout: Number(v)})}
        />
      </Section>

      {/* ═══ mixAIモデル割当 ═══ */}
      <Section title="mixAI モデル割当">
        {['coding', 'research', 'reasoning', 'vision', 'translation'].map(cat => (
          <SelectRow
            key={cat}
            label={cat}
            value={settings.model_assignments?.[cat] || ''}
            options={[
              { value: '', label: '未割当（スキップ）' },
              ...ollamaModels.map(m => ({ value: m.name, label: `${m.name} (${m.size})` })),
            ]}
            onChange={v => setSettings({
              ...settings,
              model_assignments: { ...settings.model_assignments, [cat]: v },
            })}
          />
        ))}
      </Section>

      {/* ═══ GPUモニター ═══ */}
      <Section title="GPU モニター">
        {gpuInfo ? (
          <div className="space-y-2">
            {gpuInfo.gpus.map((gpu, i) => (
              <GpuCard key={i} gpu={gpu} />
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-sm">GPU情報取得中...</p>
        )}
      </Section>

      {/* ═══ セキュリティ ═══ */}
      <Section title="セキュリティ">
        <InputRow
          label="PIN変更"
          type="password"
          value={settings.pin || ''}
          onChange={v => setSettings({...settings, pin: v})}
          placeholder="新しいPINを入力"
        />
        <InfoRow label="JWT有効期限" value={`${settings.jwt_expiry_hours || 168}時間`} />
        <InfoRow label="最大同時接続" value={`${settings.max_connections || 3}`} />
      </Section>

      {/* ═══ プロジェクトディレクトリ ═══ */}
      <Section title="プロジェクト">
        <InfoRow label="プロジェクトDir" value={settings.project_dir || '未設定'} />
        <InfoRow label="Ollamaホスト" value={settings.ollama_host || 'http://localhost:11434'} />
      </Section>

      {/* 保存ボタン */}
      <div className="flex items-center gap-3 pt-2 pb-8">
        <button
          onClick={saveSettings}
          disabled={saving}
          className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-600 text-white rounded-lg font-medium transition-colors"
        >
          {saving ? '保存中...' : '設定を保存'}
        </button>
        {message && (
          <span className={`text-sm ${message.includes('エラー') ? 'text-red-400' : 'text-emerald-400'}`}>
            {message}
          </span>
        )}
      </div>
    </div>
  );
}

// ═══ サブコンポーネント ═══

function Section({ title, children }) {
  return (
    <div className="bg-gray-900 rounded-xl p-4 space-y-3">
      <h3 className="text-emerald-400 font-semibold text-sm">{title}</h3>
      {children}
    </div>
  );
}

function SelectRow({ label, value, options, onChange }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <label className="text-gray-300 text-sm shrink-0">{label}</label>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="bg-gray-800 text-gray-200 text-sm rounded-lg px-3 py-1.5 border border-gray-700 focus:border-emerald-500 outline-none max-w-[200px]"
      >
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

function InputRow({ label, type = 'text', value, onChange, placeholder }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <label className="text-gray-300 text-sm shrink-0">{label}</label>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="bg-gray-800 text-gray-200 text-sm rounded-lg px-3 py-1.5 border border-gray-700 focus:border-emerald-500 outline-none max-w-[200px]"
      />
    </div>
  );
}

function InfoRow({ label, value }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-gray-400 text-sm">{label}</span>
      <span className="text-gray-300 text-sm font-mono">{value}</span>
    </div>
  );
}

function GpuCard({ gpu }) {
  const vramPercent = gpu.memory_total > 0 ? (gpu.memory_used / gpu.memory_total * 100) : 0;
  const barColor = vramPercent > 90 ? 'bg-red-500' : vramPercent > 70 ? 'bg-amber-500' : 'bg-emerald-500';

  return (
    <div className="bg-gray-800 rounded-lg p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-gray-200 text-sm font-medium">{gpu.name}</span>
        <span className="text-gray-400 text-xs">{gpu.utilization}% util</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
          <div className={`h-full ${barColor} rounded-full transition-all duration-500`}
               style={{ width: `${vramPercent}%` }} />
        </div>
        <span className="text-gray-400 text-xs shrink-0">
          {(gpu.memory_used / 1024).toFixed(1)}/{(gpu.memory_total / 1024).toFixed(1)} GB
        </span>
      </div>
      <div className="text-gray-500 text-xs">
        温度: {gpu.temperature}°C | 電力: {gpu.power_draw}W
      </div>
    </div>
  );
}
```

### 2.3 App.jsx の修正（設定タブ追加）

```jsx
import SettingsView from './components/SettingsView';

// return内:
{activeTab === 'settings' ? (
  <SettingsView token={token} />
) : activeTab === 'soloAI' ? (
  <>
    <ChatView messages={soloAI.messages} isExecuting={soloAI.isExecuting} />
    <InputBar onSend={soloAI.sendMessage} disabled={soloAI.isExecuting} />
  </>
) : (
  <MixAIView mixAI={mixAI} />
)}
```

---

## 3. バックエンド: 設定API + GPUモニターAPI

### 3.1 `src/web/api_routes.py` に追加

```python
import subprocess
import json
from pathlib import Path

# ═══ 設定 GET/PUT ═══

class SettingsResponse(BaseModel):
    claude_model_id: str = "claude-opus-4-6"
    timeout: int = 600
    model_assignments: dict = {}
    pin: str = ""  # 表示時は空文字
    jwt_expiry_hours: int = 168
    max_connections: int = 3
    project_dir: str = ""
    ollama_host: str = "http://localhost:11434"


@router.get("/api/settings", response_model=SettingsResponse)
async def get_settings(payload: dict = Depends(verify_jwt)):
    """Web UI設定を取得（web_config.json + config.json統合）"""
    settings = _load_merged_settings()
    settings["pin"] = ""  # PINは表示しない
    return settings


class SettingsUpdate(BaseModel):
    claude_model_id: str | None = None
    timeout: int | None = None
    model_assignments: dict | None = None
    pin: str | None = None
    jwt_expiry_hours: int | None = None
    max_connections: int | None = None


@router.put("/api/settings")
async def update_settings(update: SettingsUpdate, payload: dict = Depends(verify_jwt)):
    """Web UI設定を更新"""
    web_config_path = Path("config/web_config.json")
    config_path = Path("config/config.json")

    # web_config.json更新
    if web_config_path.exists():
        with open(web_config_path, 'r', encoding='utf-8') as f:
            web_config = json.load(f)
    else:
        web_config = {}

    if update.pin and len(update.pin) >= 4:
        web_config["pin"] = update.pin
    if update.jwt_expiry_hours:
        web_config["jwt_expiry_hours"] = update.jwt_expiry_hours
    if update.max_connections:
        web_config["max_connections"] = update.max_connections

    with open(web_config_path, 'w', encoding='utf-8') as f:
        json.dump(web_config, f, ensure_ascii=False, indent=2)

    # config.json更新（Claude/mixAI設定）
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    else:
        config = {}

    if update.claude_model_id:
        config["claude_model_id"] = update.claude_model_id
    if update.timeout:
        config["timeout"] = update.timeout
    if update.model_assignments:
        config["model_assignments"] = update.model_assignments

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    return {"status": "ok", "message": "設定を保存しました"}


def _load_merged_settings() -> dict:
    """web_config.json + config.json を統合読み込み"""
    result = {
        "claude_model_id": "claude-opus-4-6",
        "timeout": 600,
        "model_assignments": {},
        "pin": "",
        "jwt_expiry_hours": 168,
        "max_connections": 3,
        "project_dir": "",
        "ollama_host": "http://localhost:11434",
    }

    # config.json
    try:
        config_path = Path("config/config.json")
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            result.update({
                "claude_model_id": config.get("claude_model_id", result["claude_model_id"]),
                "timeout": config.get("timeout", result["timeout"]),
                "model_assignments": config.get("model_assignments", {}),
                "project_dir": config.get("project_dir", ""),
                "ollama_host": config.get("ollama_host", result["ollama_host"]),
            })
    except Exception:
        pass

    # web_config.json
    try:
        web_config_path = Path("config/web_config.json")
        if web_config_path.exists():
            with open(web_config_path, 'r', encoding='utf-8') as f:
                web_config = json.load(f)
            result.update({
                "jwt_expiry_hours": web_config.get("jwt_expiry_hours", result["jwt_expiry_hours"]),
                "max_connections": web_config.get("max_connections", result["max_connections"]),
            })
    except Exception:
        pass

    return result


# ═══ Ollamaモデル一覧 ═══

@router.get("/api/config/ollama-models")
async def get_ollama_models(payload: dict = Depends(verify_jwt)):
    """Ollama APIから利用可能なモデル一覧を取得"""
    import httpx
    settings = _load_merged_settings()
    ollama_host = settings.get("ollama_host", "http://localhost:11434")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{ollama_host}/api/tags")
            resp.raise_for_status()
            models_data = resp.json().get("models", [])
            return [
                {
                    "name": m.get("name", ""),
                    "size": _format_size(m.get("size", 0)),
                    "modified": m.get("modified_at", ""),
                }
                for m in models_data
            ]
    except Exception as e:
        return []


def _format_size(size_bytes: int) -> str:
    """バイト数を人間可読形式に変換"""
    if size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.0f}KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f}MB"
    else:
        return f"{size_bytes / (1024 ** 3):.1f}GB"


# ═══ GPUモニター ═══

@router.get("/api/monitor/gpu")
async def get_gpu_info(payload: dict = Depends(verify_jwt)):
    """nvidia-smi経由でGPU情報を取得"""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=5,
        )

        if result.returncode != 0:
            return {"gpus": [], "error": "nvidia-smi failed"}

        gpus = []
        for line in result.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                gpus.append({
                    "name": parts[0],
                    "memory_used": int(float(parts[1])),   # MiB
                    "memory_total": int(float(parts[2])),   # MiB
                    "utilization": int(float(parts[3])),    # %
                    "temperature": int(float(parts[4])),    # °C
                    "power_draw": round(float(parts[5]), 1),  # W
                })

        return {"gpus": gpus}

    except FileNotFoundError:
        return {"gpus": [], "error": "nvidia-smi not found"}
    except Exception as e:
        return {"gpus": [], "error": str(e)}
```

---

## 4. PyQt6統合: Web UIサーバートグル

### 4.1 既存ファイルへの**最小限の変更**

**`src/utils/constants.py`** — バージョン更新（3行変更）:

```python
# 変更前
APP_VERSION = "8.5.0"
APP_CODENAME = "Autonomous RAG"
APP_DESCRIPTION = (
    "Helix AI Studio v8.5.0 'Autonomous RAG' - "
    "情報収集タブ新設・自律RAG構築パイプライン・Document Memory・ロック機構"
)

# 変更後
APP_VERSION = "9.0.0"
APP_CODENAME = "Mobile Web"
APP_DESCRIPTION = (
    "Helix AI Studio v9.0.0 'Mobile Web' - "
    "Web UI統合・モバイルアクセス・soloAI/mixAIリモート対話・GPUモニター"
)
```

### 4.2 一般設定タブにWeb UIセクション追加

**対象ファイル**: `src/tabs/settings_tab.py` （既存）

追加する箇所: 既存設定セクションの最後に「Web UIサーバー」セクションを追加

```python
# ═══ Web UIサーバーセクション ═══
# _create_web_ui_section(self) を追加

def _create_web_ui_section(self) -> QGroupBox:
    """Web UIサーバー設定セクション"""
    group = QGroupBox("Web UI サーバー")
    group.setStyleSheet(SECTION_CARD_STYLE)
    layout = QVBoxLayout(group)

    # 起動トグル
    toggle_row = QHBoxLayout()
    self.web_ui_toggle = QPushButton("サーバー停止中")
    self.web_ui_toggle.setCheckable(True)
    self.web_ui_toggle.setStyleSheet("""
        QPushButton { background-color: #374151; color: #9CA3AF; padding: 8px 16px; border-radius: 6px; }
        QPushButton:checked { background-color: #059669; color: white; }
    """)
    self.web_ui_toggle.clicked.connect(self._toggle_web_server)
    toggle_row.addWidget(self.web_ui_toggle)

    self.web_ui_status_label = QLabel("ポート: 8500")
    self.web_ui_status_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
    toggle_row.addWidget(self.web_ui_status_label)
    toggle_row.addStretch()
    layout.addLayout(toggle_row)

    # アクセスURL表示
    self.web_ui_url_label = QLabel("")
    self.web_ui_url_label.setStyleSheet(f"color: {COLORS['accent_cyan']}; font-size: 11px;")
    self.web_ui_url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    layout.addWidget(self.web_ui_url_label)

    return group

def _toggle_web_server(self):
    """Web UIサーバーの起動/停止"""
    if self.web_ui_toggle.isChecked():
        try:
            from ..web.server import start_server_background
            self._web_server_thread = start_server_background(port=8500)
            self.web_ui_toggle.setText("サーバー稼働中")

            # Tailscale IP取得
            import subprocess
            result = subprocess.run(["tailscale", "ip", "-4"],
                                     capture_output=True, text=True, timeout=5)
            ip = result.stdout.strip() if result.returncode == 0 else "localhost"
            self.web_ui_url_label.setText(f"アクセスURL: http://{ip}:8500")
        except Exception as e:
            self.web_ui_toggle.setChecked(False)
            self.web_ui_toggle.setText("サーバー停止中")
            self.web_ui_url_label.setText(f"起動失敗: {e}")
    else:
        # サーバー停止
        if hasattr(self, '_web_server_thread') and self._web_server_thread:
            self._web_server_thread.stop()
            self._web_server_thread = None
        self.web_ui_toggle.setText("サーバー停止中")
        self.web_ui_url_label.setText("")
```

### 4.3 `src/web/server.py` にバックグラウンド起動関数追加

```python
import threading

class WebServerThread:
    """PyQt6から起動するWeb UIサーバースレッド"""

    def __init__(self, host="0.0.0.0", port=8500):
        self.host = host
        self.port = port
        self._thread = None
        self._server = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        config = uvicorn.Config(app, host=self.host, port=self.port,
                                 log_level="info")
        self._server = uvicorn.Server(config)
        self._server.run()

    def stop(self):
        if self._server:
            self._server.should_exit = True

    @property
    def is_running(self):
        return self._thread is not None and self._thread.is_alive()


def start_server_background(port=8500) -> WebServerThread:
    """PyQt6からバックグラウンドでサーバーを起動"""
    server = WebServerThread(port=port)
    server.start()
    return server
```

---

## 5. PWA強化

### 5.1 アイコン生成

以下のサイズのPNGアイコンが必要:
- `frontend/public/icon-192.png` (192x192)
- `frontend/public/icon-512.png` (512x512)

**生成方法**: Helix AI Studioのロゴ（emerald背景 + DNA helixアイコン）をSVGで作成し、Pythonで変換:

```python
# アイコン生成スクリプト: scripts/generate_pwa_icons.py
from PIL import Image, ImageDraw, ImageFont
import math

def create_icon(size):
    img = Image.new('RGBA', (size, size), (16, 185, 129, 255))  # emerald-500
    draw = ImageDraw.Draw(img)

    # 中央に "H" テキスト
    font_size = size // 2
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), "H", font=font)
    x = (size - (bbox[2] - bbox[0])) // 2
    y = (size - (bbox[3] - bbox[1])) // 2
    draw.text((x, y), "H", fill="white", font=font)

    return img

for s in [192, 512]:
    img = create_icon(s)
    img.save(f"frontend/public/icon-{s}.png")
    print(f"Generated icon-{s}.png")
```

### 5.2 manifest.json更新

```json
{
  "name": "Helix AI Studio",
  "short_name": "Helix AI",
  "start_url": "/",
  "display": "standalone",
  "orientation": "portrait",
  "theme_color": "#10b981",
  "background_color": "#030712",
  "icons": [
    {
      "src": "/icon-192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any maskable"
    },
    {
      "src": "/icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ]
}
```

### 5.3 Service Worker（オフライン基本対応）

**`frontend/public/sw.js`**:

```javascript
const CACHE_NAME = 'helix-ai-studio-v9';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/icon-192.png',
  '/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // APIリクエストはキャッシュしない
  if (event.request.url.includes('/api/') || event.request.url.includes('/ws/')) {
    return;
  }
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});
```

**`frontend/src/main.jsx`** にSW登録追加:

```javascript
// Service Worker登録
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(err => {
      console.log('SW registration failed:', err);
    });
  });
}
```

---

## 6. テスト項目チェックリスト

| # | テスト項目 | 方法 | 期待結果 |
|---|----------|------|---------|
| 1 | 設定タブ表示 | 設定タブをタップ | Claudeモデル/mixAIモデル/GPU/セキュリティ表示 |
| 2 | GPUモニター | 設定タブ内GPU欄 | 2GPU（RTX PRO 6000 + RTX 5070 Ti）のVRAM/温度表示 |
| 3 | GPU自動更新 | 5秒待機 | VRAM使用量が自動更新 |
| 4 | Claudeモデル変更 | ドロップダウン変更→保存 | config.json更新 |
| 5 | mixAIモデル割当 | カテゴリ別モデル選択→保存 | model_assignments保存 |
| 6 | PIN変更 | 新PIN入力→保存→再ログイン | 新PINでログイン可能 |
| 7 | Ollamaモデル一覧 | 設定タブ mixAI欄 | プル済みモデルがドロップダウンに表示 |
| 8 | PyQt6 バージョン | デスクトップアプリ起動 | v9.0.0表示 |
| 9 | PyQt6 WebUIトグル | 一般設定→Web UIサーバー→チェック | サーバー起動、URL表示 |
| 10 | PWAインストール | Safari→ホーム画面に追加 | 専用アイコンで起動 |
| 11 | PWAオフライン | 機内モード→アプリ起動 | ログイン画面表示（API接続不可の旨） |
| 12 | 既存機能維持 | PyQt6 mixAI/soloAI実行 | Phase 1-2と同じ動作 |

---

## 7. 新規/変更ファイルサマリー

| 種別 | ファイル | 内容 |
|------|---------|------|
| **新規** | `frontend/src/components/SettingsView.jsx` | 設定画面（モデル選択/GPU/セキュリティ） |
| **新規** | `frontend/public/sw.js` | Service Worker（オフライン対応） |
| **新規** | `frontend/public/icon-192.png` | PWAアイコン 192x192 |
| **新規** | `frontend/public/icon-512.png` | PWAアイコン 512x512 |
| **新規** | `scripts/generate_pwa_icons.py` | アイコン生成スクリプト |
| **修正** | `frontend/src/components/TabBar.jsx` | 設定タブ追加 |
| **修正** | `frontend/src/App.jsx` | SettingsView統合 |
| **修正** | `frontend/public/manifest.json` | アイコンパス更新 |
| **修正** | `frontend/src/main.jsx` | SW登録追加 |
| **修正** | `src/web/api_routes.py` | 設定API + GPUモニターAPI + Ollamaモデル一覧 |
| **修正** | `src/web/server.py` | start_server_background() 追加 |
| **変更** | `src/utils/constants.py` | VERSION → 9.0.0（3行のみ） |
| **変更** | `src/tabs/settings_tab.py` | Web UIサーバーセクション追加 |

### 既存PyQt6への変更（最小限）
- `constants.py`: バージョン番号3行のみ
- `settings_tab.py`: Web UIトグルセクション追加（既存機能への影響なし）

---

## 8. Phase 3完了後の最終作業

### 8.1 BIBLE更新

BIBLE_Helix_AI_Studio_9_0_0.md を作成。主な更新内容:

- v9.0.0 "Mobile Web" リリースノート
- Web UIアーキテクチャセクション追加（FastAPI + React PWA）
- 認証フロー（Tailscale + PIN + JWT）ドキュメント
- WebSocketプロトコル仕様
- 新規ファイル/ディレクトリ構成の更新
- デプロイ手順（PyQt6トグル or コマンドライン起動）

### 8.2 git commit

```bash
git add -A
git commit -m "v9.0.0 'Mobile Web' - Web UI統合完成

Phase 1: FastAPI + WebSocket + React PWA基盤、soloAI対応
Phase 2: iOS修正、タブ切替、mixAI 3Phase WebSocket、ファイルブラウザ
Phase 3: 設定画面、GPUモニター、PyQt6統合、PWA強化

- Tailscale VPN + PIN + JWT 3層認証
- soloAI/mixAI モバイルリモート対話
- リアルタイムGPUモニター（nvidia-smi）
- PWA + Service Worker対応
- 既存PyQt6への影響最小限（constants.py + settings_tab.py のみ）"
```
