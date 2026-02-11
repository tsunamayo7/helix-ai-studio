"""
Budget Circuit Breaker - Phase 2.8

予算ベースのサーキットブレーカー
推定コストで警告/停止を行う
"""

import json
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class BudgetStatus(Enum):
    """予算ステータス"""
    OK = "ok"
    WARNING = "warning"
    HARD_STOP = "hard_stop"


@dataclass
class BudgetConfig:
    """予算設定"""
    session_est_budget: float = 5.0      # セッション予算 (USD)
    daily_est_budget: float = 20.0       # 日次予算 (USD)
    warn_threshold: float = 0.7          # 警告閾値 (70%)
    hard_stop: float = 1.0               # 停止閾値 (100%)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BudgetConfig':
        return cls(
            session_est_budget=data.get("session_est_budget", 5.0),
            daily_est_budget=data.get("daily_est_budget", 20.0),
            warn_threshold=data.get("warn_threshold", 0.7),
            hard_stop=data.get("hard_stop", 1.0),
        )


@dataclass
class BudgetEvent:
    """予算イベント"""
    timestamp: str
    event_type: str  # "warning" | "hard_stop" | "usage"
    session_id: str
    current_session_cost: float
    current_daily_cost: float
    session_budget: float
    daily_budget: float
    session_ratio: float
    daily_ratio: float
    message: Optional[str] = None


class BudgetCircuitBreaker:
    """
    予算サーキットブレーカー

    セッション/日次の予算を監視し、警告/停止を行う
    """

    def __init__(
        self,
        config: Optional[BudgetConfig] = None,
        data_dir: Optional[str] = None,
    ):
        """
        Args:
            config: 予算設定
            data_dir: データディレクトリ
        """
        if data_dir is None:
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        logs_dir = Path(__file__).parent.parent.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        self.config = config or BudgetConfig()
        self.config_file = self.data_dir / "budget_config.json"
        self.events_file = logs_dir / "budget_events.jsonl"

        # 現在のセッションコスト
        self.current_session_id: Optional[str] = None
        self.session_cost: float = 0.0

        # 日次コスト
        self.daily_cost: float = 0.0
        self.daily_date: Optional[date] = None

        # 設定を読み込み
        self._load_config()
        self._load_daily_cost()

    def _load_config(self):
        """設定を読み込み"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.config = BudgetConfig.from_dict(data)
                logger.info(f"[BudgetBreaker] Loaded config: {self.config}")
            except Exception as e:
                logger.error(f"[BudgetBreaker] Failed to load config: {e}")

    def save_config(self):
        """設定を保存"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config.to_dict(), f, indent=2)
            logger.info(f"[BudgetBreaker] Saved config")
        except Exception as e:
            logger.error(f"[BudgetBreaker] Failed to save config: {e}")

    def _load_daily_cost(self):
        """今日の日次コストを読み込み"""
        today = date.today()

        if not self.events_file.exists():
            self.daily_cost = 0.0
            self.daily_date = today
            return

        try:
            daily_total = 0.0

            with open(self.events_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        event_date = datetime.fromisoformat(event["timestamp"]).date()

                        if event_date == today and event.get("event_type") == "usage":
                            # コスト増分を加算
                            daily_total = event.get("current_daily_cost", daily_total)
                    except:
                        continue

            self.daily_cost = daily_total
            self.daily_date = today
            logger.info(f"[BudgetBreaker] Daily cost loaded: ${self.daily_cost:.4f}")

        except Exception as e:
            logger.error(f"[BudgetBreaker] Failed to load daily cost: {e}")
            self.daily_cost = 0.0
            self.daily_date = today

    def _check_daily_reset(self):
        """日付が変わったらリセット"""
        today = date.today()
        if self.daily_date != today:
            logger.info(f"[BudgetBreaker] Daily reset: {self.daily_date} -> {today}")
            self.daily_cost = 0.0
            self.daily_date = today

    def start_session(self, session_id: str):
        """新しいセッションを開始"""
        self.current_session_id = session_id
        self.session_cost = 0.0
        self._check_daily_reset()
        logger.info(f"[BudgetBreaker] Session started: {session_id}")

    def record_cost(self, cost_est: float, session_id: Optional[str] = None) -> BudgetStatus:
        """
        コストを記録し、ステータスを返す

        Args:
            cost_est: 推定コスト (USD)
            session_id: セッションID

        Returns:
            BudgetStatus
        """
        self._check_daily_reset()

        # セッションIDを更新
        if session_id and session_id != self.current_session_id:
            self.start_session(session_id)

        # コストを加算
        self.session_cost += cost_est
        self.daily_cost += cost_est

        # 比率を計算
        session_ratio = self.session_cost / self.config.session_est_budget if self.config.session_est_budget > 0 else 0
        daily_ratio = self.daily_cost / self.config.daily_est_budget if self.config.daily_est_budget > 0 else 0

        # ステータスを判定
        status = BudgetStatus.OK
        message = None

        if session_ratio >= self.config.hard_stop or daily_ratio >= self.config.hard_stop:
            status = BudgetStatus.HARD_STOP
            if session_ratio >= self.config.hard_stop:
                message = f"セッション予算超過: ${self.session_cost:.4f} / ${self.config.session_est_budget:.2f}"
            else:
                message = f"日次予算超過: ${self.daily_cost:.4f} / ${self.config.daily_est_budget:.2f}"
        elif session_ratio >= self.config.warn_threshold or daily_ratio >= self.config.warn_threshold:
            status = BudgetStatus.WARNING
            message = f"予算警告: セッション {session_ratio*100:.1f}%, 日次 {daily_ratio*100:.1f}%"

        # イベントを記録
        event = BudgetEvent(
            timestamp=datetime.now().isoformat(),
            event_type=status.value if status != BudgetStatus.OK else "usage",
            session_id=self.current_session_id or "unknown",
            current_session_cost=self.session_cost,
            current_daily_cost=self.daily_cost,
            session_budget=self.config.session_est_budget,
            daily_budget=self.config.daily_est_budget,
            session_ratio=session_ratio,
            daily_ratio=daily_ratio,
            message=message,
        )

        self._log_event(event)

        if status != BudgetStatus.OK:
            logger.warning(f"[BudgetBreaker] {status.value}: {message}")

        return status

    def check_before_send(self) -> tuple[BudgetStatus, Optional[str]]:
        """
        送信前のチェック

        Returns:
            (status, message): ステータスとメッセージ
        """
        self._check_daily_reset()

        session_ratio = self.session_cost / self.config.session_est_budget if self.config.session_est_budget > 0 else 0
        daily_ratio = self.daily_cost / self.config.daily_est_budget if self.config.daily_est_budget > 0 else 0

        if session_ratio >= self.config.hard_stop:
            message = f"セッション予算超過 (${self.session_cost:.4f} / ${self.config.session_est_budget:.2f})"
            return BudgetStatus.HARD_STOP, message

        if daily_ratio >= self.config.hard_stop:
            message = f"日次予算超過 (${self.daily_cost:.4f} / ${self.config.daily_est_budget:.2f})"
            return BudgetStatus.HARD_STOP, message

        if session_ratio >= self.config.warn_threshold or daily_ratio >= self.config.warn_threshold:
            message = f"予算警告: セッション {session_ratio*100:.1f}%, 日次 {daily_ratio*100:.1f}%"
            return BudgetStatus.WARNING, message

        return BudgetStatus.OK, None

    def _log_event(self, event: BudgetEvent):
        """イベントをログに記録"""
        try:
            with open(self.events_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"[BudgetBreaker] Failed to log event: {e}")

    def get_current_usage(self) -> Dict[str, Any]:
        """現在の使用状況を取得"""
        self._check_daily_reset()

        session_ratio = self.session_cost / self.config.session_est_budget if self.config.session_est_budget > 0 else 0
        daily_ratio = self.daily_cost / self.config.daily_est_budget if self.config.daily_est_budget > 0 else 0

        return {
            "session_cost": self.session_cost,
            "session_budget": self.config.session_est_budget,
            "session_ratio": session_ratio,
            "daily_cost": self.daily_cost,
            "daily_budget": self.config.daily_est_budget,
            "daily_ratio": daily_ratio,
            "warn_threshold": self.config.warn_threshold,
            "hard_stop": self.config.hard_stop,
        }

    def update_config(
        self,
        session_budget: Optional[float] = None,
        daily_budget: Optional[float] = None,
        warn_threshold: Optional[float] = None,
        hard_stop: Optional[float] = None,
    ):
        """設定を更新"""
        if session_budget is not None:
            self.config.session_est_budget = session_budget
        if daily_budget is not None:
            self.config.daily_est_budget = daily_budget
        if warn_threshold is not None:
            self.config.warn_threshold = warn_threshold
        if hard_stop is not None:
            self.config.hard_stop = hard_stop

        self.save_config()

    def reset_session(self):
        """セッションコストをリセット"""
        self.session_cost = 0.0
        logger.info(f"[BudgetBreaker] Session cost reset")

    def reset_daily(self):
        """日次コストをリセット（手動）"""
        self.daily_cost = 0.0
        self.daily_date = date.today()
        logger.info(f"[BudgetBreaker] Daily cost manually reset")


# グローバルインスタンス
_budget_breaker: Optional[BudgetCircuitBreaker] = None


def get_budget_breaker() -> BudgetCircuitBreaker:
    """BudgetCircuitBreakerのグローバルインスタンスを取得"""
    global _budget_breaker
    if _budget_breaker is None:
        _budget_breaker = BudgetCircuitBreaker()
    return _budget_breaker
