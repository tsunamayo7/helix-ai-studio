"""
Routing Executor - Phase 2.x 統合レイヤー

CP1〜CP10を統合した送信エントリーポイント
全ての送信はこのExecutorを経由する
"""

import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

from ..backends import BackendRequest, BackendResponse
from ..backends.registry import get_backend_registry
from .router import BackendRouter
from .classifier import TaskClassifier
from .task_types import TaskType
from .fallback import FallbackManager
from .decision_logger import RoutingDecision, get_routing_decision_logger
from .policy_checker import get_policy_checker, PolicyCheckResult
from .model_presets import get_preset_manager
from ..metrics.usage_metrics import get_usage_metrics_recorder
from ..metrics.budget_breaker import get_budget_breaker, BudgetStatus
from ..prompts.prompt_packs import get_prompt_pack_manager

logger = logging.getLogger(__name__)


class RoutingExecutor:
    """
    ルーティング実行器

    CP1-CP10を統合した送信処理の中央エントリーポイント
    """

    def __init__(self, project_id: Optional[str] = None):
        """
        Args:
            project_id: プロジェクトID（Preset適用に使用）
        """
        # 各コンポーネントのインスタンス
        self.backend_registry = get_backend_registry()
        self.router = BackendRouter()
        self.classifier = TaskClassifier()
        self.fallback_manager = FallbackManager()
        self.decision_logger = get_routing_decision_logger()
        self.policy_checker = get_policy_checker()
        self.preset_manager = get_preset_manager()
        self.metrics_recorder = get_usage_metrics_recorder()
        self.budget_breaker = get_budget_breaker()
        self.prompt_pack_manager = get_prompt_pack_manager()

        # プロジェクトID
        self.project_id = project_id

        # プリセットを適用
        self._apply_project_preset()

    def _apply_project_preset(self):
        """プロジェクトプリセットをRouterに適用"""
        if self.project_id:
            preset = self.preset_manager.get_project_preset(self.project_id)
            if preset:
                self.router.set_preset(preset.name, preset.mapping)
                logger.info(
                    f"[RoutingExecutor] Applied preset '{preset.name}' "
                    f"for project '{self.project_id}'"
                )

    def set_project(self, project_id: str):
        """プロジェクトを設定"""
        self.project_id = project_id
        self._apply_project_preset()

    def update_approval_state(self, approval_state: Dict[str, bool]):
        """承認状態を更新"""
        self.policy_checker.update_approval_state(approval_state)

    def execute(
        self,
        request: BackendRequest,
        user_forced_backend: Optional[str] = None,
        approval_snapshot: Optional[Dict[str, bool]] = None,
    ) -> Tuple[BackendResponse, Dict[str, Any]]:
        """
        送信を実行

        Args:
            request: BackendRequest
            user_forced_backend: ユーザーが明示的に指定したBackend
            approval_snapshot: 承認スナップショット

        Returns:
            (response, execution_info): レスポンスと実行情報
        """
        execution_info = {
            "task_type": None,
            "selected_backend": None,
            "reason_codes": [],
            "fallback_chain": [],
            "preset_name": None,
            "prompt_pack": None,
            "policy_blocked": False,
            "budget_status": None,
        }

        # === CP8: 予算チェック（送信前） ===
        budget_status, budget_message = self.budget_breaker.check_before_send()
        execution_info["budget_status"] = budget_status.value

        if budget_status == BudgetStatus.HARD_STOP:
            logger.warning(f"[RoutingExecutor] Budget hard stop: {budget_message}")

            return BackendResponse(
                success=False,
                response_text=f"予算超過により送信がブロックされました: {budget_message}",
                duration_ms=0.0,
                error_type="BudgetExceeded",
                metadata={"budget_message": budget_message}
            ), execution_info

        if budget_status == BudgetStatus.WARNING:
            logger.warning(f"[RoutingExecutor] Budget warning: {budget_message}")
            # 警告は記録するが、送信は続行

        # === CP2: タスク分類 ===
        task_type, confidence = self.classifier.classify_with_confidence(
            request.phase, request.user_text
        )
        execution_info["task_type"] = task_type.value

        logger.info(
            f"[RoutingExecutor] Task classified: type={task_type}, "
            f"confidence={confidence:.2f}"
        )

        # === CP3/CP7: Routerでバックエンド選択 ===
        selected_backend, reason_codes, user_forced = self.router.select_backend(
            task_type=task_type,
            phase=request.phase,
            user_forced_backend=user_forced_backend,
            approval_snapshot=approval_snapshot,
        )

        execution_info["selected_backend"] = selected_backend
        execution_info["reason_codes"] = reason_codes
        execution_info["preset_name"] = self.router.active_preset_name

        logger.info(
            f"[RoutingExecutor] Backend selected: {selected_backend}, "
            f"reasons={reason_codes}"
        )

        # === CP6: ルーティング決定の作成 ===
        decision = self.decision_logger.create_decision(
            session_id=request.session_id,
            phase=request.phase,
            task_type=task_type.value,
            selected_backend=selected_backend,
            user_forced_backend=user_forced,
            reason_codes=reason_codes,
        )
        decision.preset_name = self.router.active_preset_name
        decision.approval_snapshot = approval_snapshot
        decision.local_available = self.backend_registry.is_local_available()

        # === CP3: ポリシーチェック ===
        # 承認状態を更新
        if approval_snapshot:
            self.policy_checker.update_approval_state(approval_snapshot)

        policy_result = self.policy_checker.check_task_execution(
            task_type=task_type.value,
            backend=selected_backend,
            context=request.context,
        )

        if not policy_result.allowed:
            logger.warning(
                f"[RoutingExecutor] Policy blocked: {policy_result.reason}"
            )

            execution_info["policy_blocked"] = True

            decision.policy_blocked = True
            decision.policy_block_reason = policy_result.reason

            self.decision_logger.finalize_decision(
                decision,
                final_status="blocked",
                fallback_chain=[selected_backend],
                error_type="PolicyViolation",
                error_message=policy_result.reason,
            )

            return BackendResponse(
                success=False,
                response_text=f"ポリシー違反により送信がブロックされました: {policy_result.reason}",
                duration_ms=0.0,
                error_type="PolicyViolation",
                metadata={"missing_scopes": policy_result.missing_scopes}
            ), execution_info

        # === CP9: Prompt Pack注入 ===
        modified_text, pack_name = self.prompt_pack_manager.inject_pack(
            backend=selected_backend,
            original_prompt=request.user_text,
            task_type=task_type.value,
        )
        execution_info["prompt_pack"] = pack_name
        decision.prompt_pack = pack_name

        if pack_name:
            logger.info(f"[RoutingExecutor] Prompt pack injected: {pack_name}")
            # リクエストを更新
            request.user_text = modified_text

        # contextにメタデータを追加
        request.context = request.context or {}
        request.context.update({
            "task_type": task_type.value,
            "selected_backend": selected_backend,
            "reason_codes": reason_codes,
            "preset_name": self.router.active_preset_name,
            "prompt_pack": pack_name,
        })

        # === CP5: フォールバック付き実行 ===
        backends = self.backend_registry.get_all()
        fallback_chain = [selected_backend]
        current_backend_name = selected_backend

        while True:
            backend = backends.get(current_backend_name)

            if backend is None:
                # バックエンドが見つからない → フォールバック
                next_backend = self.fallback_manager.next_backend(
                    current_backend_name, task_type
                )

                if next_backend is None:
                    # フォールバック先がない
                    self.decision_logger.finalize_decision(
                        decision,
                        final_status="error",
                        fallback_chain=fallback_chain,
                        error_type="BackendNotFound",
                        error_message=f"Backend '{current_backend_name}' not found",
                    )

                    return BackendResponse(
                        success=False,
                        response_text=f"Backend '{current_backend_name}' が見つかりません",
                        duration_ms=0.0,
                        error_type="BackendNotFound",
                    ), execution_info

                fallback_chain.append(next_backend)
                current_backend_name = next_backend
                continue

            # バックエンド実行
            logger.info(f"[RoutingExecutor] Executing backend: {current_backend_name}")
            response = backend.send(request)

            if response.success:
                # === CP4: メトリクス記録 ===
                self.metrics_recorder.record_call(
                    session_id=request.session_id,
                    backend=current_backend_name,
                    task_type=task_type.value,
                    phase=request.phase,
                    duration_ms=response.duration_ms,
                    tokens_est=response.tokens_used,
                    cost_est=response.cost_est,
                    success=True,
                    metadata=response.metadata,
                )

                # === CP8: 予算記録 ===
                if response.cost_est:
                    self.budget_breaker.record_cost(
                        response.cost_est, request.session_id
                    )

                # === CP6: 決定ログ記録 ===
                execution_info["fallback_chain"] = fallback_chain

                self.decision_logger.finalize_decision(
                    decision,
                    final_status="success",
                    fallback_chain=fallback_chain,
                    duration_ms=response.duration_ms,
                    tokens_est=response.tokens_used,
                    cost_est=response.cost_est,
                )

                return response, execution_info

            # 失敗 → フォールバック試行
            logger.warning(
                f"[RoutingExecutor] Backend failed: {current_backend_name}, "
                f"error={response.error_type}"
            )

            # === CP4: 失敗メトリクス記録 ===
            self.metrics_recorder.record_call(
                session_id=request.session_id,
                backend=current_backend_name,
                task_type=task_type.value,
                phase=request.phase,
                duration_ms=response.duration_ms,
                tokens_est=response.tokens_used,
                cost_est=response.cost_est,
                success=False,
                error_type=response.error_type,
                metadata=response.metadata,
            )

            next_backend = self.fallback_manager.next_backend(
                current_backend_name, task_type
            )

            if next_backend is None:
                # フォールバック先がない
                execution_info["fallback_chain"] = fallback_chain

                self.decision_logger.finalize_decision(
                    decision,
                    final_status="error",
                    fallback_chain=fallback_chain,
                    error_type=response.error_type,
                    error_message=response.response_text,
                    duration_ms=response.duration_ms,
                )

                return response, execution_info

            fallback_chain.append(next_backend)
            current_backend_name = next_backend


# グローバルインスタンス
_routing_executor: Optional[RoutingExecutor] = None


def get_routing_executor(project_id: Optional[str] = None) -> RoutingExecutor:
    """RoutingExecutorのグローバルインスタンスを取得"""
    global _routing_executor
    if _routing_executor is None:
        _routing_executor = RoutingExecutor(project_id)
    elif project_id and _routing_executor.project_id != project_id:
        _routing_executor.set_project(project_id)
    return _routing_executor
