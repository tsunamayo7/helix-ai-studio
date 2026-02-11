"""
Prompt Packs - Phase 2.9

Backend別の安定化プロンプト
Opus前提の指示でもSonnetが破綻しにくくなるよう調整
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PromptPack:
    """
    プロンプトパック

    特定のBackend向けに最適化されたプロンプト設定
    """
    name: str
    display_name: str
    target_backend: str  # "claude-sonnet-4-5", "claude-opus-4-5", etc.
    system_instructions: str
    output_contract: str
    safety_guards: str
    enabled: bool = True

    def get_full_injection(self) -> str:
        """注入する全テキストを取得"""
        parts = []

        if self.system_instructions:
            parts.append("## システム指示\n" + self.system_instructions)

        if self.output_contract:
            parts.append("## 出力契約\n" + self.output_contract)

        if self.safety_guards:
            parts.append("## 安全ガード\n" + self.safety_guards)

        return "\n\n".join(parts)


# 組み込みプロンプトパック
BUILTIN_PACKS = {
    "sonnet_stabilizer": PromptPack(
        name="sonnet_stabilizer",
        display_name="Sonnet 安定化パック",
        target_backend="claude-sonnet-4-5",
        system_instructions="""あなたは熟練した開発者です。以下のルールを厳守してください：

1. **変更範囲の限定**: 要求された部分のみを変更し、関係ない箇所には触れない
2. **段階的な実装**: 大きな変更は小さなステップに分割して実行
3. **確認優先**: 不明確な点は推測せず、確認を求める
4. **既存パターンの尊重**: プロジェクトの既存コーディングスタイルに従う""",

        output_contract="""## 出力フォーマット
1. **変更ファイル一覧** (最初に明示)
2. **変更内容** (差分形式で簡潔に)
3. **テスト方法** (変更の検証方法)
4. **既知の制限** (あれば記載)

## 禁止事項
- 要求されていない「改善」や「リファクタリング」
- 複数の無関係な変更を一度に行う
- テストなしでの大規模変更""",

        safety_guards="""## 安全ガード
- ファイル削除は明示的な確認後のみ
- 設定ファイルの変更は差分を事前表示
- 外部APIキーやシークレットは決して出力しない
- 破壊的変更は必ず警告を表示"""
    ),

    "sonnet_minimal": PromptPack(
        name="sonnet_minimal",
        display_name="Sonnet 最小パック",
        target_backend="claude-sonnet-4-5",
        system_instructions="""簡潔に、要点のみを回答してください。
必要な変更のみを行い、余計な説明は省略します。""",

        output_contract="""変更内容は以下の形式で出力:
- ファイル: [パス]
- 変更: [差分の要約]""",

        safety_guards=""
    ),

    "haiku_fast": PromptPack(
        name="haiku_fast",
        display_name="Haiku 高速パック",
        target_backend="claude-haiku-4-5",
        system_instructions="""最短で回答。コードのみ出力。説明は省略可。""",

        output_contract="""コードブロックで出力。コメントは最小限。""",

        safety_guards=""
    ),

    "opus_full": PromptPack(
        name="opus_full",
        display_name="Opus フルパック",
        target_backend="claude-opus-4-5",
        system_instructions="""あなたは最高レベルのソフトウェアアーキテクトです。
深い分析と最適な設計を提供してください。
必要に応じて代替案も提示してください。""",

        output_contract="",  # Opusには過剰な制約は不要

        safety_guards="""セキュリティと保守性を常に考慮してください。"""
    ),

    "gemini_ui": PromptPack(
        name="gemini_ui",
        display_name="Gemini UI パック",
        target_backend="gemini-3-pro",
        system_instructions="""あなたはUI/UXデザインの専門家です。
ユーザビリティとアクセシビリティを重視してください。
PyQt6/QSS形式で出力してください。""",

        output_contract="""## 出力形式
1. QSS スタイルシート (変更箇所のみ)
2. レイアウト変更の説明 (簡潔に)
3. 実装例 (コードブロック)""",

        safety_guards=""
    ),
}


class PromptPackManager:
    """
    プロンプトパック管理

    Backend別に適切なパックを選択・注入
    """

    def __init__(self):
        self.packs: Dict[str, PromptPack] = {}
        self._load_builtin_packs()

    def _load_builtin_packs(self):
        """組み込みパックを読み込み"""
        for name, pack in BUILTIN_PACKS.items():
            self.packs[name] = pack

    def get_pack_for_backend(self, backend: str) -> Optional[PromptPack]:
        """
        Backend向けのパックを取得

        Args:
            backend: Backend名

        Returns:
            PromptPack or None
        """
        # 完全一致を探す
        for pack in self.packs.values():
            if pack.enabled and pack.target_backend == backend:
                return pack

        # 部分一致を探す (e.g., "sonnet" in "claude-sonnet-4-5")
        backend_lower = backend.lower()
        for pack in self.packs.values():
            if pack.enabled and pack.target_backend.lower() in backend_lower:
                return pack

        return None

    def get_pack_by_name(self, name: str) -> Optional[PromptPack]:
        """名前でパックを取得"""
        return self.packs.get(name)

    def get_all_packs(self) -> List[PromptPack]:
        """全パックを取得"""
        return list(self.packs.values())

    def inject_pack(
        self,
        backend: str,
        original_prompt: str,
        task_type: Optional[str] = None,
    ) -> tuple[str, Optional[str]]:
        """
        プロンプトにパックを注入

        Args:
            backend: Backend名
            original_prompt: 元のプロンプト
            task_type: タスク種別（オプション）

        Returns:
            (modified_prompt, pack_name): 変更後プロンプトとパック名
        """
        pack = self.get_pack_for_backend(backend)

        if not pack:
            return original_prompt, None

        # パックの内容を先頭に挿入
        injection = pack.get_full_injection()

        if injection:
            modified = f"{injection}\n\n---\n\n{original_prompt}"
            logger.info(f"[PromptPackManager] Injected pack: {pack.name} for {backend}")
            return modified, pack.name

        return original_prompt, pack.name

    def add_custom_pack(self, pack: PromptPack):
        """カスタムパックを追加"""
        self.packs[pack.name] = pack
        logger.info(f"[PromptPackManager] Added custom pack: {pack.name}")

    def enable_pack(self, name: str) -> bool:
        """パックを有効化"""
        if name in self.packs:
            self.packs[name].enabled = True
            return True
        return False

    def disable_pack(self, name: str) -> bool:
        """パックを無効化"""
        if name in self.packs:
            self.packs[name].enabled = False
            return True
        return False


# グローバルインスタンス
_prompt_pack_manager: Optional[PromptPackManager] = None


def get_prompt_pack_manager() -> PromptPackManager:
    """PromptPackManagerのグローバルインスタンスを取得"""
    global _prompt_pack_manager
    if _prompt_pack_manager is None:
        _prompt_pack_manager = PromptPackManager()
    return _prompt_pack_manager
