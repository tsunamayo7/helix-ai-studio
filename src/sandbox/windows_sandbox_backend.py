"""Helix AI Studio — Windows Sandbox バックエンド

Windows 11 Pro/Enterprise/Education に標準搭載の Windows Sandbox を利用して
隔離環境を提供する。Docker Desktop 不要で一般ユーザーが即座に利用可能。

制約:
- 同時に 1 インスタンスのみ
- エフェメラル（終了時に全データ消失、MappedFolder 経由で永続化）
- 外部ウィンドウのみ（アプリ内埋め込み不可）
- コンテナ内コマンド実行 API なし（24H2 以降で限定的に対応）
"""

import logging
import os
import platform
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QTimer

from .backend_base import BackendCapability, SandboxBackend
from .sandbox_config import SandboxInfo, SandboxStatus

logger = logging.getLogger(__name__)


class WindowsSandboxBackend(SandboxBackend):
    """Windows Sandbox バックエンド"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = SandboxStatus.NONE
        self._wsb_path: Optional[str] = None
        self._process: Optional[subprocess.Popen] = None
        self._workspace_path: str = ""
        self._sandbox_info: Optional[SandboxInfo] = None

        # プロセス監視タイマー
        self._monitor_timer = QTimer(self)
        self._monitor_timer.timeout.connect(self._check_process)
        self._monitor_timer.setInterval(3000)  # 3秒間隔

    # ─── 必須メソッド ───

    def backend_type(self) -> str:
        return "windows_sandbox"

    def capabilities(self) -> BackendCapability:
        return BackendCapability.DIFF_PROMOTE

    def is_available(self) -> bool:
        """Windows Sandbox が利用可能かチェック"""
        if platform.system() != "Windows":
            return False
        wsb_exe = self._get_wsb_exe_path()
        return wsb_exe.exists()

    def get_unavailable_reason(self) -> str:
        """利用不可時の理由"""
        if platform.system() != "Windows":
            return "Windows Sandbox は Windows でのみ利用可能です。"

        wsb_exe = self._get_wsb_exe_path()
        if not wsb_exe.exists():
            return (
                "Windows Sandbox が有効化されていません。\n\n"
                "【有効化手順】\n"
                "1. 設定 → アプリ → オプション機能 → Windows のその他の機能\n"
                "2. 「Windows サンドボックス」にチェックを入れる\n"
                "3. PC を再起動する\n\n"
                "※ Windows 11 Pro / Enterprise / Education が必要です。\n"
                "※ BIOS で仮想化 (VT-x / AMD-V) を有効にしてください。"
            )

        return ""

    def create(self, config) -> Optional[SandboxInfo]:
        """Windows Sandbox を起動"""
        if not self.is_available():
            self.errorOccurred.emit(self.get_unavailable_reason())
            return None

        # 既存プロセスチェック
        if self._is_sandbox_running():
            self.errorOccurred.emit(
                "Windows Sandbox は既に起動中です。\n"
                "同時に複数のインスタンスは実行できません。\n"
                "既存の Sandbox を閉じてから再試行してください。"
            )
            return None

        self._set_status(SandboxStatus.CREATING)

        try:
            # ワークスペースパス取得
            workspace = getattr(config, 'workspace_path', '')
            if not workspace:
                workspace = str(Path.cwd())
            self._workspace_path = workspace

            # .wsb ファイル生成
            wsb_config = self._generate_wsb_config(config)
            self._wsb_path = self._write_wsb_file(wsb_config)

            # Windows Sandbox 起動
            wsb_exe = str(self._get_wsb_exe_path())
            self._process = subprocess.Popen(
                [wsb_exe, self._wsb_path],
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            )

            # SandboxInfo 生成
            self._sandbox_info = SandboxInfo(
                sandbox_id=f"wsb-{self._process.pid}",
                container_name="WindowsSandbox",
                status=SandboxStatus.RUNNING,
                backend_type="windows_sandbox",
                vnc_url="",
                workspace_path=self._workspace_path,
            )

            self._set_status(SandboxStatus.RUNNING)
            self._monitor_timer.start()

            logger.info(f"[WindowsSandbox] Started (PID: {self._process.pid})")
            return self._sandbox_info

        except FileNotFoundError:
            self.errorOccurred.emit("WindowsSandbox.exe が見つかりません。")
            self._set_status(SandboxStatus.ERROR)
            return None
        except Exception as e:
            logger.error(f"[WindowsSandbox] Start failed: {e}")
            self.errorOccurred.emit(f"Windows Sandbox の起動に失敗しました: {e}")
            self._set_status(SandboxStatus.ERROR)
            return None

    def destroy(self) -> bool:
        """Windows Sandbox を終了"""
        self._monitor_timer.stop()

        try:
            # taskkill で WindowsSandbox.exe を終了
            subprocess.run(
                ["taskkill", "/F", "/IM", "WindowsSandbox.exe"],
                capture_output=True, timeout=10,
            )
            logger.info("[WindowsSandbox] Stopped via taskkill")
        except Exception as e:
            logger.warning(f"[WindowsSandbox] taskkill failed: {e}")

        self._process = None
        self._sandbox_info = None
        self._set_status(SandboxStatus.STOPPED)

        # 一時 .wsb ファイルを削除
        self._cleanup_wsb_file()

        return True

    def get_status(self) -> SandboxStatus:
        return self._status

    # ─── オプションメソッド ───

    def get_diff(self) -> str:
        """MappedFolder 経由の変更差分を検出"""
        if not self._workspace_path or not Path(self._workspace_path).exists():
            return ""

        try:
            # git diff を使用（ワークスペースが git 管理下の場合）
            result = subprocess.run(
                ["git", "diff"],
                capture_output=True, text=True, timeout=30,
                cwd=self._workspace_path,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout

            # git diff --cached も含む
            result2 = subprocess.run(
                ["git", "diff", "--cached"],
                capture_output=True, text=True, timeout=30,
                cwd=self._workspace_path,
            )
            if result2.returncode == 0 and result2.stdout.strip():
                return result.stdout + "\n" + result2.stdout

        except FileNotFoundError:
            logger.debug("[WindowsSandbox] git not found for diff detection")
        except Exception as e:
            logger.warning(f"[WindowsSandbox] diff detection failed: {e}")

        return ""

    def get_workspace_path(self) -> str:
        return self._workspace_path

    # ─── .wsb ファイル生成 ───

    def _generate_wsb_config(self, config) -> str:
        """SandboxConfig / WindowsSandboxConfig から .wsb XML を生成"""
        root = ET.Element("Configuration")

        # VGpu
        vgpu = getattr(config, 'vgpu', 'Enable')
        ET.SubElement(root, "VGpu").text = vgpu

        # Networking
        networking = getattr(config, 'networking', 'Default')
        ET.SubElement(root, "Networking").text = networking

        # ClipboardRedirection
        clipboard = getattr(config, 'clipboard', 'Enable')
        ET.SubElement(root, "ClipboardRedirection").text = clipboard

        # MemoryInMB
        memory_mb = getattr(config, 'memory_mb', None)
        if memory_mb is None:
            # SandboxConfig からの変換（memory_limit "2g" → 2048）
            mem_str = getattr(config, 'memory_limit', '2g')
            try:
                if isinstance(mem_str, str) and mem_str.endswith('g'):
                    memory_mb = int(mem_str[:-1]) * 1024
                elif isinstance(mem_str, (int, float)):
                    memory_mb = int(mem_str) * 1024
                else:
                    memory_mb = 2048
            except (ValueError, TypeError):
                memory_mb = 2048
        ET.SubElement(root, "MemoryInMB").text = str(memory_mb)

        # MappedFolders
        workspace = getattr(config, 'workspace_path', '')
        if workspace and Path(workspace).exists():
            mapped_folders = ET.SubElement(root, "MappedFolders")
            folder = ET.SubElement(mapped_folders, "MappedFolder")
            ET.SubElement(folder, "HostFolder").text = str(Path(workspace).resolve())
            ET.SubElement(folder, "SandboxFolder").text = r"C:\workspace"

            readonly = getattr(config, 'mount_readonly', False)
            ET.SubElement(folder, "ReadOnly").text = str(readonly).lower()

        # LogonCommand
        logon_cmd = getattr(config, 'logon_command', '')
        if not logon_cmd:
            if workspace:
                logon_cmd = r"explorer.exe C:\workspace"
            else:
                logon_cmd = "explorer.exe"
        logon = ET.SubElement(root, "LogonCommand")
        ET.SubElement(logon, "Command").text = logon_cmd

        # XML を文字列に変換
        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="unicode", xml_declaration=False)

    def _write_wsb_file(self, xml_content: str) -> str:
        """一時 .wsb ファイルを書き出す"""
        temp_dir = Path(tempfile.gettempdir()) / "helix_sandbox"
        temp_dir.mkdir(exist_ok=True)

        wsb_path = temp_dir / "helix_workspace.wsb"
        wsb_path.write_text(xml_content, encoding="utf-8")
        logger.debug(f"[WindowsSandbox] WSB file written: {wsb_path}")
        return str(wsb_path)

    def _cleanup_wsb_file(self):
        """一時 .wsb ファイルを削除"""
        if self._wsb_path:
            try:
                Path(self._wsb_path).unlink(missing_ok=True)
            except Exception:
                pass
            self._wsb_path = None

    # ─── プロセス監視 ───

    def _check_process(self):
        """Windows Sandbox プロセスの生存確認"""
        if not self._is_sandbox_running():
            logger.info("[WindowsSandbox] Process terminated (detected by monitor)")
            self._monitor_timer.stop()
            self._process = None
            self._sandbox_info = None
            self._set_status(SandboxStatus.STOPPED)
            self._cleanup_wsb_file()
            self.statusChanged.emit("stopped")

    def _is_sandbox_running(self) -> bool:
        """WindowsSandbox.exe が実行中かチェック"""
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq WindowsSandbox.exe", "/NH"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            )
            return "WindowsSandbox.exe" in result.stdout
        except Exception:
            return False

    # ─── ユーティリティ ───

    @staticmethod
    def _get_wsb_exe_path() -> Path:
        """WindowsSandbox.exe のパスを返す"""
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        return Path(system_root) / "System32" / "WindowsSandbox.exe"

    def _set_status(self, status: SandboxStatus):
        """状態を更新してシグナルを発火"""
        self._status = status
        self.statusChanged.emit(status.value)
