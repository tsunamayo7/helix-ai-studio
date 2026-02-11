"""
Execution with Fallback - Phase 2.4 / 2.5

フォールバック付きBackend実行
Phase 2.5: ルーティング決定ログ統合
"""

import logging
from typing import Dict, Any, Optional
from ..backends import LLMBackend, BackendRequest, BackendResponse
from .fallback import FallbackManager
from .task_types import TaskType
from .decision_logger import RoutingDecision, get_routing_decision_logger

logger = logging.getLogger(__name__)


def execute_with_fallback(
    backends: Dict[str, LLMBackend],
    request: BackendRequest,
    selected_backend_name: str,
    task_type: TaskType,
    fallback_manager: FallbackManager,
    risk_gate_violations: bool = False,
    routing_decision: Optional[RoutingDecision] = None,
    policy_block_reason: Optional[str] = None,
) -> tuple[BackendResponse, list]:
    """
    フォールバック付きでBackendを実行

    Args:
        backends: Backend名→Backendインスタンスの辞書
        request: リクエスト
        selected_backend_name: 選択されたBackend名
        task_type: タスク種別
        fallback_manager: フォールバック管理器
        risk_gate_violations: RiskGate違反がある場合True
        routing_decision: Phase 2.5 ルーティング決定オブジェクト
        policy_block_reason: Phase 2.6 ポリシーブロック理由

    Returns:
        (response, fallback_chain): 応答とフォールバックチェーン
    """
    fallback_chain = [selected_backend_name]
    current_backend_name = selected_backend_name
    decision_logger = get_routing_decision_logger()

    # RiskGate違反の場合はフォールバックしない
    if risk_gate_violations:
        logger.warning(
            f"[ExecuteWithFallback] RiskGate violation detected. "
            f"No fallback allowed."
        )

        # Phase 2.6: blockedとして記録
        if routing_decision:
            routing_decision.policy_blocked = True
            routing_decision.policy_block_reason = policy_block_reason
            decision_logger.finalize_decision(
                routing_decision,
                final_status="blocked",
                fallback_chain=fallback_chain,
                error_type="PolicyViolation",
                error_message=policy_block_reason,
            )

        backend = backends.get(current_backend_name)
        if backend is None:
            return BackendResponse(
                success=False,
                response_text=f"Backend not found and RiskGate violation: {policy_block_reason or 'Unknown'}",
                duration_ms=0.0,
                error_type="BackendNotFound",
            ), fallback_chain

        response = backend.send(request)
        return response, fallback_chain

    # フォールバックループ
    while True:
        backend = backends.get(current_backend_name)

        if backend is None:
            logger.error(
                f"[ExecuteWithFallback] Backend not found: {current_backend_name}"
            )
            # フォールバック先を試す
            next_backend = fallback_manager.next_backend(current_backend_name, task_type)
            if next_backend is None:
                # フォールバック先がない
                if routing_decision:
                    decision_logger.finalize_decision(
                        routing_decision,
                        final_status="error",
                        fallback_chain=fallback_chain,
                        error_type="BackendNotFound",
                        error_message=f"Backend '{current_backend_name}' not found",
                    )

                return BackendResponse(
                    success=False,
                    response_text=f"Backend '{current_backend_name}' not found and no fallback available.",
                    duration_ms=0.0,
                    error_type="BackendNotFound",
                ), fallback_chain

            fallback_chain.append(next_backend)
            current_backend_name = next_backend
            continue

        # Backend実行
        logger.info(f"[ExecuteWithFallback] Trying backend: {current_backend_name}")
        response = backend.send(request)

        if response.success:
            # 成功
            logger.info(
                f"[ExecuteWithFallback] Success: {current_backend_name}, "
                f"fallback_occurred={'yes' if len(fallback_chain) > 1 else 'no'}"
            )

            # Phase 2.5: 決定ログを記録
            if routing_decision:
                decision_logger.finalize_decision(
                    routing_decision,
                    final_status="success",
                    fallback_chain=fallback_chain,
                    duration_ms=response.duration_ms,
                    tokens_est=response.tokens_used,
                    cost_est=response.cost_est,
                )

            return response, fallback_chain

        # 失敗 → フォールバック先を試す
        logger.warning(
            f"[ExecuteWithFallback] Failed: {current_backend_name}, "
            f"error={response.error_type}"
        )

        next_backend = fallback_manager.next_backend(current_backend_name, task_type)
        if next_backend is None:
            # フォールバック先がない
            logger.error(f"[ExecuteWithFallback] No more fallback backends.")

            # Phase 2.5: エラーとして記録
            if routing_decision:
                decision_logger.finalize_decision(
                    routing_decision,
                    final_status="error",
                    fallback_chain=fallback_chain,
                    error_type=response.error_type,
                    error_message=response.response_text,
                    duration_ms=response.duration_ms,
                )

            return response, fallback_chain

        fallback_chain.append(next_backend)
        current_backend_name = next_backend
