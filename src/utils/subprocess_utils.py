"""
Helix AI Studio - Subprocess Utilities (v8.5.0 Patch 2)
Windows上でサブプロセスのコンソールウィンドウを非表示にして実行するユーティリティ
"""

import subprocess
import sys
from typing import Any


def run_hidden(cmd, **kwargs) -> subprocess.CompletedProcess:
    """Windows上でサブプロセスのコンソールウィンドウを非表示にして実行

    subprocess.run() のドロップイン置換。
    Windows以外のプラットフォームでは通常の subprocess.run() と同じ動作。

    Args:
        cmd: 実行コマンド (list or str)
        **kwargs: subprocess.run() に渡す追加引数

    Returns:
        subprocess.CompletedProcess
    """
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs.setdefault("startupinfo", si)
        kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
    return subprocess.run(cmd, **kwargs)


def popen_hidden(cmd, **kwargs) -> subprocess.Popen:
    """Windows上でサブプロセスのコンソールウィンドウを非表示にしてPopen実行

    subprocess.Popen() のドロップイン置換。

    Args:
        cmd: 実行コマンド (list or str)
        **kwargs: subprocess.Popen() に渡す追加引数

    Returns:
        subprocess.Popen
    """
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs.setdefault("startupinfo", si)
        kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
    return subprocess.Popen(cmd, **kwargs)
