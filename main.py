"""Helix AI Studio エントリポイント

run.py と同等の起動スクリプト。
python main.py でアプリを起動できます。
"""
import logging
import os

import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8504))
    uvicorn.run(
        "helix_studio.app:app",
        host="0.0.0.0",
        port=port,
        reload=os.environ.get("RENDER") is None,
        log_level="info",
    )
