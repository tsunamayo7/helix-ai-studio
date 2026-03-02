"""
Helix Pilot Tool — アプリ内統合用シングルトンラッパー

scripts/helix_pilot.py の HelixPilot クラスをラップし、
デスクトップ GUI タブ（cloudAI / localAI / mixAI）から呼び出し可能にする。

使用パターン:
    tool = HelixPilotTool.get_instance()
    if tool.is_available:
        result = tool.execute("describe", {"window": "Helix AI Studio"})
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# アプリルートパス
_APP_ROOT = Path(__file__).parent.parent.parent


class HelixPilotTool:
    """Helix Pilot シングルトンラッパー"""

    _instance: Optional["HelixPilotTool"] = None

    def __init__(self):
        self._pilot = None
        self._config_path = _APP_ROOT / "config" / "helix_pilot.json"
        self._available: Optional[bool] = None
        self._last_error: str = ""

    @classmethod
    def get_instance(cls) -> "HelixPilotTool":
        """シングルトンインスタンスを取得"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def is_available(self) -> bool:
        """Pilot が利用可能か（Ollama接続 + Visionモデル存在）"""
        if self._available is not None:
            return self._available
        self._available = self._check_availability()
        return self._available

    def reset_availability(self):
        """利用可能性キャッシュをリセット（設定変更後に呼ぶ）"""
        self._available = None
        self._pilot = None

    @property
    def last_error(self) -> str:
        """最後のエラーメッセージ"""
        return self._last_error

    def _check_availability(self) -> bool:
        """Ollama 接続 + Vision モデルの存在確認"""
        try:
            config = self._load_config()
            endpoint = config.get("ollama_endpoint", "http://localhost:11434")
            vision_model = config.get("vision_model", "")

            if not vision_model:
                self._last_error = "vision_not_set"
                return False

            # Ollama 接続確認
            import httpx
            try:
                resp = httpx.get(f"{endpoint}/api/tags", timeout=5.0)
                if resp.status_code != 200:
                    self._last_error = "ollama_not_connected"
                    return False
            except Exception:
                self._last_error = "ollama_not_connected"
                return False

            # Vision モデル存在確認
            models = resp.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            # 完全一致 or タグなし一致
            found = False
            for name in model_names:
                if name == vision_model or name.split(":")[0] == vision_model.split(":")[0]:
                    found = True
                    break

            if not found:
                self._last_error = f"vision_not_found:{vision_model}"
                return False

            self._last_error = ""
            return True

        except Exception as e:
            logger.warning(f"[HelixPilotTool] Availability check failed: {e}")
            self._last_error = "ollama_not_connected"
            return False

    def _load_config(self) -> dict:
        """config/helix_pilot.json を読み込み"""
        if self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"[HelixPilotTool] Config load error: {e}")
        return {}

    def _ensure_pilot(self):
        """HelixPilot インスタンスを lazy 初期化"""
        if self._pilot is not None:
            return

        # DPI 競合防止: PyQt6 が既に DPI Awareness を設定しているため
        os.environ["HELIX_PILOT_SKIP_DPI"] = "1"

        # scripts/ を sys.path に追加
        scripts_dir = str(_APP_ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)

        try:
            from helix_pilot import HelixPilot
            self._pilot = HelixPilot(
                config_path=self._config_path,
                output_mode="compact",
            )
            logger.info("[HelixPilotTool] HelixPilot initialized")
        except Exception as e:
            logger.error(f"[HelixPilotTool] HelixPilot init failed: {e}")
            raise

    def execute(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        コマンドを実行

        Args:
            command: コマンド名 (auto/browse/click/type/find/describe/verify/
                     screenshot/scroll/hotkey/wait-stable/status)
            params: コマンドパラメータ辞書

        Returns:
            dict: 実行結果 {"ok": bool, "result": ..., "error": ...}
        """
        try:
            self._ensure_pilot()
        except Exception as e:
            return {"ok": False, "error": f"Pilot init failed: {e}"}

        try:
            window = params.get("window", "")
            result = None

            if command == "auto":
                result = self._pilot.cmd_auto(
                    instruction=params.get("instruction", ""),
                    window=window,
                    dry_run=params.get("dry_run", False),
                )
            elif command == "browse":
                result = self._pilot.cmd_browse(
                    instruction=params.get("instruction", ""),
                    window=window,
                    dry_run=params.get("dry_run", False),
                )
            elif command == "click":
                result = self._pilot.cmd_click(
                    x=int(params.get("x", 0)),
                    y=int(params.get("y", 0)),
                    window=window,
                )
            elif command == "type":
                result = self._pilot.cmd_type(
                    text=params.get("text", ""),
                    window=window,
                )
            elif command == "hotkey":
                result = self._pilot.cmd_hotkey(
                    keys=params.get("keys", ""),
                    window=window,
                )
            elif command == "scroll":
                result = self._pilot.cmd_scroll(
                    amount=int(params.get("amount", 0)),
                    window=window,
                )
            elif command == "find":
                result = self._pilot.cmd_find(
                    description=params.get("description", ""),
                    window=window,
                )
            elif command == "describe":
                result = self._pilot.cmd_describe(window=window)
            elif command == "verify":
                result = self._pilot.cmd_verify(
                    expected=params.get("expected", ""),
                    window=window,
                )
            elif command == "screenshot":
                result = self._pilot.cmd_screenshot(
                    window=window,
                    name=params.get("name", "pilot_shot"),
                )
            elif command == "wait-stable":
                result = self._pilot.cmd_wait_stable(
                    timeout=int(params.get("timeout", 30)),
                    window=window,
                )
            elif command == "status":
                result = self._pilot.cmd_status()
            else:
                return {"ok": False, "error": f"Unknown command: {command}"}

            # HelixPilot の cmd_* は dict を返す
            if isinstance(result, dict):
                return result
            return {"ok": True, "result": str(result)}

        except Exception as e:
            logger.error(f"[HelixPilotTool] Execute error: {command} — {e}", exc_info=True)
            return {"ok": False, "error": str(e)}

    def get_screen_context(self, window: str = "") -> str:
        """
        画面の describe 結果をテキストで返す（プロンプト注入用）

        Returns:
            str: 画面説明テキスト（失敗時は空文字）
        """
        try:
            self._ensure_pilot()
            result = self._pilot.cmd_describe(window=window)
            if isinstance(result, dict):
                if result.get("ok"):
                    return result.get("description", result.get("result", ""))
                else:
                    return f"[Screen context unavailable: {result.get('error', 'unknown')}]"
            return str(result)
        except Exception as e:
            logger.warning(f"[HelixPilotTool] Screen context error: {e}")
            return ""

    def shutdown(self):
        """アプリ終了時のクリーンアップ"""
        if self._pilot is not None:
            try:
                if hasattr(self._pilot, "shutdown"):
                    self._pilot.shutdown()
                logger.info("[HelixPilotTool] Shutdown completed")
            except Exception as e:
                logger.warning(f"[HelixPilotTool] Shutdown error: {e}")
            finally:
                self._pilot = None
