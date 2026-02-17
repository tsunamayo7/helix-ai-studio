# Helix AI Studio v9.5.0 "Cross-Device Sync"
## Web実行ロック + モバイルファイル添付 + デバイス間ファイル転送 + ログアウト後チャット閲覧
## 実装設計書（Claude Code CLI用）

**作成日**: 2026-02-16
**前提**: v9.4.0 "Unified Timeout" 完了済み（2つ目ウィンドウ問題は三層防御で解決済み）
**原則**: セキュリティ（Tailscale VPN + JWT認証）は既存基盤を活用

---

## 1. v9.5.0 の全体像

### 5つの実装項目:

| # | 機能 | 概要 |
|---|------|------|
| A | Web実行ロック | Web版で実行中 → Windows側をロック（オーバーレイ + 操作不可） |
| B | モバイルファイル添付 | iPhone/iPadからファイルをアップロードしてプロンプトに添付 |
| C | デバイス間ファイル転送 | ファイルタブでモバイル↔Windows間のファイル送受信 |
| D | ログアウト後チャット閲覧 | 認証なしで直近チャットのタイトル+プレビューを閲覧可能 |
| E | BIBLE更新 | v9.0.0〜v9.2.0の欠落バージョン補完 + v9.5.0記載 |

---

## 2. 機能A: Web実行ロック

### 2.1 アーキテクチャ

```
iPhone で soloAI/mixAI 実行開始
    ↓ WebSocket: {"type": "execution_started", "tab": "soloAI"}
    ↓
FastAPI server
    ↓ ロック状態をファイルに書き出し
    ↓
data/web_execution_lock.json  ← PyQt6がポーリングで監視（2秒間隔）
    ↓
Windows PyQt6: オーバーレイ表示 + 入力無効化
    ↓
iPhone で実行完了
    ↓ ロック解除 → オーバーレイ消去 → Windows操作復帰
```

### 2.2 ロックファイル: `data/web_execution_lock.json`

```json
// ロック中
{
  "locked": true,
  "tab": "soloAI",
  "client_info": "iPhone Safari",
  "started_at": "2026-02-16T14:30:00",
  "prompt_preview": "Pythonでhello worldを..."
}

// ロック解除時
{
  "locked": false
}
```

### 2.3 バックエンド: サーバー側ロック管理 (`src/web/server.py` に追加)

```python
import json
from pathlib import Path

LOCK_FILE = Path("data/web_execution_lock.json")

def _set_execution_lock(tab: str, client_info: str, prompt: str):
    """Web実行ロックを設定"""
    lock_data = {
        "locked": True,
        "tab": tab,
        "client_info": client_info,
        "started_at": datetime.now().isoformat(),
        "prompt_preview": prompt[:50],
    }
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(json.dumps(lock_data, ensure_ascii=False), encoding='utf-8')

def _release_execution_lock():
    """Web実行ロックを解除"""
    LOCK_FILE.write_text('{"locked": false}', encoding='utf-8')
```

### REST APIエンドポイント (`src/web/api_routes.py`):

```python
@router.get("/api/execution/lock")
async def get_execution_lock(payload: dict = Depends(verify_jwt)):
    """現在のロック状態取得"""
    if LOCK_FILE.exists():
        data = json.loads(LOCK_FILE.read_text(encoding='utf-8'))
        return data
    return {"locked": False}
```

### WebSocketハンドラ修正:

```python
async def _handle_solo_execute(client_id: str, data: dict):
    prompt = data.get("prompt", "")
    client_info = data.get("client_info", "Web Client")

    # ロック設定
    _set_execution_lock("soloAI", client_info, prompt)

    try:
        # ... 既存の実行ロジック ...
        pass
    finally:
        # 必ずロック解除（エラー時も）
        _release_execution_lock()
```

mixAIの `_handle_mix_execute` にも同様に try/finally で `_set_execution_lock` / `_release_execution_lock` を追加。

### 2.4 PyQt6: ロック監視 (`src/main_window.py` に追加)

```python
from PyQt6.QtCore import QTimer

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # ... 既存の初期化 ...

        # Web実行ロック監視タイマー（2秒間隔）
        self._web_lock_timer = QTimer(self)
        self._web_lock_timer.setInterval(2000)
        self._web_lock_timer.timeout.connect(self._check_web_execution_lock)
        self._web_lock_timer.start()
        self._web_locked = False

    def _check_web_execution_lock(self):
        """Web実行ロックファイルを監視"""
        lock_file = Path("data/web_execution_lock.json")
        try:
            if lock_file.exists():
                data = json.loads(lock_file.read_text(encoding='utf-8'))
                is_locked = data.get("locked", False)
            else:
                is_locked = False
        except Exception:
            is_locked = False

        if is_locked and not self._web_locked:
            self._activate_web_lock(data)
        elif not is_locked and self._web_locked:
            self._deactivate_web_lock()

    def _activate_web_lock(self, lock_data: dict):
        """Webロック有効化 — オーバーレイ表示"""
        self._web_locked = True
        tab = lock_data.get("tab", "Web")
        client = lock_data.get("client_info", "")
        preview = lock_data.get("prompt_preview", "")

        for tab_widget in [self.llmmix_tab, self.claude_tab]:
            if hasattr(tab_widget, 'web_lock_overlay'):
                tab_widget.web_lock_overlay.show_lock(
                    f"📱 Web UIから実行中 ({tab})\n"
                    f"端末: {client}\n"
                    f"内容: {preview}"
                )
        self.statusBar().showMessage(f"📱 Web UI実行中: {tab} - {preview}")

    def _deactivate_web_lock(self):
        """Webロック解除"""
        self._web_locked = False
        for tab_widget in [self.llmmix_tab, self.claude_tab]:
            if hasattr(tab_widget, 'web_lock_overlay'):
                tab_widget.web_lock_overlay.hide_lock()
        self.statusBar().showMessage("Ready")
```

### 2.5 PyQt6: WebLockOverlayウィジェット (`src/widgets/web_lock_overlay.py` 新規)

```python
"""
Web UI実行中のロックオーバーレイ。
半透明ダーク背景で親ウィジェットを覆い、入力をブロックする。
"""

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class WebLockOverlay(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("webLockOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        self.setStyleSheet("""
            #webLockOverlay {
                background-color: rgba(0, 0, 0, 180);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # スマホアイコン
        icon_label = QLabel("📱")
        icon_label.setFont(QFont("Segoe UI Emoji", 48))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # メッセージ
        self.message_label = QLabel("Web UIから実行中...")
        self.message_label.setStyleSheet(
            "color: #10b981; font-size: 16px; font-weight: bold; padding: 10px;")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        # サブメッセージ
        self.sub_label = QLabel("完了するまでお待ちください")
        self.sub_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.sub_label)

        self.hide()

    def show_lock(self, message: str = ""):
        if message:
            self.message_label.setText(message)
        if self.parent():
            self.setGeometry(self.parent().rect())
        self.raise_()
        self.show()

    def hide_lock(self):
        self.hide()

    def resizeEvent(self, event):
        if self.parent():
            self.setGeometry(self.parent().rect())
```

### 2.6 WebLockOverlayの設置

mixAIタブ (`helix_orchestrator_tab.py`) と soloAIタブ (`claude_tab.py`) の `__init__` にそれぞれ:

```python
from ..widgets.web_lock_overlay import WebLockOverlay

# __init__ 内
self.web_lock_overlay = WebLockOverlay(self)
```

---

## 3. 機能B: モバイルファイル添付（アップロード）

### 3.1 制限設定 (`src/web/file_transfer.py` 新規)

```python
"""
Web UIファイル転送の制限・バリデーション定義。
"""

from pathlib import Path

# アップロード制限
UPLOAD_MAX_SIZE_MB = 10
UPLOAD_MAX_SIZE_BYTES = UPLOAD_MAX_SIZE_MB * 1024 * 1024

UPLOAD_ALLOWED_EXTENSIONS = {
    # テキスト系
    '.txt', '.md', '.csv', '.json', '.yaml', '.yml', '.toml',
    '.xml', '.html', '.css', '.log', '.ini', '.cfg', '.env',
    # コード系
    '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.c', '.cpp',
    '.h', '.hpp', '.cs', '.go', '.rs', '.rb', '.php', '.swift',
    '.kt', '.scala', '.sh', '.bat', '.ps1', '.sql',
    # ドキュメント系
    '.pdf', '.docx',
    # 画像系
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg',
}

UPLOAD_BLOCKED_EXTENSIONS = {
    '.exe', '.dll', '.msi', '.scr', '.com',
    '.vbs', '.wsf', '.wsh',
    '.zip', '.rar', '.7z', '.tar', '.gz',
}


def validate_upload(filename: str, size: int = None) -> str | None:
    """アップロードファイルのバリデーション。エラーメッセージを返す。Noneなら OK。"""
    if not filename:
        return "ファイル名が空です"

    ext = Path(filename).suffix.lower()

    if ext in UPLOAD_BLOCKED_EXTENSIONS:
        return f"セキュリティ上の理由で {ext} ファイルはアップロードできません"

    if ext not in UPLOAD_ALLOWED_EXTENSIONS:
        return f"{ext} ファイルは対応していません。対応形式: テキスト, コード, 画像, PDF, DOCX"

    if size and size > UPLOAD_MAX_SIZE_BYTES:
        return f"ファイルサイズ ({size // (1024*1024)}MB) が上限 ({UPLOAD_MAX_SIZE_MB}MB) を超えています"

    return None
```

### 3.2 バックエンド: アップロードAPI (`src/web/api_routes.py` に追加)

```python
from fastapi import UploadFile, File
from .file_transfer import UPLOAD_MAX_SIZE_BYTES, UPLOAD_ALLOWED_EXTENSIONS, validate_upload

UPLOAD_DIR = Path("data/web_uploads")

@router.post("/api/files/upload")
async def upload_file(file: UploadFile = File(...),
                       payload: dict = Depends(verify_jwt)):
    """モバイルからファイルをアップロード"""
    error = validate_upload(file.filename, file.size)
    if error:
        raise HTTPException(status_code=400, detail=error)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{timestamp}_{file.filename}"
    save_path = UPLOAD_DIR / safe_name

    # ストリーミング書き込み（メモリ効率）
    total_size = 0
    with open(save_path, 'wb') as f:
        while chunk := await file.read(1024 * 64):  # 64KB chunks
            total_size += len(chunk)
            if total_size > UPLOAD_MAX_SIZE_BYTES:
                save_path.unlink(exist_ok=True)
                raise HTTPException(status_code=413,
                    detail=f"ファイルサイズ上限 ({UPLOAD_MAX_SIZE_BYTES // (1024*1024)}MB) 超過")
            f.write(chunk)

    return {
        "status": "ok",
        "filename": safe_name,
        "original_name": file.filename,
        "size": total_size,
        "path": str(save_path),
    }

@router.get("/api/files/uploads")
async def list_uploads(payload: dict = Depends(verify_jwt)):
    """アップロード済みファイル一覧"""
    if not UPLOAD_DIR.exists():
        return {"files": []}
    files = []
    for f in sorted(UPLOAD_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.is_file():
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "uploaded_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
    return {"files": files}

@router.delete("/api/files/uploads/{filename}")
async def delete_upload(filename: str, payload: dict = Depends(verify_jwt)):
    """アップロードファイル削除"""
    target = UPLOAD_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not str(target.resolve()).startswith(str(UPLOAD_DIR.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")
    target.unlink()
    return {"status": "ok"}
```

### 3.3 フロントエンド: InputBar アップロードメニュー

```jsx
// InputBar.jsx — 既存の「+ 追加」ボタンのメニューを拡張
// ファイル添付メニューを2段構成にする

function AttachMenu({ token, onFileAttached, onOpenBrowser, onClose }) {
  const fileInputRef = useRef(null);
  const [uploading, setUploading] = useState(false);

  async function handleLocalUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    // クライアント側バリデーション
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
      alert(`ファイルサイズ上限: 10MB（選択: ${(file.size / (1024*1024)).toFixed(1)}MB）`);
      return;
    }

    const allowedExts = ['.txt','.md','.py','.js','.jsx','.ts','.json','.csv',
      '.html','.css','.yaml','.sql','.pdf','.docx','.png','.jpg','.jpeg','.gif'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!allowedExts.includes(ext)) {
      alert(`非対応の拡張子: ${ext}`);
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch('/api/files/upload', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });
      if (res.ok) {
        const data = await res.json();
        onFileAttached({
          name: file.name,
          serverPath: data.path,
          size: data.size,
          source: 'upload',  // 'upload' = モバイルから
        });
        onClose();
      } else {
        const err = await res.json();
        alert(err.detail || 'アップロード失敗');
      }
    } catch (e) {
      alert('アップロードエラー');
    }
    setUploading(false);
  }

  return (
    <div className="absolute bottom-full left-0 mb-2 bg-gray-800 rounded-lg
                    border border-gray-700 shadow-xl p-2 min-w-[200px]">
      {/* モバイル端末からアップロード */}
      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading}
        className="w-full text-left px-3 py-2 text-sm text-gray-300
                   hover:bg-gray-700 rounded flex items-center gap-2"
      >
        📤 この端末からアップロード
        {uploading && <span className="text-[10px] text-emerald-400">送信中...</span>}
      </button>
      <input ref={fileInputRef} type="file" className="hidden"
             onChange={handleLocalUpload}
             accept=".txt,.md,.py,.js,.jsx,.ts,.json,.csv,.html,.css,.yaml,.sql,.pdf,.docx,.png,.jpg,.jpeg,.gif" />

      {/* サーバー上のファイルを参照（既存のFileBrowserModal） */}
      <button
        onClick={() => { onOpenBrowser(); onClose(); }}
        className="w-full text-left px-3 py-2 text-sm text-gray-300
                   hover:bg-gray-700 rounded flex items-center gap-2"
      >
        📁 サーバーのファイルを参照
      </button>

      {/* 上限表示 */}
      <div className="px-3 py-1 text-[10px] text-gray-600 border-t border-gray-700 mt-1">
        上限: 10MB / テキスト・コード・画像・PDF
      </div>
    </div>
  );
}
```

---

## 4. 機能C: デバイス間ファイル転送

### 4.1 バックエンド: ダウンロード + プロジェクトコピー API (`src/web/api_routes.py`)

```python
from fastapi.responses import FileResponse
from .file_transfer import UPLOAD_MAX_SIZE_BYTES, UPLOAD_MAX_SIZE_MB, UPLOAD_ALLOWED_EXTENSIONS

@router.get("/api/files/download")
async def download_file(path: str, payload: dict = Depends(verify_jwt)):
    """サーバー上のファイルをモバイル端末にダウンロード"""
    project_dir = _get_project_dir()
    target = Path(project_dir) / path

    # パストラバーサル防止
    if not str(target.resolve()).startswith(str(Path(project_dir).resolve())):
        raise HTTPException(status_code=403, detail="Access denied")

    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    # サイズ制限
    if target.stat().st_size > UPLOAD_MAX_SIZE_BYTES:
        raise HTTPException(status_code=413,
            detail=f"ファイルサイズが上限 ({UPLOAD_MAX_SIZE_MB}MB) を超えています")

    # 拡張子チェック
    if target.suffix.lower() not in UPLOAD_ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"非対応の拡張子: {target.suffix}")

    return FileResponse(path=str(target), filename=target.name,
                         media_type="application/octet-stream")

@router.post("/api/files/copy-to-project")
async def copy_upload_to_project(filename: str, dest_dir: str = "",
                                   payload: dict = Depends(verify_jwt)):
    """アップロードファイルをプロジェクトディレクトリにコピー（モバイル→Windows）"""
    source = UPLOAD_DIR / filename
    if not source.exists():
        raise HTTPException(status_code=404, detail="Upload not found")

    project_dir = Path(_get_project_dir())
    # タイムスタンププレフィックス除去（YYYYMMDD_HHMMSS_originalname）
    original_name = "_".join(filename.split("_")[2:]) if filename.count("_") >= 2 else filename
    dest = project_dir / dest_dir / original_name

    # パストラバーサル防止
    if not str(dest.resolve()).startswith(str(project_dir.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")

    import shutil
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)

    return {"status": "ok", "path": str(dest.relative_to(project_dir))}
```

### 4.2 フロントエンド: FileManagerView にTransferSection追加

```jsx
// FileManagerView.jsx に追加

function TransferSection({ token }) {
  const [uploads, setUploads] = useState([]);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => { fetchUploads(); }, []);

  async function fetchUploads() {
    try {
      const res = await fetch('/api/files/uploads', {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setUploads(data.files || []);
      }
    } catch (e) { console.error(e); }
  }

  async function handleUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch('/api/files/upload', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });
      if (res.ok) fetchUploads();
      else { const err = await res.json(); alert(err.detail); }
    } catch (e) { alert('アップロードエラー'); }
    setUploading(false);
  }

  async function handleCopyToProject(filename) {
    const dest = prompt('コピー先ディレクトリ（空でルート）:', '');
    if (dest === null) return;
    try {
      const res = await fetch(
        `/api/files/copy-to-project?filename=${encodeURIComponent(filename)}&dest_dir=${encodeURIComponent(dest)}`,
        { method: 'POST', headers: { 'Authorization': `Bearer ${token}` } }
      );
      if (res.ok) {
        const data = await res.json();
        alert(`コピー完了: ${data.path}`);
      }
    } catch (e) { alert('コピー失敗'); }
  }

  async function handleDeleteUpload(filename) {
    if (!confirm(`${filename} を削除しますか？`)) return;
    try {
      await fetch(`/api/files/uploads/${encodeURIComponent(filename)}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      fetchUploads();
    } catch (e) { console.error(e); }
  }

  function formatSize(bytes) {
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  }

  return (
    <div className="mt-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-emerald-400">📤 ファイル転送</h3>
        <button onClick={() => fileInputRef.current?.click()} disabled={uploading}
          className="px-3 py-1.5 bg-emerald-700 hover:bg-emerald-600 text-white
                     text-xs rounded-lg transition-colors disabled:opacity-50">
          {uploading ? '送信中...' : '📱 この端末からアップロード'}
        </button>
        <input ref={fileInputRef} type="file" className="hidden" onChange={handleUpload}
               accept=".txt,.md,.py,.js,.json,.csv,.html,.pdf,.docx,.png,.jpg,.jpeg" />
      </div>

      {uploads.length > 0 && (
        <div className="bg-gray-900 rounded-lg border border-gray-800 divide-y divide-gray-800">
          {uploads.map(f => (
            <div key={f.name} className="flex items-center justify-between px-3 py-2">
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-300 truncate">{f.name}</p>
                <p className="text-[10px] text-gray-600">{formatSize(f.size)}</p>
              </div>
              <div className="flex items-center gap-1">
                <button onClick={() => handleCopyToProject(f.name)}
                  className="text-[10px] px-2 py-1 bg-blue-900/50 text-blue-300 rounded hover:bg-blue-800/50">
                  ↗ プロジェクトにコピー
                </button>
                <button onClick={() => handleDeleteUpload(f.name)}
                  className="text-[10px] px-2 py-1 text-red-400 hover:bg-red-900/30 rounded">
                  🗑
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {uploads.length === 0 && (
        <p className="text-gray-600 text-xs text-center py-4">
          アップロードファイルなし（上限: 10MB）
        </p>
      )}

      <p className="text-[10px] text-gray-700 mt-2">
        対応: テキスト, コード, 画像, PDF, DOCX / 上限: 10MB/ファイル
      </p>
    </div>
  );
}
```

### 4.3 プロジェクトファイルにダウンロードボタン追加

FileManagerView.jsx の既存ファイル行に📥ボタンを追加:

```jsx
async function handleDownload(path) {
  try {
    const res = await fetch(`/api/files/download?path=${encodeURIComponent(path)}`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    if (res.ok) {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = path.split('/').pop();
      a.click();
      URL.revokeObjectURL(url);
    } else {
      const err = await res.json();
      alert(err.detail);
    }
  } catch (e) { alert('ダウンロードエラー'); }
}

// ファイル行内に追加
{file.type === 'file' && (
  <button onClick={() => handleDownload(currentPath + '/' + file.name)}
    className="text-[10px] px-2 py-1 text-gray-400 hover:text-emerald-300
               hover:bg-emerald-900/30 rounded"
    title="この端末にダウンロード">
    📥
  </button>
)}
```

---

## 5. 機能D: ログアウト後チャット閲覧

### 5.1 設計コンセプト

ログアウト状態（未認証）でもWeb UIにアクセスした際に、直近のチャット履歴の
タイトルとプレビュー（冒頭50文字）を閲覧可能にする。
チャット本文の全文閲覧やメッセージ送信にはログインが必要。

```
┌─────────────────────────────────────────────────────────┐
│ Helix AI Studio              [🔒 ログイン]             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  📋 最近のチャット                                      │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │ 📝 Pythonでhello worldを書いて                  │    │
│  │    2/16 14:30 · soloAI · 4メッセージ            │    │
│  │    「こんにちは！Pythonでhello worldを書く...」  │    │
│  │                                  [ログインして続行]│    │
│  ├─────────────────────────────────────────────────┤    │
│  │ 📝 React Hooksの使い方を教えて                  │    │
│  │    2/16 13:15 · soloAI · 6メッセージ            │    │
│  │    「React Hooksは関数コンポーネントで...」      │    │
│  │                                  [ログインして続行]│    │
│  ├─────────────────────────────────────────────────┤    │
│  │ 📝 mixAI: プロジェクト構成の分析                │    │
│  │    2/16 12:00 · mixAI · 8メッセージ             │    │
│  │    「プロジェクトの構成を分析しました...」       │    │
│  │                                  [ログインして続行]│    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  全20件中 最新10件を表示                                │
│  ※ チャット本文の閲覧にはログインが必要です             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 5.2 セキュリティ判断

| リスク要素 | 状況 | 判断 |
|-----------|------|------|
| ネットワーク | Tailscale VPN内のみアクセス可 | 低リスク |
| 利用者 | 個人利用（自分のみ） | 低リスク |
| 公開内容 | タイトル + 冒頭50文字プレビューのみ | 低リスク |
| 本文 | 認証必須 | 保護済み |

**結論**: Tailscale VPN内の個人利用であるため、タイトル+プレビューの認証なし公開は許容可能。

### 5.3 バックエンド: 認証不要エンドポイント (`src/web/api_routes.py`)

```python
@router.get("/api/chats/public-list")
async def public_chat_list(limit: int = 10):
    """認証不要: 直近チャットのタイトル+プレビューを返す

    注意: JWT認証なし。Tailscale VPN内アクセス前提。
    チャット本文は含まない。タイトルとプレビュー（50文字）のみ。
    """
    try:
        from .chat_store import ChatStore
        store = ChatStore()
        chats = store.list_chats(limit=limit)

        public_chats = []
        for chat in chats:
            # 最初のユーザーメッセージからプレビューを抽出
            preview = ""
            first_assistant = ""
            messages = store.get_messages(chat["id"], limit=2)
            for msg in messages:
                if msg["role"] == "user" and not preview:
                    preview = msg["content"][:50]
                if msg["role"] == "assistant" and not first_assistant:
                    first_assistant = msg["content"][:50]

            public_chats.append({
                "id": chat["id"],
                "title": chat.get("title", "無題"),
                "tab": chat.get("tab", "soloAI"),
                "created_at": chat.get("created_at", ""),
                "updated_at": chat.get("updated_at", ""),
                "message_count": chat.get("message_count", 0),
                "user_preview": preview,
                "assistant_preview": first_assistant,
            })

        return {"chats": public_chats, "total": len(public_chats)}
    except Exception as e:
        return {"chats": [], "total": 0, "error": str(e)}
```

### 5.4 ChatStore拡張 (`src/web/chat_store.py`)

`list_chats` と `get_messages` に `limit` パラメータが既にあるか確認し、
なければ以下のように拡張:

```python
def list_chats(self, limit: int = 50) -> list:
    """チャット一覧を取得（新しい順）"""
    conn = self._get_connection()
    try:
        rows = conn.execute(
            """SELECT id, title, tab, created_at, updated_at,
                      (SELECT COUNT(*) FROM messages WHERE chat_id = chats.id) as message_count
               FROM chats
               ORDER BY updated_at DESC
               LIMIT ?""",
            (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def get_messages(self, chat_id: str, limit: int = None) -> list:
    """チャットのメッセージを取得"""
    conn = self._get_connection()
    try:
        query = "SELECT role, content, created_at FROM messages WHERE chat_id = ? ORDER BY created_at ASC"
        params = [chat_id]
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
```

### 5.5 フロントエンド: ログイン前画面 (`App.jsx` 修正)

```jsx
// App.jsx — ログイン前の状態で表示するコンポーネント

function PreLoginView({ onLogin }) {
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
    const isToday = d.toDateString() === now.toDateString();
    if (isToday) {
      return d.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });
    }
    return d.toLocaleDateString('ja-JP', { month: 'numeric', day: 'numeric' })
      + ' ' + d.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });
  }

  function tabBadge(tab) {
    if (tab === 'mixAI') return { text: 'mixAI', color: 'bg-purple-900/50 text-purple-300' };
    return { text: 'soloAI', color: 'bg-cyan-900/50 text-cyan-300' };
  }

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      {/* ヘッダー */}
      <div className="p-4 border-b border-gray-800 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-emerald-400">Helix AI Studio</h1>
          <p className="text-[10px] text-gray-600">v9.5.0 Cross-Device Sync</p>
        </div>
        <button
          onClick={onLogin}
          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white
                     text-sm font-medium rounded-lg transition-colors"
        >
          🔒 ログイン
        </button>
      </div>

      {/* チャット一覧 */}
      <div className="flex-1 overflow-auto p-4">
        <h2 className="text-sm font-medium text-gray-400 mb-3">📋 最近のチャット</h2>

        {loading && (
          <p className="text-gray-600 text-sm text-center py-8">読み込み中...</p>
        )}

        {!loading && recentChats.length === 0 && (
          <p className="text-gray-600 text-sm text-center py-8">
            チャット履歴がありません
          </p>
        )}

        <div className="space-y-2">
          {recentChats.map(chat => {
            const badge = tabBadge(chat.tab);
            return (
              <div key={chat.id}
                className="bg-gray-900 rounded-lg border border-gray-800 p-3
                           hover:border-gray-700 transition-colors">
                {/* タイトル行 */}
                <div className="flex items-center justify-between mb-1">
                  <h3 className="text-sm font-medium text-gray-200 truncate flex-1">
                    {chat.title || '無題'}
                  </h3>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${badge.color} ml-2 shrink-0`}>
                    {badge.text}
                  </span>
                </div>

                {/* メタ情報 */}
                <div className="flex items-center gap-2 text-[10px] text-gray-600 mb-2">
                  <span>{formatDate(chat.updated_at)}</span>
                  <span>·</span>
                  <span>{chat.message_count}メッセージ</span>
                </div>

                {/* プレビュー */}
                {chat.assistant_preview && (
                  <p className="text-xs text-gray-500 line-clamp-2">
                    {chat.assistant_preview}...
                  </p>
                )}

                {/* ログインして続行 */}
                <button
                  onClick={onLogin}
                  className="mt-2 text-[10px] text-emerald-500 hover:text-emerald-400
                             transition-colors"
                >
                  ログインして続行 →
                </button>
              </div>
            );
          })}
        </div>

        {recentChats.length > 0 && (
          <p className="text-[10px] text-gray-700 text-center mt-4">
            最新{recentChats.length}件を表示 · チャット本文の閲覧にはログインが必要です
          </p>
        )}
      </div>
    </div>
  );
}
```

### 5.6 App.jsx の認証フロー修正

```jsx
// App.jsx 内のメインレンダリング修正

function App() {
  const [token, setToken] = useState(localStorage.getItem('helix_token'));
  const [showLogin, setShowLogin] = useState(false);

  // トークンの有効性確認
  useEffect(() => {
    if (token) {
      fetch('/api/health', {
        headers: { 'Authorization': `Bearer ${token}` }
      }).then(res => {
        if (!res.ok) {
          // トークン無効 → ログアウト状態に
          localStorage.removeItem('helix_token');
          setToken(null);
        }
      }).catch(() => {});
    }
  }, []);

  function handleLogin(newToken) {
    localStorage.setItem('helix_token', newToken);
    setToken(newToken);
    setShowLogin(false);
  }

  function handleLogout() {
    localStorage.removeItem('helix_token');
    setToken(null);
  }

  // 未認証: PreLoginView を表示（ログインモーダルの表示制御付き）
  if (!token) {
    if (showLogin) {
      return <LoginView onLogin={handleLogin} onBack={() => setShowLogin(false)} />;
    }
    return <PreLoginView onLogin={() => setShowLogin(true)} />;
  }

  // 認証済み: 通常のアプリ
  return <MainApp token={token} onLogout={handleLogout} />;
}
```

---

## 6. 機能E: BIBLE更新

### 6.1 バージョン変遷サマリーの欠落補完

現在のBIBLE v9.4.0ではv8.5.0 → v9.3.0 に飛んでおり、v9.0.0〜v9.2.0が欠落している。
以下をバージョン変遷サマリーテーブルの v8.5.0 と v9.3.0 の間に追記すること:

```markdown
| v9.0.0 | Mobile Web | **Web UI基盤（FastAPI + React PWA）/ Tailscale VPN + PIN + JWT認証 / soloAI・mixAI WebSocketストリーミング / iPhoneモバイルアクセス / GPUモニター / PWAアイコン** |
| v9.1.0 | Connected Knowledge | **RAG Bridge（Web版RAG連携）/ ファイル添付（サーバーファイル参照）/ ファイルマネージャータブ / 設定読み取り専用アーキテクチャ** |
| v9.2.0 | Persistent Sessions | **チャット履歴永続化（SQLite web_chats.db）/ 3モードコンテキスト切替（単発/セッション/フル）/ コードブロック・回答コピー機能** |
```

### 6.2 v9.5.0 記載

```markdown
| **v9.5.0** | **Cross-Device Sync** | **Web実行ロック（Windows側オーバーレイ）/ モバイルファイルアップロード / デバイス間ファイル転送（モバイル↔Windows）/ ログアウト後チャット閲覧** |
```

### 6.3 v9.5.0 設計哲学の追加

```markdown
15. **デバイス間透過性** -- モバイルとデスクトップの操作が相互に認識・連携し、実行競合の防止とファイルのシームレスな受け渡しを実現する。Web UIは単なるリモートアクセスではなく、デスクトップの「延長」として機能する（v9.5.0新設）
```

### 6.4 既知の制限事項に追加

```markdown
| 5 | ログアウト後閲覧の範囲 | 認証なしで閲覧可能なのはチャットタイトルと冒頭50文字のプレビューのみ。全文閲覧にはログインが必要。Tailscale VPN内アクセスが前提 | 個人利用のため許容 |
```

### 6.5 BIBLEファイル名

`BIBLE/BIBLE_Helix_AI_Studio_9.5.0.md` として新規作成。
v9.4.0のBIBLEをベースに上記の差分を適用すること。

---

## 7. テスト項目チェックリスト

### 機能A: Web実行ロック
| # | テスト | 期待結果 |
|---|-------|---------|
| 1 | iPhoneでsoloAI実行開始 | Windows側にオーバーレイ「📱 Web UIから実行中」 |
| 2 | 実行完了 | オーバーレイ自動消去、操作復帰 |
| 3 | ロック中にWindows側で入力試行 | オーバーレイが入力をブロック |
| 4 | mixAI実行 | 同様にロック表示 |
| 5 | 異常終了（WebSocket切断） | ロックファイルが残らない（finally保証） |

### 機能B: モバイルファイル添付
| # | テスト | 期待結果 |
|---|-------|---------|
| 6 | 「+」→「📤 この端末からアップロード」 | iPhoneファイル選択UI表示 |
| 7 | 10MB以下のPythonファイル | アップロード成功、添付表示 |
| 8 | 15MBファイル | エラー「サイズ上限超過」 |
| 9 | .exeファイル | エラー「セキュリティ上の理由で不可」 |
| 10 | 添付付きでsoloAI実行 | Claude CLIに添付ファイルが渡される |

### 機能C: ファイル転送
| # | テスト | 期待結果 |
|---|-------|---------|
| 11 | ファイルタブの転送セクション表示 | アップロード済みファイル一覧 |
| 12 | 「↗ プロジェクトにコピー」 | Windows側にファイルコピー |
| 13 | プロジェクトファイルの📥ボタン | iPhoneにダウンロード |
| 14 | .pyファイルをダウンロード | 正しく保存 |

### 機能D: ログアウト後チャット閲覧
| # | テスト | 期待結果 |
|---|-------|---------|
| 15 | 未ログインでWeb UIにアクセス | PreLoginView表示（チャット一覧+ログインボタン） |
| 16 | チャット一覧の内容 | タイトル、タブ種別、日時、メッセージ数、プレビュー50文字が表示 |
| 17 | 「ログインして続行」タップ | ログイン画面に遷移 |
| 18 | ログイン後 | 通常のアプリ画面に遷移、チャット本文が閲覧可能 |
| 19 | チャットが0件の場合 | 「チャット履歴がありません」と表示 |
| 20 | GET /api/chats/public-list | 認証なしで200 OK、チャット一覧JSON返却 |

### 機能E: BIBLE
| # | テスト | 期待結果 |
|---|-------|---------|
| 21 | BIBLEバージョン変遷 | v9.0.0〜v9.5.0が全て記載 |
| 22 | 設計哲学15番 | 「デバイス間透過性」が記載 |

---

## 8. 新規/変更ファイルサマリー

| 種別 | ファイル | 内容 |
|------|---------|------|
| **新規** | `src/web/file_transfer.py` | アップロード制限・バリデーション |
| **新規** | `src/widgets/web_lock_overlay.py` | PyQt6 Webロックオーバーレイ |
| **修正** | `src/web/server.py` | 実行ロック管理（set/release） |
| **修正** | `src/web/api_routes.py` | upload/download/copy-to-project + lock + public-list API |
| **修正** | `src/web/chat_store.py` | list_chats/get_messages に limit パラメータ追加 |
| **修正** | `src/main_window.py` | Webロック監視タイマー |
| **修正** | `src/tabs/helix_orchestrator_tab.py` | WebLockOverlay設置 |
| **修正** | `src/tabs/claude_tab.py` | WebLockOverlay設置 |
| **修正** | `frontend/src/components/InputBar.jsx` | AttachMenu（アップロード+参照） |
| **修正** | `frontend/src/components/FileManagerView.jsx` | TransferSection + ダウンロードボタン |
| **修正** | `frontend/src/App.jsx` | PreLoginView + 認証フロー修正 |
| **変更** | `src/utils/constants.py` | v9.5.0 / "Cross-Device Sync" |
| **変更** | `BIBLE/` | v9.0.0〜v9.2.0補完 + v9.5.0記載 |

---

## 9. セキュリティ考慮事項

| 項目 | 対策 |
|------|------|
| パストラバーサル | resolve() + startswith() でproject_dir外アクセス防止 |
| ファイルサイズ | 10MB上限、ストリーミング読み込みでメモリ保護 |
| 拡張子制限 | ホワイトリスト + ブラックリスト二重チェック |
| 認証 | 全API endpoint で JWT認証必須（public-list除く） |
| public-list | タイトル+50文字プレビューのみ。本文は認証必須。VPN内前提 |
| ネットワーク | Tailscale VPN内のみアクセス可（既存基盤） |
| 実行ロック | ファイルベース（プロセス間通信不要、crash-safe） |

---

## 10. Claude Code CLI 実行コマンド

```powershell
claude -p "v9_5_0_Cross_Device_Sync.md の内容に従ってv9.5.0を実装してください。順序: 機能A（Webロック）→ 機能B（アップロード）→ 機能C（ダウンロード+転送）→ 機能D（ログアウト後チャット閲覧: public-list API + PreLoginView）→ 機能E（BIBLE更新: v9.0.0〜v9.2.0の欠落バージョン補完 + v9.5.0記載）。constants.pyのバージョンを9.5.0、コードネームを'Cross-Device Sync'に更新。BIBLEは BIBLE/ ディレクトリ内の最新BIBLEをベースに更新。frontendビルドも実行すること。" --dangerously-skip-permissions
```
