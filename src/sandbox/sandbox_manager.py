"""Helix AI Studio — SandboxManager

Docker コンテナの CRUD、ファイル操作、コマンド実行を管理する。
Docker が未インストールでも ImportError を投げずに graceful に動作する。
"""

import logging
import os
import re
import socket
import time
from pathlib import Path
from typing import Optional, Callable

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .sandbox_config import SandboxConfig, SandboxInfo, SandboxStatus

logger = logging.getLogger(__name__)

# docker パッケージはオプション依存
try:
    import docker
    from docker.errors import DockerException, ImageNotFound, NotFound, APIError
    DOCKER_SDK_AVAILABLE = True
except ImportError:
    DOCKER_SDK_AVAILABLE = False
    logger.info("[SandboxManager] docker SDK not installed — sandbox features disabled")


def _find_free_port(start: int = 6080, end: int = 6180) -> int:
    """空きポートを検索する"""
    for port in range(start, end):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"No free port found in range {start}-{end}")


class SandboxManager(QObject):
    """Docker Sandbox コンテナの管理"""

    statusChanged = pyqtSignal(str)
    outputReceived = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._client = None
        self._active_sandbox: Optional[SandboxInfo] = None
        self._timeout_timer: Optional[QTimer] = None
        self._status = SandboxStatus.NONE

    # ─── Docker 接続 ───

    def _get_client(self):
        """Docker クライアントを遅延初期化"""
        if not DOCKER_SDK_AVAILABLE:
            return None
        if self._client is None:
            try:
                self._client = docker.from_env()
                self._client.ping()
                logger.info("[SandboxManager] Docker connection established.")
            except Exception as e:
                logger.warning(
                    f"[SandboxManager] Docker connection failed: {e}\n"
                    "Docker Desktop / Rancher Desktop が起動していない可能性があります。"
                    "コンテナランタイムを起動してから「🔄 更新」ボタンを押してください。"
                )
                self._client = None
        return self._client

    def reset_connection(self):
        """キャッシュ済み Docker クライアントをリセット（再接続に使用）"""
        self._client = None
        logger.debug("[SandboxManager] Client cache cleared (reset_connection).")

    @staticmethod
    def _is_docker_available_via_cli() -> bool:
        """CLI fallback: `docker version` が成功するか確認（SDK が使えない場合の補完）"""
        try:
            import subprocess
            result = subprocess.run(
                ["docker", "version"],
                capture_output=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_docker_unavailable_reason(self) -> str:
        """Docker が利用不可な理由を人間が読める形で返す"""
        if not DOCKER_SDK_AVAILABLE:
            return "docker SDK 未インストール: `pip install docker` を実行してください。"

        # CLI で確認
        if not self._is_docker_available_via_cli():
            return (
                "docker CLI が見つからないか、Docker エンジンが起動していません。\n"
                "Docker Desktop または Rancher Desktop を起動してください。"
            )

        # CLI は OK だが SDK の接続に失敗する場合（ソケット差異など）
        return (
            "docker CLI は有効ですが、Python SDK の接続に失敗しています。\n"
            "DOCKER_HOST 環境変数が正しいか確認してください。\n"
            "Rancher Desktop を使用している場合は Moby/dockerd エンジンを選択してください。"
        )

    def is_docker_available(self) -> bool:
        """Docker が利用可能かチェック（SDK→CLI 2段フォールバック）"""
        # 1段目: SDK で確認
        if DOCKER_SDK_AVAILABLE:
            try:
                client = self._get_client()
                if client:
                    client.ping()
                    return True
                # キャッシュが None = 前回失敗 → CLI へフォールバック
            except Exception:
                # 接続は取れていたが ping 失敗 = ソケットが失われた（再起動等）
                self.reset_connection()

        # 2段目: CLI フォールバック（SDK 未導入 or SDK 接続失敗時）
        if self._is_docker_available_via_cli():
            logger.info("[SandboxManager] Docker available via CLI fallback (SDK unavailable/failed).")
            return True

        return False

    def check_image_exists(self) -> bool:
        """helix-sandbox:latest イメージが存在するかチェック"""
        client = self._get_client()
        if not client:
            return False
        try:
            client.images.get("helix-sandbox:latest")
            return True
        except Exception:
            return False

    def build_image(self, progress_callback: Optional[Callable] = None) -> bool:
        """Dockerfile からイメージをビルド"""
        client = self._get_client()
        if not client:
            return False

        dockerfile_dir = Path(__file__).parent.parent.parent / "docker" / "sandbox"
        if not (dockerfile_dir / "Dockerfile").exists():
            self.errorOccurred.emit("Dockerfile not found")
            return False

        try:
            if progress_callback:
                progress_callback("Building sandbox image...")

            _image, logs = client.images.build(
                path=str(dockerfile_dir),
                tag="helix-sandbox:latest",
                rm=True,
            )
            for chunk in logs:
                if "stream" in chunk:
                    msg = chunk["stream"].strip()
                    if msg and progress_callback:
                        progress_callback(msg)

            logger.info("[SandboxManager] Image built: helix-sandbox:latest")
            return True
        except Exception as e:
            logger.error(f"[SandboxManager] Build failed: {e}")
            self.errorOccurred.emit(f"Build failed: {e}")
            return False

    # ─── コンテナ CRUD ───

    def create(self, config: SandboxConfig) -> Optional[SandboxInfo]:
        """sandbox コンテナを作成・起動"""
        client = self._get_client()
        if not client:
            self.errorOccurred.emit("Docker is not available")
            return None

        self._set_status(SandboxStatus.CREATING)

        try:
            # ポート割り当て
            novnc_port = _find_free_port(6080, 6180)
            vnc_port = _find_free_port(5900, 5999)

            container_name = f"helix-sandbox-{int(time.time())}"

            # Volume マウント設定
            volumes = {}
            if config.workspace_path and os.path.isdir(config.workspace_path):
                mode = "ro" if config.mount_readonly else "rw"
                volumes[os.path.abspath(config.workspace_path)] = {
                    "bind": "/workspace",
                    "mode": mode,
                }

            # 環境変数
            environment = {
                "DISPLAY": ":99",
                "RESOLUTION": f"{config.resolution}x24",
            }
            if config.vnc_password:
                environment["VNC_PASSWORD"] = config.vnc_password

            # CPU 制限
            nano_cpus = int(config.cpu_limit * 1e9)

            # v12.0.1: network_disabled=True だとポートフォワーディングが無効化され
            # NoVNC にアクセスできないため、最低限 bridge モードを使用する
            effective_network = config.network_mode
            if effective_network == "none":
                effective_network = "bridge"

            # host.docker.internal でコンテナ内からホストのサービス
            # （Ollama localhost:11434 等）にアクセス可能にする
            extra_hosts = {"host.docker.internal": "host-gateway"}

            container = client.containers.run(
                image=config.image_name,
                detach=True,
                name=container_name,
                ports={"5900/tcp": vnc_port, "6080/tcp": novnc_port},
                environment=environment,
                volumes=volumes,
                nano_cpus=nano_cpus,
                mem_limit=config.memory_limit,
                network_mode=effective_network,
                extra_hosts=extra_hosts,
            )

            # 起動確認 (最大10秒)
            for _ in range(20):
                container.reload()
                if container.status == "running":
                    break
                time.sleep(0.5)

            if container.status != "running":
                raise RuntimeError(f"Container failed to start: {container.status}")

            # v12.0.1: NoVNC HTTP サービスの起動完了を待機（最大20秒）
            import urllib.request
            for i in range(40):
                try:
                    req = urllib.request.urlopen(
                        f"http://localhost:{novnc_port}/vnc.html", timeout=2
                    )
                    if req.status == 200:
                        logger.info(f"[SandboxManager] NoVNC HTTP ready after {(i+1)*0.5:.1f}s")
                        break
                except Exception:
                    time.sleep(0.5)
            else:
                logger.warning("[SandboxManager] NoVNC HTTP not ready after 20s, proceeding anyway")

            vnc_url = f"http://localhost:{novnc_port}/vnc.html"
            if config.vnc_password:
                vnc_url += f"?autoconnect=true&resize=scale&password={config.vnc_password}"
            else:
                vnc_url += "?autoconnect=true&resize=scale"

            info = SandboxInfo(
                sandbox_id=container.short_id,
                container_name=container_name,
                status=SandboxStatus.RUNNING,
                vnc_url=vnc_url,
                vnc_port=vnc_port,
                novnc_port=novnc_port,
                workspace_path=config.workspace_path,
                config=config,
            )

            self._active_sandbox = info
            self._set_status(SandboxStatus.RUNNING)

            # タイムアウトタイマー
            if config.timeout_minutes > 0:
                self._start_timeout(config.timeout_minutes)

            logger.info(f"[SandboxManager] Sandbox created: {container_name} (NoVNC: {novnc_port})")
            return info

        except Exception as e:
            logger.error(f"[SandboxManager] Create failed: {e}")
            # 残骸コンテナを掃除
            try:
                client = self._get_client()
                if client:
                    c = client.containers.get(container_name)
                    c.remove(force=True)
                    logger.info(f"[SandboxManager] Cleaned up failed container: {container_name}")
            except Exception:
                pass
            self._set_status(SandboxStatus.ERROR)
            self.errorOccurred.emit(str(e))
            return None

    def execute(self, command: str, workdir: str = "/workspace") -> dict:
        """sandbox 内でコマンド実行"""
        container = self._get_container()
        if not container:
            return {"exit_code": -1, "stdout": "", "stderr": "Sandbox not running"}

        try:
            result = container.exec_run(
                cmd=["bash", "-c", command],
                workdir=workdir,
                demux=True,
            )
            stdout = result.output[0].decode("utf-8", errors="replace") if result.output[0] else ""
            stderr = result.output[1].decode("utf-8", errors="replace") if result.output[1] else ""
            return {"exit_code": result.exit_code, "stdout": stdout, "stderr": stderr}
        except Exception as e:
            return {"exit_code": -1, "stdout": "", "stderr": str(e)}

    def write_file(self, path: str, content: str) -> dict:
        """sandbox 内にファイルを書き込む"""
        if not self._validate_sandbox_path(path):
            return {"error": "Invalid path: path traversal detected"}

        container = self._get_container()
        if not container:
            return {"error": "Sandbox not running"}

        try:
            # Python を使って安全にファイル書き込み
            escaped = content.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
            cmd = f"python3 -c \"import pathlib; p=pathlib.Path('{path}'); p.parent.mkdir(parents=True, exist_ok=True); p.write_text('{escaped}')\""
            result = container.exec_run(cmd=["bash", "-c", cmd], workdir="/workspace")
            if result.exit_code == 0:
                return {"success": True, "path": path}
            else:
                output = result.output.decode("utf-8", errors="replace") if result.output else ""
                return {"error": f"Write failed: {output}"}
        except Exception as e:
            return {"error": str(e)}

    def read_file(self, path: str) -> dict:
        """sandbox 内のファイルを読む"""
        if not self._validate_sandbox_path(path):
            return {"error": "Invalid path: path traversal detected"}

        result = self.execute(f"cat '{path}'")
        if result["exit_code"] == 0:
            return {"content": result["stdout"], "path": path}
        return {"error": result["stderr"] or "File not found"}

    def list_dir(self, path: str = "/workspace") -> dict:
        """sandbox 内のディレクトリ一覧（構造化データ）"""
        if not self._validate_sandbox_path(path):
            return {"error": "Invalid path: path traversal detected"}

        # JSON 形式で取得: name, type(file/dir/link), size, permissions
        script = (
            f"python3 -c \""
            f"import os, json, stat; "
            f"p='{path}'; entries=[]; "
            f"[entries.append({{"
            f"'name':e,'type':'dir' if os.path.isdir(os.path.join(p,e)) else 'file',"
            f"'size':os.path.getsize(os.path.join(p,e)) if os.path.isfile(os.path.join(p,e)) else 0"
            f"}}) for e in sorted(os.listdir(p))]; "
            f"print(json.dumps({{'path':p,'entries':entries}}))\""
        )
        result = self.execute(script)
        if result["exit_code"] == 0:
            try:
                import json
                data = json.loads(result["stdout"].strip())
                data["ok"] = True
                return data
            except Exception:
                pass
            # フォールバック: 生テキスト
            return {"ok": True, "listing": result["stdout"], "path": path}
        return {"error": result["stderr"] or "Directory not found"}

    def screenshot(self) -> Optional[bytes]:
        """sandbox 内のスクリーンショットを PNG で取得"""
        container = self._get_container()
        if not container:
            return None

        try:
            result = container.exec_run(
                cmd=["bash", "-c", "import -window root -display :99 png:- 2>/dev/null"],
                demux=True,
            )
            if result.exit_code == 0 and result.output[0]:
                return result.output[0]
        except Exception as e:
            logger.debug(f"[SandboxManager] Screenshot failed: {e}")
        return None

    def get_diff(self) -> str:
        """sandbox 内の変更差分を取得"""
        container = self._get_container()
        if not container:
            return ""

        # git repo の場合は git diff を使用
        result = self.execute("git diff --no-color 2>/dev/null || diff -rq /workspace /workspace-original 2>/dev/null || echo 'No diff available'")
        return result.get("stdout", "")

    def snapshot(self) -> Optional[str]:
        """現在の状態をスナップショット (docker commit)"""
        container = self._get_container()
        if not container:
            return None

        try:
            tag = f"helix-sandbox-snapshot:{int(time.time())}"
            container.commit(repository="helix-sandbox-snapshot", tag=str(int(time.time())))
            return tag
        except Exception as e:
            logger.error(f"[SandboxManager] Snapshot failed: {e}")
            return None

    def destroy(self) -> bool:
        """sandbox コンテナ + volume を破棄"""
        container = self._get_container()
        if not container:
            self._active_sandbox = None
            self._set_status(SandboxStatus.NONE)
            return True

        try:
            container.stop(timeout=5)
            container.remove(v=True)
            logger.info(f"[SandboxManager] Sandbox destroyed: {self._active_sandbox.container_name}")
        except Exception as e:
            logger.error(f"[SandboxManager] Destroy failed: {e}")

        self._active_sandbox = None
        self._stop_timeout()
        self._set_status(SandboxStatus.NONE)
        return True

    # ─── 状態管理 ───

    def get_status(self) -> SandboxStatus:
        """現在の sandbox 状態"""
        return self._status

    def get_info(self) -> Optional[SandboxInfo]:
        """稼働中の sandbox 情報"""
        return self._active_sandbox

    def get_vnc_url(self) -> Optional[str]:
        """NoVNC の接続 URL"""
        if self._active_sandbox:
            return self._active_sandbox.vnc_url
        return None

    # ─── 内部ヘルパー ───

    def _get_container(self):
        """アクティブなコンテナオブジェクトを取得"""
        if not self._active_sandbox:
            return None
        client = self._get_client()
        if not client:
            return None
        try:
            container = client.containers.get(self._active_sandbox.container_name)
            if container.status == "running":
                return container
        except Exception:
            pass
        return None

    def _set_status(self, status: SandboxStatus):
        """状態を更新してシグナル発火"""
        self._status = status
        self.statusChanged.emit(status.value)

    def _validate_sandbox_path(self, path: str) -> bool:
        """パストラバーサル検査（sandbox 内の POSIX パスとして検証）"""
        # ".." を含むパスを拒否
        import posixpath
        normalized = posixpath.normpath(path)
        if ".." in normalized.split("/"):
            return False
        # 絶対パスの場合は /workspace 配下であること
        if path.startswith("/") and not normalized.startswith("/workspace"):
            return False
        return True

    def _start_timeout(self, minutes: int):
        """タイムアウトタイマー開始"""
        self._stop_timeout()
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self._on_timeout)
        self._timeout_timer.start(minutes * 60 * 1000)

    def _stop_timeout(self):
        """タイムアウトタイマー停止"""
        if self._timeout_timer:
            self._timeout_timer.stop()
            self._timeout_timer = None

    def _on_timeout(self):
        """タイムアウト時のコールバック"""
        logger.info("[SandboxManager] Sandbox timeout — auto-destroying")
        if self._active_sandbox and self._active_sandbox.config and self._active_sandbox.config.auto_cleanup:
            self.destroy()
        else:
            self._set_status(SandboxStatus.STOPPED)

    def get_container_stats(self) -> Optional[dict]:
        """コンテナのリソース使用状況を取得"""
        container = self._get_container()
        if not container:
            return None
        try:
            stats = container.stats(stream=False)
            # CPU 使用率計算
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                        stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                           stats["precpu_stats"]["system_cpu_usage"]
            cpu_percent = (cpu_delta / system_delta) * 100.0 if system_delta > 0 else 0.0

            # メモリ使用量
            mem_usage = stats["memory_stats"].get("usage", 0)
            mem_limit = stats["memory_stats"].get("limit", 0)
            mem_mb = mem_usage / (1024 * 1024)

            return {
                "cpu_percent": round(cpu_percent, 1),
                "memory_mb": round(mem_mb, 1),
                "memory_limit_mb": round(mem_limit / (1024 * 1024), 1),
            }
        except Exception:
            return None
