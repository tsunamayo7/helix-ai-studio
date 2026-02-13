"""
Thermal Monitor - CP2

GPU/CPU 温度・使用率・VRAM 監視を実装

Features:
- nvidia-smi (Windows) を使用したGPU温度・VRAM監視
- psutil を使用したCPU温度・使用率監視
- 定期的なサンプリングと状態通知
"""

import json
import logging
import subprocess
import threading
import time
from typing import Optional, Dict, Any, Callable, List

from ..utils.subprocess_utils import run_hidden
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ThermalStatus(Enum):
    """温度ステータス"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class ThermalReading:
    """温度読み取り値"""
    timestamp: str
    gpu_temp: Optional[float] = None
    gpu_usage: Optional[float] = None
    vram_used_mb: Optional[float] = None
    vram_total_mb: Optional[float] = None
    cpu_temp: Optional[float] = None
    cpu_usage: Optional[float] = None
    gpu_status: str = "unknown"
    cpu_status: str = "unknown"
    gpu_name: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ThermalThresholds:
    """温度閾値設定"""
    gpu_warn_threshold: float = 70.0   # GPU警告閾値℃
    gpu_stop_threshold: float = 85.0   # GPU停止閾値℃
    cpu_warn_threshold: float = 70.0   # CPU警告閾値℃
    cpu_stop_threshold: float = 90.0   # CPU停止閾値℃

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ThermalThresholds':
        return cls(
            gpu_warn_threshold=data.get("gpu_warn_threshold", 70.0),
            gpu_stop_threshold=data.get("gpu_stop_threshold", 85.0),
            cpu_warn_threshold=data.get("cpu_warn_threshold", 70.0),
            cpu_stop_threshold=data.get("cpu_stop_threshold", 90.0),
        )


class ThermalMonitor:
    """
    Thermal Monitor

    GPU/CPU の温度・使用率・VRAM を監視し、閾値超過時に通知を発行

    Windows環境:
    - GPU: nvidia-smi コマンドで取得
    - CPU: psutil で取得（温度は環境依存）
    """

    def __init__(
        self,
        thresholds: Optional[ThermalThresholds] = None,
        sampling_interval: float = 5.0,
        data_dir: Optional[str] = None
    ):
        """
        Args:
            thresholds: 温度閾値設定
            sampling_interval: サンプリング間隔（秒）
            data_dir: データディレクトリ
        """
        if data_dir is None:
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        self.config_file = self.data_dir / "thermal_config.json"
        self.thresholds = thresholds or ThermalThresholds()
        self.sampling_interval = sampling_interval

        # 状態管理
        self._latest_reading: Optional[ThermalReading] = None
        self._history: List[ThermalReading] = []
        self._max_history = 100  # 最大履歴数

        # 監視スレッド
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitor = threading.Event()
        self._is_monitoring = False

        # コールバック
        self._status_callbacks: List[Callable[[ThermalReading], None]] = []
        self._threshold_callbacks: List[Callable[[str, str, float, float], None]] = []

        # ログ設定
        self._setup_logging()

        # 設定読み込み
        self._load_config()

        # nvidia-smi の存在確認
        self._nvidia_smi_available = self._check_nvidia_smi()

        logger.info(f"[ThermalMonitor] Initialized (nvidia-smi available: {self._nvidia_smi_available})")

    def _setup_logging(self):
        """ログ設定"""
        logs_dir = self.data_dir.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        log_file = logs_dir / "thermal_monitor.log"
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
                    self.thresholds = ThermalThresholds.from_dict(data.get("thresholds", {}))
                    self.sampling_interval = data.get("sampling_interval", 5.0)
                logger.info(f"[ThermalMonitor] Loaded config")
            except Exception as e:
                logger.error(f"[ThermalMonitor] Failed to load config: {e}")

    def save_config(self):
        """設定を保存"""
        try:
            config = {
                "thresholds": self.thresholds.to_dict(),
                "sampling_interval": self.sampling_interval,
            }
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            logger.info(f"[ThermalMonitor] Saved config")
        except Exception as e:
            logger.error(f"[ThermalMonitor] Failed to save config: {e}")

    def _check_nvidia_smi(self) -> bool:
        """nvidia-smiが利用可能か確認"""
        try:
            result = run_hidden(
                ["nvidia-smi", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    # ========================================
    # 温度読み取りメソッド
    # ========================================

    def read_gpu_temp(self) -> tuple[Optional[float], Optional[str], Dict[str, Any]]:
        """
        GPU温度を読み取り

        Returns:
            (temperature, gpu_name, full_info)
        """
        if not self._nvidia_smi_available:
            return None, None, {"error": "nvidia-smi not available"}

        try:
            # nvidia-smi CSV形式で取得
            # timestamp, name, temperature.gpu, utilization.gpu, memory.used, memory.total
            result = run_hidden(
                [
                    "nvidia-smi",
                    "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits"
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return None, None, {"error": result.stderr}

            # 最初のGPUのみ処理
            line = result.stdout.strip().split("\n")[0]
            parts = [p.strip() for p in line.split(",")]

            if len(parts) >= 5:
                gpu_name = parts[0]
                temp = float(parts[1]) if parts[1] else None
                usage = float(parts[2]) if parts[2] else None
                vram_used = float(parts[3]) if parts[3] else None
                vram_total = float(parts[4]) if parts[4] else None

                return temp, gpu_name, {
                    "gpu_name": gpu_name,
                    "gpu_usage": usage,
                    "vram_used_mb": vram_used,
                    "vram_total_mb": vram_total,
                }

            return None, None, {"error": "Parse failed"}

        except subprocess.TimeoutExpired:
            return None, None, {"error": "nvidia-smi timeout"}
        except Exception as e:
            return None, None, {"error": str(e)}

    def read_cpu_temp(self) -> tuple[Optional[float], Optional[float]]:
        """
        CPU温度と使用率を読み取り

        Returns:
            (temperature, usage_percent)
        """
        cpu_temp = None
        cpu_usage = None

        try:
            import psutil

            # CPU使用率
            cpu_usage = psutil.cpu_percent(interval=0.1)

            # CPU温度（環境によっては取得できない）
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    # 最初に見つかった温度センサーを使用
                    for name, entries in temps.items():
                        if entries:
                            cpu_temp = entries[0].current
                            break
            except (AttributeError, NotImplementedError):
                # Windows では sensors_temperatures() がサポートされていない場合がある
                pass

        except ImportError:
            logger.warning("[ThermalMonitor] psutil not installed")
        except Exception as e:
            logger.error(f"[ThermalMonitor] CPU read error: {e}")

        return cpu_temp, cpu_usage

    def read_vram_usage(self) -> tuple[Optional[float], Optional[float]]:
        """
        VRAM使用量を読み取り

        Returns:
            (used_mb, total_mb)
        """
        _, _, info = self.read_gpu_temp()
        return info.get("vram_used_mb"), info.get("vram_total_mb")

    # ========================================
    # ステータス判定
    # ========================================

    def _get_thermal_status(self, temp: Optional[float], warn_threshold: float, stop_threshold: float) -> str:
        """温度ステータスを判定"""
        if temp is None:
            return ThermalStatus.UNKNOWN.value
        if temp >= stop_threshold:
            return ThermalStatus.CRITICAL.value
        if temp >= warn_threshold:
            return ThermalStatus.WARNING.value
        return ThermalStatus.NORMAL.value

    # ========================================
    # 読み取り実行
    # ========================================

    def read_all(self) -> ThermalReading:
        """
        全ての温度/使用率を読み取り

        Returns:
            ThermalReading
        """
        timestamp = datetime.now().isoformat()

        # GPU読み取り
        gpu_temp, gpu_name, gpu_info = self.read_gpu_temp()
        gpu_usage = gpu_info.get("gpu_usage")
        vram_used = gpu_info.get("vram_used_mb")
        vram_total = gpu_info.get("vram_total_mb")
        gpu_error = gpu_info.get("error")

        # CPU読み取り
        cpu_temp, cpu_usage = self.read_cpu_temp()

        # ステータス判定
        gpu_status = self._get_thermal_status(
            gpu_temp,
            self.thresholds.gpu_warn_threshold,
            self.thresholds.gpu_stop_threshold
        )
        cpu_status = self._get_thermal_status(
            cpu_temp,
            self.thresholds.cpu_warn_threshold,
            self.thresholds.cpu_stop_threshold
        )

        reading = ThermalReading(
            timestamp=timestamp,
            gpu_temp=gpu_temp,
            gpu_usage=gpu_usage,
            vram_used_mb=vram_used,
            vram_total_mb=vram_total,
            cpu_temp=cpu_temp,
            cpu_usage=cpu_usage,
            gpu_status=gpu_status,
            cpu_status=cpu_status,
            gpu_name=gpu_name,
            error=gpu_error,
        )

        self._latest_reading = reading

        return reading

    def post_status(self, reading: ThermalReading):
        """
        ステータスを通知

        Args:
            reading: 温度読み取り値
        """
        # 履歴に追加
        self._history.append(reading)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # ログに記録
        self._log_reading(reading)

        # コールバック呼び出し
        for callback in self._status_callbacks:
            try:
                callback(reading)
            except Exception as e:
                logger.error(f"[ThermalMonitor] Status callback error: {e}")

        # 閾値チェック
        self._check_thresholds(reading)

    def _log_reading(self, reading: ThermalReading):
        """読み取り値をJSONLログに記録"""
        logs_dir = self.data_dir.parent / "logs"
        log_file = logs_dir / "thermal_readings.jsonl"

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(reading.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"[ThermalMonitor] Failed to log reading: {e}")

    def _check_thresholds(self, reading: ThermalReading):
        """閾値超過をチェックしてコールバック発行"""
        # GPU閾値チェック
        if reading.gpu_temp is not None:
            if reading.gpu_status == ThermalStatus.CRITICAL.value:
                self._emit_threshold_event("gpu", "stop", reading.gpu_temp, self.thresholds.gpu_stop_threshold)
            elif reading.gpu_status == ThermalStatus.WARNING.value:
                self._emit_threshold_event("gpu", "warning", reading.gpu_temp, self.thresholds.gpu_warn_threshold)

        # CPU閾値チェック
        if reading.cpu_temp is not None:
            if reading.cpu_status == ThermalStatus.CRITICAL.value:
                self._emit_threshold_event("cpu", "stop", reading.cpu_temp, self.thresholds.cpu_stop_threshold)
            elif reading.cpu_status == ThermalStatus.WARNING.value:
                self._emit_threshold_event("cpu", "warning", reading.cpu_temp, self.thresholds.cpu_warn_threshold)

    def _emit_threshold_event(self, device: str, event_type: str, current_temp: float, threshold: float):
        """閾値イベントを発行"""
        logger.warning(f"[ThermalMonitor] {device.upper()} {event_type}: {current_temp}°C (threshold: {threshold}°C)")

        for callback in self._threshold_callbacks:
            try:
                callback(device, event_type, current_temp, threshold)
            except Exception as e:
                logger.error(f"[ThermalMonitor] Threshold callback error: {e}")

    # ========================================
    # コールバック管理
    # ========================================

    def add_status_callback(self, callback: Callable[[ThermalReading], None]):
        """ステータス更新コールバックを追加"""
        self._status_callbacks.append(callback)

    def add_threshold_callback(self, callback: Callable[[str, str, float, float], None]):
        """閾値超過コールバックを追加（device, event_type, current_temp, threshold）"""
        self._threshold_callbacks.append(callback)

    def remove_status_callback(self, callback: Callable[[ThermalReading], None]):
        """ステータス更新コールバックを削除"""
        if callback in self._status_callbacks:
            self._status_callbacks.remove(callback)

    def remove_threshold_callback(self, callback: Callable[[str, str, float, float], None]):
        """閾値超過コールバックを削除"""
        if callback in self._threshold_callbacks:
            self._threshold_callbacks.remove(callback)

    # ========================================
    # 監視スレッド
    # ========================================

    def start_monitoring(self):
        """監視を開始"""
        if self._is_monitoring:
            return

        self._stop_monitor.clear()
        self._is_monitoring = True

        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self._monitor_thread.start()

        logger.info(f"[ThermalMonitor] Monitoring started (interval: {self.sampling_interval}s)")

    def stop_monitoring(self):
        """監視を停止"""
        if not self._is_monitoring:
            return

        self._stop_monitor.set()
        self._is_monitoring = False

        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
            self._monitor_thread = None

        logger.info("[ThermalMonitor] Monitoring stopped")

    def _monitor_loop(self):
        """監視ループ"""
        while not self._stop_monitor.is_set():
            try:
                reading = self.read_all()
                self.post_status(reading)
            except Exception as e:
                logger.error(f"[ThermalMonitor] Monitor loop error: {e}")

            self._stop_monitor.wait(self.sampling_interval)

    # ========================================
    # 状態取得
    # ========================================

    def get_latest_reading(self) -> Optional[ThermalReading]:
        """最新の読み取り値を取得"""
        return self._latest_reading

    def get_history(self, limit: int = 50) -> List[ThermalReading]:
        """履歴を取得"""
        return self._history[-limit:]

    def is_monitoring(self) -> bool:
        """監視中かどうか"""
        return self._is_monitoring

    def update_thresholds(self, thresholds: ThermalThresholds):
        """閾値を更新"""
        self.thresholds = thresholds
        self.save_config()
        logger.info(f"[ThermalMonitor] Thresholds updated: {thresholds.to_dict()}")


# ========================================
# グローバルインスタンス
# ========================================

_thermal_monitor: Optional[ThermalMonitor] = None


def get_thermal_monitor() -> ThermalMonitor:
    """ThermalMonitorのグローバルインスタンスを取得"""
    global _thermal_monitor
    if _thermal_monitor is None:
        _thermal_monitor = ThermalMonitor()
    return _thermal_monitor
