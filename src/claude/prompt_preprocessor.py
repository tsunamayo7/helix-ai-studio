"""
Prompt Preprocessor - プロンプト前処理
送信時に工程テンプレートを自動付与
"""

from typing import Tuple
from ..data.workflow_templates import WorkflowTemplates
from ..data.workflow_state import WorkflowStateMachine
from ..utils.constants import WorkflowPhase


class PromptPreprocessor:
    """
    プロンプト前処理クラス

    送信前にユーザーの入力を処理し、工程に応じたテンプレートを付与
    """

    def __init__(self):
        self.template_enabled = True  # デフォルトでテンプレ付与ON

    def process(
        self,
        user_input: str,
        workflow_state: WorkflowStateMachine
    ) -> Tuple[str, bool, str]:
        """
        ユーザー入力を処理

        Args:
            user_input: ユーザーが入力したメッセージ
            workflow_state: 現在の工程状態

        Returns:
            (処理後のメッセージ, テンプレートが付与されたか, 付与したテンプレート名)
        """
        if not self.template_enabled:
            return user_input, False, ""

        current_phase = workflow_state.current_phase

        # 工程に対応するテンプレートを取得
        if WorkflowTemplates.has_template(current_phase):
            template = WorkflowTemplates.get_template(current_phase)
            phase_name = WorkflowPhase.get_display_name(current_phase)

            # テンプレートをユーザー入力の前に付与
            processed_message = template + user_input

            return processed_message, True, phase_name
        else:
            # テンプレートがない工程（S0, S4, S5）はそのまま
            return user_input, False, ""

    def set_template_enabled(self, enabled: bool):
        """
        テンプレート自動付与の有効/無効を設定

        Args:
            enabled: 有効にする場合True
        """
        self.template_enabled = enabled

    def is_template_enabled(self) -> bool:
        """
        テンプレート自動付与が有効かどうかを取得

        Returns:
            有効な場合True
        """
        return self.template_enabled

    @staticmethod
    def check_send_permission(workflow_state: WorkflowStateMachine) -> Tuple[bool, str]:
        """
        送信許可チェック（二重ガード用）

        Args:
            workflow_state: 現在の工程状態

        Returns:
            (許可されているか, エラーメッセージ)
        """
        current = workflow_state.current_phase

        # S0〜S3: 計画作成や読み込みのための送信は許可
        if current in [
            WorkflowPhase.S0_INTAKE,
            WorkflowPhase.S1_CONTEXT,
            WorkflowPhase.S2_PLAN,
            WorkflowPhase.S3_RISK_GATE
        ]:
            return True, ""

        # S4: 実装工程なので送信OK
        if current == WorkflowPhase.S4_IMPLEMENT:
            # ただし、S3の承認が必要
            if not workflow_state.get_flag("risk_approved"):
                return False, "S3（Risk Gate）の承認が完了していません。危険な操作を含む実装を行う場合、まずS3で承認を取得してください。"
            return True, ""

        # S5〜S7: 実装は完了しているので、送信OK
        if current in [
            WorkflowPhase.S5_VERIFY,
            WorkflowPhase.S6_REVIEW,
            WorkflowPhase.S7_RELEASE
        ]:
            return True, ""

        return True, ""

    @staticmethod
    def check_write_permission(workflow_state: WorkflowStateMachine) -> Tuple[bool, str]:
        """
        書き込み許可チェック（内部ガード用）

        Args:
            workflow_state: 現在の工程状態

        Returns:
            (許可されているか, エラーメッセージ)
        """
        # S3承認が必要
        if not workflow_state.get_flag("risk_approved"):
            return False, "書き込み操作はS3（Risk Gate）の承認が必要です。工程を進めて承認を取得してください。"

        # S4以降のみ書き込み許可
        phases = WorkflowPhase.all_phases()
        current_idx = phases.index(workflow_state.current_phase)
        s4_idx = phases.index(WorkflowPhase.S4_IMPLEMENT)

        if current_idx < s4_idx:
            return False, f"書き込み操作はS4（Implement）以降でのみ許可されています。現在の工程: {WorkflowPhase.get_display_name(workflow_state.current_phase)}"

        return True, ""


# グローバルインスタンス
_global_prompt_preprocessor = None


def get_prompt_preprocessor() -> PromptPreprocessor:
    """
    グローバルなPromptPreprocessorインスタンスを取得

    Returns:
        PromptPreprocessor インスタンス
    """
    global _global_prompt_preprocessor
    if _global_prompt_preprocessor is None:
        _global_prompt_preprocessor = PromptPreprocessor()
    return _global_prompt_preprocessor
