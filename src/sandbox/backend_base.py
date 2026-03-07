"""Helix AI Studio — Sandbox バックエンド抽象基底クラス

全バックエンド（Windows Sandbox / Docker / Guacamole）が実装する共通インターフェース。
BackendCapability フラグでバックエンド固有の機能有無を宣言し、
VirtualDesktopTab が Capability に応じて UI を動的に切り替える。
"""

import logging
from abc import abstractmethod
from enum import Flag, auto
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from .sandbox_config import SandboxConfig, SandboxInfo, SandboxStatus

logger = logging.getLogger(__name__)


class BackendCapability(Flag):
    """バックエンドが提供する機能フラグ"""
    NONE          = 0
    EMBED_VIEW    = auto()   # アプリ内 NoVNC/WebView 埋め込み
    FILE_BROWSE   = auto()   # コンテナ内ファイル閲覧
    EXEC_COMMAND  = auto()   # コンテナ内コマンド実行
    SCREENSHOT    = auto()   # スクリーンショット取得
    DIFF_PROMOTE  = auto()   # 差分検出＋本番適用 (Promotion)
    STATS         = auto()   # CPU/RAM リソース統計
    NETWORKING    = auto()   # ネットワークモード設定


class SandboxBackend(QObject):
    """Sandbox バックエンドの抽象基底クラス

    全バックエンドはこのクラスを継承し、
    backend_type / capabilities / is_available / create / destroy / get_status を実装する。
    オプション機能は capabilities() に応じてオーバーライドする。
    """

    # シグナル（VirtualDesktopTab が接続する）
    statusChanged = pyqtSignal(str)
    outputReceived = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    # ─── 必須メソッド ───

    @abstractmethod
    def backend_type(self) -> str:
        """バックエンド識別名を返す (例: "windows_sandbox", "docker")"""
        ...

    @abstractmethod
    def capabilities(self) -> BackendCapability:
        """このバックエンドが提供する機能フラグを返す"""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """バックエンドが利用可能かチェック"""
        ...

    @abstractmethod
    def get_unavailable_reason(self) -> str:
        """利用不可時の理由を人間が読める形で返す"""
        ...

    @abstractmethod
    def create(self, config) -> Optional[SandboxInfo]:
        """Sandbox を作成・起動する"""
        ...

    @abstractmethod
    def destroy(self) -> bool:
        """Sandbox を停止・破棄する"""
        ...

    @abstractmethod
    def get_status(self) -> SandboxStatus:
        """現在の Sandbox 状態を返す"""
        ...

    # ─── オプションメソッド（Capability に応じてオーバーライド）───

    def get_diff(self) -> str:
        """Sandbox 内の変更を unified diff 形式で取得 (DIFF_PROMOTE)"""
        return ""

    def screenshot(self) -> Optional[bytes]:
        """スクリーンショットを PNG バイトで返す (SCREENSHOT)"""
        return None

    def list_files(self, path: str = "/workspace") -> list:
        """指定パスのファイル一覧を返す (FILE_BROWSE)"""
        return []

    def read_file(self, path: str) -> bytes:
        """指定パスのファイル内容を返す (FILE_BROWSE)"""
        return b""

    def get_container_stats(self) -> Optional[dict]:
        """CPU/RAM 統計を dict で返す (STATS)"""
        return None

    def get_vnc_url(self) -> str:
        """NoVNC / リモートデスクトップの URL を返す (EMBED_VIEW)"""
        return ""

    def reset_connection(self):
        """キャッシュ済み接続をリセット（再接続用）"""
        pass

    # ─── Docker 互換メソッド（localAI/cloudAI タブとの後方互換）───

    def check_image_exists(self) -> bool:
        """Docker イメージ存在チェック（Docker バックエンドのみ有効）"""
        return False

    def build_image(self, progress_callback=None) -> bool:
        """Docker イメージビルド（Docker バックエンドのみ有効）"""
        return False

    def remove_image(self, force: bool = True) -> bool:
        """Docker イメージ削除（Docker バックエンドのみ有効）"""
        return False

    def exec_in_sandbox(self, command: str) -> Optional[str]:
        """Sandbox 内でコマンド実行（EXEC_COMMAND）"""
        return None

    def get_workspace_path(self) -> str:
        """ホスト側ワークスペースパスを返す"""
        return ""
