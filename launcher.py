#!/usr/bin/env python3
"""
Helix AI Studio Launcher (v11.9.4)

薄いランチャーEXE。同ディレクトリの HelixAIStudio.py をシステム Python で起動する。
- ソースコード変更時にEXE再ビルド不要
- アイコンは HelixAIStudio.py 側の AppUserModelID + setWindowIcon で制御
"""
import sys
import os
import subprocess
import shutil


def _show_error(message: str, title: str = "Helix AI Studio - Error") -> None:
    """クロスプラットフォームのエラーダイアログを表示する（ランチャー専用インライン版）。"""
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
        except Exception:
            pass
    elif sys.platform == 'darwin':
        try:
            safe_msg = message.replace('"', '\\"')
            safe_title = title.replace('"', '\\"')
            subprocess.run(
                [
                    'osascript', '-e',
                    f'display dialog "{safe_msg}" with title "{safe_title}" '
                    f'buttons {{"OK"}} with icon stop',
                ],
                timeout=10,
            )
        except Exception:
            pass
    else:
        print(f"[{title}] {message}", file=sys.stderr)


def main():
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))

    entry_point = os.path.join(app_dir, 'HelixAIStudio.py')

    if not os.path.exists(entry_point):
        _show_error(f"HelixAIStudio.py が見つかりません:\n{entry_point}")
        return 1

    # システムの python.exe を探す (pythonw より python を優先)
    python_exe = shutil.which('python') or shutil.which('pythonw')
    if not python_exe:
        _show_error(
            "Python が見つかりません。\n\n"
            "Python 3.10 以上をインストールし、PATH に追加してください。\n"
            "https://www.python.org/downloads/"
        )
        return 1

    # サブプロセスとして起動し、終了を待つ
    # python.exe の場合は CREATE_NO_WINDOW でコンソール窓を非表示にする
    creation_flags = 0
    if os.name == 'nt' and 'pythonw' not in os.path.basename(python_exe).lower():
        creation_flags = subprocess.CREATE_NO_WINDOW

    proc = subprocess.Popen(
        [python_exe, entry_point],
        cwd=app_dir,
        creationflags=creation_flags,
    )
    proc.wait()
    return proc.returncode


if __name__ == '__main__':
    sys.exit(main())
