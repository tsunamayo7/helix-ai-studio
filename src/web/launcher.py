"""
Helix AI Studio - Webサーバーランチャー (v9.3.0)

PyQt6プロセスからWebサーバーをサブプロセスとして起動するための
軽量モジュール。fastapi等の重い依存を一切importしないため、
PyQt6側の ``from ..web.launcher import start_server_background``
でimportエラーが発生しない。

起動方式:
  uvicorn を直接サブプロセスで起動する。
  PyInstaller EXE環境ではsys.executableがEXE自身を指すため、
  sys.executableは使用せず、実際のpython.exeを検索して使用する。
"""

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# プロジェクトルート
_PROJECT_ROOT = Path(__file__).parent.parent.parent


def _find_python() -> str:
    """
    実際のPythonインタープリタのパスを返す。

    PyInstaller EXE環境では sys.executable が EXE 自身を指すため、
    そのまま使うとEXEが再起動してしまう。
    以下の優先順位で python.exe を検索する:
      1. sys.executable が .exe で終わらない or 'python' を含む → そのまま使用
      2. PyInstaller の _MEIPASS 内の python.exe
      3. EXE と同じディレクトリの python.exe / pythonw.exe
      4. venv の python.exe
      5. PATH 上の python.exe
    """
    exe = sys.executable

    # 通常のPython実行時: sys.executable が python を指している
    exe_name = Path(exe).stem.lower()
    if 'python' in exe_name:
        return exe

    # --- PyInstaller frozen 環境 ---
    logger.info(f"Frozen environment detected: sys.executable={exe}")

    # _MEIPASS 内の python
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        for name in ('python.exe', 'python3.exe', 'python'):
            candidate = Path(meipass) / name
            if candidate.exists():
                logger.info(f"Found Python in _MEIPASS: {candidate}")
                return str(candidate)

    # EXE と同じディレクトリ
    exe_dir = Path(exe).parent
    for name in ('python.exe', 'pythonw.exe', 'python3.exe', 'python'):
        candidate = exe_dir / name
        if candidate.exists():
            logger.info(f"Found Python next to exe: {candidate}")
            return str(candidate)

    # venv（プロジェクトルート/.venv or venv）
    for venv_dir in ('.venv', 'venv'):
        candidate = _PROJECT_ROOT / venv_dir / 'Scripts' / 'python.exe'
        if candidate.exists():
            logger.info(f"Found Python in venv: {candidate}")
            return str(candidate)

    # PATH 上の python
    found = shutil.which('python')
    if found:
        logger.info(f"Found Python on PATH: {found}")
        return found

    found = shutil.which('python3')
    if found:
        logger.info(f"Found Python3 on PATH: {found}")
        return found

    # 最終手段: sys.executable をそのまま返す（動かない可能性あり）
    logger.warning(f"Could not find python interpreter, falling back to {exe}")
    return exe


class SubprocessWebServer:
    """
    PyQt6から起動するWebサーバー（サブプロセス版）。

    ``python -c "import uvicorn; uvicorn.run(...)"`` をサブプロセスとして実行する。
    外部スクリプトファイルにも依存しない完全自己完結型。
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8500):
        self.host = host
        self.port = port
        self._process: subprocess.Popen | None = None

    def start(self):
        """サブプロセスでサーバーを起動"""
        if self.is_running:
            logger.warning("Web server is already running")
            return

        python = _find_python()

        # python -c でインラインスクリプトとして起動。
        # 外部スクリプトファイルに依存しない。
        # uvicorn に文字列パスを渡すことで src パッケージの直接 import を回避。
        inline_script = (
            "import sys, os;"
            f"sys.path.insert(0, os.getcwd());"
            "import uvicorn;"
            f"uvicorn.run('src.web.server:app',"
            f"host='{self.host}',port={self.port},"
            "log_level='info',access_log=True)"
        )

        cmd = [python, "-c", inline_script]
        logger.info(f"Starting web server: python={python}, port={self.port}")

        env = {**os.environ, "HELIX_WEB_SERVER_ONLY": "1"}

        kwargs = dict(
            cwd=str(_PROJECT_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        # Windows: コンソールウィンドウを表示しない
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        self._process = subprocess.Popen(cmd, **kwargs)
        logger.info(f"Web server process started (pid={self._process.pid})")

    def stop(self):
        """サーバープロセスを終了"""
        if self._process is None:
            return

        if self._process.poll() is None:
            logger.info(f"Terminating web server (pid={self._process.pid})")
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Web server did not terminate, killing...")
                self._process.kill()

        self._process = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None


def start_server_background(port: int = 8500) -> SubprocessWebServer:
    """
    PyQt6からバックグラウンドでWebサーバーを起動する。

    python -c "import uvicorn; uvicorn.run(...)" をサブプロセスとして実行。
    PyInstaller EXE環境でも実際のpython.exeを使うため、
    EXEが再起動してしまう問題が発生しない。
    """
    server = SubprocessWebServer(port=port)
    server.start()
    return server
