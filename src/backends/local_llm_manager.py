"""
LocalLLM Manager - CP1 (VRAM非常駐構造)

Local LLM を常時起動しつつ VRAM を使わない構造を実装
UML状態遷移図に基づく状態管理

States:
- Idle: LLMはロードされていない状態
- Loading: モデルロード中
- Active: モデル実行可能状態（VRAMに読み込み）
- Throttled: 熱制御で処理を抑制
- Unloading: 自動アンロード状態
- Error: 異常発生
"""

import json
import logging
import time
import threading
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, asdict, field
from pathlib import Path
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class LLMState(Enum):
    """LLM Manager の状態"""
    IDLE = "idle"
    LOADING = "loading"
    ACTIVE = "active"
    THROTTLED = "throttled"
    UNLOADING = "unloading"
    ERROR = "error"


@dataclass
class LLMManagerConfig:
    """LocalLLM Manager 設定"""
    idle_timeout_sec: int = 300  # 5分後にアンロード
    auto_unload: bool = True     # アイドルタイムアウト後に自動アンロード
    throttle_on_high_temp: bool = True  # 高温時にスロットル
    endpoint: str = ""
    model_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LLMManagerConfig':
        return cls(
            idle_timeout_sec=data.get("idle_timeout_sec", 300),
            auto_unload=data.get("auto_unload", True),
            throttle_on_high_temp=data.get("throttle_on_high_temp", True),
            endpoint=data.get("endpoint", ""),
            model_name=data.get("model_name", ""),
        )


class LocalLLMManager:
    """
    LocalLLM Manager

    VRAM非常駐構造:
    - Idle時はVRAMにモデルロードなし
    - Request時にLoading→Activeへ移行
    - idle_timeout後にUnloading→Idleへ移行

    状態遷移:
    [*] --> Idle
    Idle --> Loading : request_received
    Loading --> Active : load_success
    Loading --> Error : load_failure
    Active --> Throttled : temp_exceeds_warn
    Active --> Unloading : idle_timeout
    Active --> Error : exec_failure
    Throttled --> Active : temp_normalized
    Throttled --> Unloading : idle_timeout
    Throttled --> Error : exec_failure
    Error --> Unloading : reset
    Unloading --> Idle : unload_complete
    """

    def __init__(self, config: Optional[LLMManagerConfig] = None, data_dir: Optional[str] = None):
        """
        Args:
            config: マネージャー設定
            data_dir: データディレクトリ
        """
        if data_dir is None:
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        self.config_file = self.data_dir / "llm_manager_config.json"
        self.config = config or LLMManagerConfig()

        # 状態管理
        self._state = LLMState.IDLE
        self._last_used_time: Optional[float] = None
        self._active_model: Optional[str] = None
        self._last_error: Optional[str] = None

        # 状態遷移コールバック
        self._state_callbacks: list[Callable[[LLMState, LLMState], None]] = []

        # アイドルタイムアウト監視スレッド
        self._idle_monitor_thread: Optional[threading.Thread] = None
        self._stop_monitor = threading.Event()

        # ログ設定
        self._setup_logging()

        # 設定読み込み
        self._load_config()

        logger.info(f"[LocalLLMManager] Initialized in state: {self._state.value}")

    def _setup_logging(self):
        """ログ設定"""
        logs_dir = self.data_dir.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        log_file = logs_dir / "local_llm_manager.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(file_handler)
        logger.setLevel(logging.INFO)

    def _load_config(self):
        """設定を読み込み"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.config = LLMManagerConfig.from_dict(data)
                logger.info(f"[LocalLLMManager] Loaded config")
            except Exception as e:
                logger.error(f"[LocalLLMManager] Failed to load config: {e}")

    def save_config(self):
        """設定を保存"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config.to_dict(), f, indent=2)
            logger.info(f"[LocalLLMManager] Saved config")
        except Exception as e:
            logger.error(f"[LocalLLMManager] Failed to save config: {e}")

    # ========================================
    # 状態遷移メソッド
    # ========================================

    def _transition_to(self, new_state: LLMState, reason: str = ""):
        """状態遷移を実行"""
        old_state = self._state
        if old_state == new_state:
            return

        self._state = new_state

        # ログに記録
        self._log_transition(old_state, new_state, reason)

        # コールバックを呼び出し
        for callback in self._state_callbacks:
            try:
                callback(old_state, new_state)
            except Exception as e:
                logger.error(f"[LocalLLMManager] Callback error: {e}")

        logger.info(f"[LocalLLMManager] State transition: {old_state.value} -> {new_state.value} ({reason})")

    def _log_transition(self, old_state: LLMState, new_state: LLMState, reason: str):
        """状態遷移をJSONLログに記録"""
        logs_dir = self.data_dir.parent / "logs"
        log_file = logs_dir / "llm_state_transitions.jsonl"

        entry = {
            "timestamp": datetime.now().isoformat(),
            "old_state": old_state.value,
            "new_state": new_state.value,
            "reason": reason,
            "model": self._active_model,
        }

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"[LocalLLMManager] Failed to log transition: {e}")

    def add_state_callback(self, callback: Callable[[LLMState, LLMState], None]):
        """状態遷移コールバックを追加"""
        self._state_callbacks.append(callback)

    def remove_state_callback(self, callback: Callable[[LLMState, LLMState], None]):
        """状態遷移コールバックを削除"""
        if callback in self._state_callbacks:
            self._state_callbacks.remove(callback)

    # ========================================
    # モデル管理メソッド
    # ========================================

    def load_model(self, model_name: Optional[str] = None) -> tuple[bool, str]:
        """
        モデルをロード (Idle -> Loading -> Active)

        Args:
            model_name: ロードするモデル名（省略時はconfig.model_name）

        Returns:
            (success, message)
        """
        if self._state not in [LLMState.IDLE, LLMState.ERROR]:
            return False, f"現在の状態 ({self._state.value}) ではロードできません"

        model = model_name or self.config.model_name
        if not model:
            return False, "モデル名が指定されていません"

        self._transition_to(LLMState.LOADING, f"load_model({model})")

        try:
            # 実際のモデルロード処理
            # ここでは LocalConnector 経由でヘルスチェックを行う
            from .local_connector import get_local_connector

            connector = get_local_connector()
            if not connector.config.endpoint:
                raise ValueError("エンドポイントが設定されていません")

            ok, msg = connector.healthcheck()
            if not ok:
                raise ConnectionError(msg)

            # ロード成功
            self._active_model = model
            self._last_used_time = time.time()
            self._transition_to(LLMState.ACTIVE, "load_success")

            # アイドル監視開始
            self._start_idle_monitor()

            return True, f"モデル '{model}' をロードしました"

        except Exception as e:
            self._last_error = str(e)
            self._transition_to(LLMState.ERROR, f"load_failure: {e}")
            return False, f"モデルロードに失敗: {e}"

    def unload_model(self) -> tuple[bool, str]:
        """
        モデルをアンロード (Active/Throttled/Error -> Unloading -> Idle)

        Returns:
            (success, message)
        """
        if self._state == LLMState.IDLE:
            return True, "すでにアンロード済みです"

        if self._state == LLMState.LOADING:
            return False, "ロード中はアンロードできません"

        self._transition_to(LLMState.UNLOADING, "unload_model")

        try:
            # 監視スレッド停止
            self._stop_idle_monitor()

            # 実際のアンロード処理
            # ローカルLLMの場合、特別な処理は不要（接続を切るだけ）

            self._active_model = None
            self._last_used_time = None
            self._transition_to(LLMState.IDLE, "unload_complete")

            return True, "モデルをアンロードしました"

        except Exception as e:
            self._last_error = str(e)
            self._transition_to(LLMState.ERROR, f"unload_failure: {e}")
            return False, f"アンロードに失敗: {e}"

    def request_llm(self, prompt: str, options: Optional[Dict[str, Any]] = None) -> tuple[bool, str, Dict[str, Any]]:
        """
        LLMにリクエストを送信

        Args:
            prompt: 入力プロンプト
            options: 生成オプション

        Returns:
            (success, response_text, metadata)
        """
        # Idle状態なら自動でロード
        if self._state == LLMState.IDLE:
            ok, msg = self.load_model()
            if not ok:
                return False, msg, {"error_type": "LoadFailed"}

        # Throttled状態なら処理を遅延
        if self._state == LLMState.THROTTLED:
            logger.warning("[LocalLLMManager] Throttled - request delayed")
            time.sleep(2)  # 2秒待機

        # Active または Throttled 状態でのみリクエスト可能
        if self._state not in [LLMState.ACTIVE, LLMState.THROTTLED]:
            return False, f"現在の状態 ({self._state.value}) ではリクエストできません", {"error_type": "InvalidState"}

        try:
            from .local_connector import get_local_connector

            connector = get_local_connector()
            success, response, metadata = connector.generate(prompt, options)

            if success:
                # 使用時刻を更新
                self._last_used_time = time.time()
                return True, response, metadata
            else:
                self._last_error = response
                self._transition_to(LLMState.ERROR, f"exec_failure: {response}")
                return False, response, metadata

        except Exception as e:
            self._last_error = str(e)
            self._transition_to(LLMState.ERROR, f"exec_failure: {e}")
            return False, str(e), {"error_type": "ExecutionFailed"}

    # ========================================
    # Thermal Policy 連携
    # ========================================

    def apply_throttle(self, reason: str = "temp_exceeds_warn"):
        """
        スロットルを適用 (Active -> Throttled)

        Args:
            reason: スロットル理由
        """
        if self._state == LLMState.ACTIVE:
            self._transition_to(LLMState.THROTTLED, reason)
            logger.warning(f"[LocalLLMManager] Throttle applied: {reason}")

    def resume_normal(self, reason: str = "temp_normalized"):
        """
        通常状態に復帰 (Throttled -> Active)

        Args:
            reason: 復帰理由
        """
        if self._state == LLMState.THROTTLED:
            self._transition_to(LLMState.ACTIVE, reason)
            logger.info(f"[LocalLLMManager] Resumed normal: {reason}")

    def handle_thermal_event(self, event_type: str, temperature: float):
        """
        熱イベントを処理

        Args:
            event_type: "warning" | "stop" | "normal"
            temperature: 現在の温度
        """
        if not self.config.throttle_on_high_temp:
            return

        if event_type == "warning":
            self.apply_throttle(f"GPU temp {temperature}°C exceeds warning threshold")
        elif event_type == "stop":
            self.apply_throttle(f"GPU temp {temperature}°C exceeds stop threshold - urgent")
            # 高温が続く場合はアンロードを検討
        elif event_type == "normal":
            self.resume_normal(f"GPU temp {temperature}°C normalized")

    # ========================================
    # アイドルタイムアウト監視
    # ========================================

    def _start_idle_monitor(self):
        """アイドル監視スレッドを開始"""
        if not self.config.auto_unload:
            return

        self._stop_monitor.clear()
        self._idle_monitor_thread = threading.Thread(
            target=self._idle_monitor_loop,
            daemon=True
        )
        self._idle_monitor_thread.start()

    def _stop_idle_monitor(self):
        """アイドル監視スレッドを停止"""
        self._stop_monitor.set()
        if self._idle_monitor_thread:
            self._idle_monitor_thread.join(timeout=2)
            self._idle_monitor_thread = None

    def _idle_monitor_loop(self):
        """アイドル監視ループ"""
        while not self._stop_monitor.is_set():
            if self._state in [LLMState.ACTIVE, LLMState.THROTTLED]:
                if self._last_used_time:
                    elapsed = time.time() - self._last_used_time
                    if elapsed >= self.config.idle_timeout_sec:
                        logger.info(f"[LocalLLMManager] Idle timeout ({elapsed:.0f}s) - unloading")
                        self.unload_model()
                        break

            # 10秒ごとにチェック
            self._stop_monitor.wait(10)

    def handle_idle_timeout(self):
        """アイドルタイムアウトを手動で処理"""
        if self._state in [LLMState.ACTIVE, LLMState.THROTTLED]:
            self.unload_model()

    # ========================================
    # 状態取得
    # ========================================

    def get_state(self) -> LLMState:
        """現在の状態を取得"""
        return self._state

    def get_state_info(self) -> Dict[str, Any]:
        """状態の詳細情報を取得"""
        return {
            "state": self._state.value,
            "active_model": self._active_model,
            "last_used_time": self._last_used_time,
            "last_error": self._last_error,
            "idle_timeout_sec": self.config.idle_timeout_sec,
            "auto_unload": self.config.auto_unload,
        }

    def is_available(self) -> bool:
        """利用可能かどうか"""
        return self._state in [LLMState.ACTIVE, LLMState.THROTTLED]

    def reset(self):
        """エラー状態からリセット (Error -> Unloading -> Idle)"""
        if self._state == LLMState.ERROR:
            self.unload_model()


# ========================================
# グローバルインスタンス（スレッドセーフ）
# ========================================

_llm_manager: Optional[LocalLLMManager] = None
_llm_manager_lock = threading.Lock()


def get_llm_manager() -> LocalLLMManager:
    """
    LocalLLMManagerのグローバルインスタンスを取得（スレッドセーフ）

    ダブルチェックロッキングパターンを使用
    """
    global _llm_manager
    if _llm_manager is None:
        with _llm_manager_lock:
            # ロック取得後に再度チェック
            if _llm_manager is None:
                _llm_manager = LocalLLMManager()
    return _llm_manager
