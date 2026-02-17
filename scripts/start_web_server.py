#!/usr/bin/env python3
"""
Helix AI Studio - スタンドアロンWebサーバー起動スクリプト

PyQt6の importチェーンから完全に独立したエントリーポイント。
launcher.py からサブプロセスとして呼び出される。

uvicorn に文字列パス "src.web.server:app" を渡すことで、
このスクリプト自体は src パッケージを一切 import しない。
uvicorn が内部で必要なモジュールだけをロードするため、
PyQt6 関連の連鎖 import が発生しない。

Usage:
    python scripts/start_web_server.py [PORT]
"""

import os
import sys


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8500

    # プロジェクトルートを sys.path に追加（src パッケージ解決のため）
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    import uvicorn
    uvicorn.run(
        "src.web.server:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
