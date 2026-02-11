"""
Thermal Policy Control - CP3

温度に応じた動作制御を組み込む状態機械

Thermal Policy State Machine:
[*] --> Normal
Normal --> WarningTemp : gpu_temp > gpu_warn_threshold
WarningTemp --> Normal : gpu_temp <= gpu_warn_threshold
WarningTemp --> StopTemp : gpu_temp > gpu_stop_threshold
StopTemp --> Throttle : gpu_temp in (gpu_warn_threshold..gpu_stop_threshold)
Throttle --> Normal : gpu_temp <= gpu_warn_threshold
Throttle --> StopTemp : gpu_temp > gpu_stop_threshold
StopTemp --> CoolingWait : throttle_applied
CoolingWait --> Normal : temp_normalized
CoolingWait --> StopTemp : temp_still_high
"""

import json
import logging
import threading
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ThermalPolicyState(Enum):
    """Thermal Policy 状態"""
    NORMAL = "normal"
    WARNING_TEMP = "warning_temp"
    STOP_TEMP = "stop_temp"
    THROTTLE = "throttle"
    COOLING_WAIT = "cooling_wait"


@dataclass
class ThermalPolicyConfig:
    """Thermal Policy 設定"""
    gpu_warn_threshold: float = 70.0   # GPU警告閾値℃
    gpu_stop_threshold: float = 85.0   # GPU停止閾値℃
    cpu_warn_threshold: float = 70.0   # CPU警告閾値℃
    cpu_stop_threshold: float = 90.0   # CPU停止閾値℃
    cooling_wait_seconds: int = 60     # 冷却待機時間（秒）
    auto_unload_on_stop: bool = True   # 停止閾値超過時に自動アンロード
    show_fan_recommendations: bool = True  # ファン制御推奨を表示

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ThermalPolicyConfig':
        return cls(
            gpu_warn_threshold=data.get("gpu_warn_threshold", 70.0),
            gpu_stop_threshold=data.get("gpu_stop_threshold", 85.0),
            cpu_warn_threshold=data.get("cpu_warn_threshold", 70.0),
            cpu_stop_threshold=data.get("cpu_stop_threshold", 90.0),
            cooling_wait_seconds=data.get("cooling_wait_seconds", 60),
            auto_unload_on_stop=data.get("auto_unload_on_stop", True),
            show_fan_recommendations=data.get("show_fan_recommendations", True),
        )


class ThermalPolicyController:
    """
    Thermal Policy Controller

    Temperature に応じた動作制御を実装

    制御フロー:
    if gpu_temp > gpu_stop_threshold:
        apply_throttle()
        if prolonged:
            unload_model()
    elif gpu_temp > gpu_warn_threshold:
        show_warning()
    elif gpu_temp <= gpu_warn_threshold:
        resume_normal()
    """

    def __init__(
        self,
        config: Optional[ThermalPolicyConfig] = None,
        data_dir: Optional[str] = None
    ):
        """
        Args:
            config: ポリシー設定
            data_dir: データディレクトリ
        """
        if data_dir is None:
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        self.config_file = self.data_dir / "thermal_policy_config.json"
        self.config = config or ThermalPolicyConfig()

        # 状態管理
        self._state = ThermalPolicyState.NORMAL
        self._last_gpu_temp: Optional[float] = None
        self._last_cpu_temp: Optional[float] = None
        self._cooling_start_time: Optional[float] = None

        # コールバック
        self._state_callbacks: List[Callable[[ThermalPolicyState, ThermalPolicyState, str], None]] = []
        self._action_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []

        # LLM Manager との連携
        self._llm_manager = None

        # ログ設定
        self._setup_logging()

        # 設定読み込み
        self._load_config()

        logger.info(f"[ThermalPolicy] Initialized in state: {self._state.value}")

    def _setup_logging(self):
        """ログ設定"""
        logs_dir = self.data_dir.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        log_file = logs_dir / "thermal_policy.log"
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
                    self.config = ThermalPolicyConfig.from_dict(data)
                logger.info(f"[ThermalPolicy] Loaded config")
            except Exception as e:
                logger.error(f"[ThermalPolicy] Failed to load config: {e}")

    def save_config(self):
        """設定を保存"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config.to_dict(), f, indent=2)
            logger.info(f"[ThermalPolicy] Saved config")
        except Exception as e:
            logger.error(f"[ThermalPolicy] Failed to save config: {e}")

    def set_llm_manager(self, llm_manager):
        """LLM Manager を設定"""
        self._llm_manager = llm_manager

    # ========================================
    # 状態遷移メソッド
    # ========================================

    def _transition_to(self, new_state: ThermalPolicyState, reason: str = ""):
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
                callback(old_state, new_state, reason)
            except Exception as e:
                logger.error(f"[ThermalPolicy] State callback error: {e}")

        logger.info(f"[ThermalPolicy] State transition: {old_state.value} -> {new_state.value} ({reason})")

    def _log_transition(self, old_state: ThermalPolicyState, new_state: ThermalPolicyState, reason: str):
        """状態遷移をJSONLログに記録"""
        logs_dir = self.data_dir.parent / "logs"
        log_file = logs_dir / "thermal_policy_events.jsonl"

        entry = {
            "timestamp": datetime.now().isoformat(),
            "old_state": old_state.value,
            "new_state": new_state.value,
            "reason": reason,
            "gpu_temp": self._last_gpu_temp,
            "cpu_temp": self._last_cpu_temp,
        }

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"[ThermalPolicy] Failed to log transition: {e}")

    # ========================================
    # コールバック管理
    # ========================================

    def add_state_callback(self, callback: Callable[[ThermalPolicyState, ThermalPolicyState, str], None]):
        """状態遷移コールバックを追加"""
        self._state_callbacks.append(callback)

    def add_action_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """アクションコールバックを追加（action_type, details）"""
        self._action_callbacks.append(callback)

    def _emit_action(self, action_type: str, details: Dict[str, Any]):
        """アクションを発行"""
        for callback in self._action_callbacks:
            try:
                callback(action_type, details)
            except Exception as e:
                logger.error(f"[ThermalPolicy] Action callback error: {e}")

    # ========================================
    # 温度処理
    # ========================================

    def process_temperature(self, gpu_temp: Optional[float], cpu_temp: Optional[float] = None):
        """
        温度読み取り値を処理し、ポリシーに基づいて制御

        Args:
            gpu_temp: GPU温度（℃）
            cpu_temp: CPU温度（℃）
        """
        self._last_gpu_temp = gpu_temp
        self._last_cpu_temp = cpu_temp

        # GPU温度がない場合はスキップ
        if gpu_temp is None:
            return

        # 現在の状態に基づいて処理
        if self._state == ThermalPolicyState.NORMAL:
            self._process_normal_state(gpu_temp)

        elif self._state == ThermalPolicyState.WARNING_TEMP:
            self._process_warning_state(gpu_temp)

        elif self._state == ThermalPolicyState.STOP_TEMP:
            self._process_stop_state(gpu_temp)

        elif self._state == ThermalPolicyState.THROTTLE:
            self._process_throttle_state(gpu_temp)

        elif self._state == ThermalPolicyState.COOLING_WAIT:
            self._process_cooling_wait_state(gpu_temp)

    def _process_normal_state(self, gpu_temp: float):
        """Normal状態の処理"""
        if gpu_temp > self.config.gpu_stop_threshold:
            self._transition_to(ThermalPolicyState.STOP_TEMP, f"GPU {gpu_temp}°C > stop threshold {self.config.gpu_stop_threshold}°C")
            self._apply_throttle()
        elif gpu_temp > self.config.gpu_warn_threshold:
            self._transition_to(ThermalPolicyState.WARNING_TEMP, f"GPU {gpu_temp}°C > warn threshold {self.config.gpu_warn_threshold}°C")
            self._show_warning()

    def _process_warning_state(self, gpu_temp: float):
        """Warning状態の処理"""
        if gpu_temp > self.config.gpu_stop_threshold:
            self._transition_to(ThermalPolicyState.STOP_TEMP, f"GPU {gpu_temp}°C > stop threshold {self.config.gpu_stop_threshold}°C")
            self._apply_throttle()
        elif gpu_temp <= self.config.gpu_warn_threshold:
            self._transition_to(ThermalPolicyState.NORMAL, f"GPU {gpu_temp}°C normalized")
            self._resume_normal()

    def _process_stop_state(self, gpu_temp: float):
        """Stop状態の処理"""
        # スロットルを適用してCoolingWaitへ
        import time
        self._cooling_start_time = time.time()
        self._transition_to(ThermalPolicyState.COOLING_WAIT, "throttle applied, waiting for cooling")

        # 自動アンロードが有効なら実行
        if self.config.auto_unload_on_stop:
            self._unload_model()

    def _process_throttle_state(self, gpu_temp: float):
        """Throttle状態の処理"""
        if gpu_temp > self.config.gpu_stop_threshold:
            self._transition_to(ThermalPolicyState.STOP_TEMP, f"GPU {gpu_temp}°C still exceeds stop threshold")
        elif gpu_temp <= self.config.gpu_warn_threshold:
            self._transition_to(ThermalPolicyState.NORMAL, f"GPU {gpu_temp}°C normalized")
            self._resume_normal()

    def _process_cooling_wait_state(self, gpu_temp: float):
        """CoolingWait状態の処理"""
        import time

        if gpu_temp > self.config.gpu_stop_threshold:
            self._transition_to(ThermalPolicyState.STOP_TEMP, "temp still high during cooling wait")
        elif gpu_temp <= self.config.gpu_warn_threshold:
            self._transition_to(ThermalPolicyState.NORMAL, f"GPU {gpu_temp}°C normalized after cooling")
            self._resume_normal()
        elif self._cooling_start_time:
            elapsed = time.time() - self._cooling_start_time
            if elapsed >= self.config.cooling_wait_seconds:
                # 冷却待機時間経過
                if gpu_temp <= self.config.gpu_warn_threshold:
                    self._transition_to(ThermalPolicyState.NORMAL, "cooling wait complete, temp normalized")
                    self._resume_normal()
                else:
                    self._transition_to(ThermalPolicyState.THROTTLE, "cooling wait complete, still throttling")

    # ========================================
    # 制御アクション
    # ========================================

    def _show_warning(self):
        """警告を表示"""
        details = {
            "gpu_temp": self._last_gpu_temp,
            "threshold": self.config.gpu_warn_threshold,
            "message": f"GPU温度が警告レベルに達しています ({self._last_gpu_temp}°C > {self.config.gpu_warn_threshold}°C)",
        }

        self._emit_action("show_warning", details)
        logger.warning(f"[ThermalPolicy] {details['message']}")

        # ファン制御推奨
        if self.config.show_fan_recommendations:
            self._show_fan_recommendation()

    def _apply_throttle(self):
        """スロットルを適用"""
        details = {
            "gpu_temp": self._last_gpu_temp,
            "threshold": self.config.gpu_stop_threshold,
            "message": f"GPU温度が危険レベルです。処理を抑制します ({self._last_gpu_temp}°C > {self.config.gpu_stop_threshold}°C)",
        }

        self._emit_action("apply_throttle", details)
        logger.error(f"[ThermalPolicy] {details['message']}")

        # LLM Manager にスロットルを通知
        if self._llm_manager:
            self._llm_manager.apply_throttle(f"GPU temp {self._last_gpu_temp}°C exceeds threshold")

        # ファン制御推奨
        if self.config.show_fan_recommendations:
            self._show_fan_recommendation()

    def _resume_normal(self):
        """通常状態に復帰"""
        details = {
            "gpu_temp": self._last_gpu_temp,
            "message": f"温度が正常範囲に戻りました ({self._last_gpu_temp}°C)",
        }

        self._emit_action("resume_normal", details)
        logger.info(f"[ThermalPolicy] {details['message']}")

        # LLM Manager に復帰を通知
        if self._llm_manager:
            self._llm_manager.resume_normal(f"GPU temp {self._last_gpu_temp}°C normalized")

    def _unload_model(self):
        """モデルをアンロード"""
        details = {
            "gpu_temp": self._last_gpu_temp,
            "message": "高温状態が続くため、モデルをアンロードします",
        }

        self._emit_action("unload_model", details)
        logger.warning(f"[ThermalPolicy] {details['message']}")

        # LLM Manager にアンロードを指示
        if self._llm_manager:
            self._llm_manager.unload_model()

    def _show_fan_recommendation(self):
        """ファン制御推奨を表示"""
        recommendations = self.get_fan_recommendations()

        details = {
            "gpu_temp": self._last_gpu_temp,
            "recommendations": recommendations,
        }

        self._emit_action("fan_recommendation", details)

    # ========================================
    # ファン制御推奨（CP4）
    # ========================================

    def get_fan_recommendations(self) -> Dict[str, Any]:
        """
        現在の温度に応じたファン制御推奨を取得

        Returns:
            推奨コマンドと説明
        """
        gpu_temp = self._last_gpu_temp or 0

        # 温度レベルに応じた推奨
        if gpu_temp >= self.config.gpu_stop_threshold:
            fan_speed = 100
            urgency = "緊急"
        elif gpu_temp >= self.config.gpu_warn_threshold:
            fan_speed = 90
            urgency = "推奨"
        elif gpu_temp >= self.config.gpu_warn_threshold - 10:
            fan_speed = 70
            urgency = "任意"
        else:
            return {
                "urgency": "不要",
                "message": "現在の温度では特別な対策は不要です",
                "commands": {},
            }

        return {
            "urgency": urgency,
            "current_temp": gpu_temp,
            "recommended_fan_speed": fan_speed,
            "message": f"GPU温度 {gpu_temp}°C - ファン速度 {fan_speed}% を推奨",
            "commands": {
                "windows_nvidia": [
                    "# NVIDIAコントロールパネルで設定するか、以下のコマンドを管理者権限で実行:",
                    f"nvidia-smi -pm 1",
                    f"nvidia-smi -pl 120",  # 電力制限
                    f"# ファン速度はMSI Afterburner等のツールで設定してください",
                ],
                "linux": [
                    f"# ファン速度を {fan_speed}% に設定:",
                    f"nvidia-settings -a '[gpu:0]/GPUFanControlState=1'",
                    f"nvidia-settings -a '[fan:0]/GPUTargetFanSpeed={fan_speed}'",
                    "# または:",
                    "sudo pwmconfig",
                    "sudo fancontrol",
                ],
            },
        }

    # ========================================
    # 状態取得
    # ========================================

    def get_state(self) -> ThermalPolicyState:
        """現在の状態を取得"""
        return self._state

    def get_state_info(self) -> Dict[str, Any]:
        """状態の詳細情報を取得"""
        return {
            "state": self._state.value,
            "gpu_temp": self._last_gpu_temp,
            "cpu_temp": self._last_cpu_temp,
            "thresholds": self.config.to_dict(),
        }

    def is_throttled(self) -> bool:
        """スロットル中かどうか"""
        return self._state in [ThermalPolicyState.THROTTLE, ThermalPolicyState.STOP_TEMP, ThermalPolicyState.COOLING_WAIT]

    def update_config(self, config: ThermalPolicyConfig):
        """設定を更新"""
        self.config = config
        self.save_config()
        logger.info(f"[ThermalPolicy] Config updated")


# ========================================
# グローバルインスタンス
# ========================================

_thermal_policy: Optional[ThermalPolicyController] = None


def get_thermal_policy() -> ThermalPolicyController:
    """ThermalPolicyControllerのグローバルインスタンスを取得"""
    global _thermal_policy
    if _thermal_policy is None:
        _thermal_policy = ThermalPolicyController()
    return _thermal_policy
