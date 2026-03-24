"""Helix AI Studio エントリポイント"""

import logging
import os
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8503))
    uvicorn.run(
        "helix_studio.app:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info",
    )
