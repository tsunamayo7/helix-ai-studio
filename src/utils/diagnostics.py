"""
Diagnostics - 診断情報の収集とエクスポート
Phase 1.2: 機密マスク、workflow_state, approvals, diff_risk_report同梱
"""
import os
import re
import json
import zipfile
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging


# 機密情報パターン（正規表現）
SENSITIVE_PATTERNS = [
    (r'(api[_-]?key|apikey)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', 'API_KEY'),
    (r'(token|access[_-]?token)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', 'TOKEN'),
    (r'(password|passwd|pwd)\s*[:=]\s*["\']?([^"\'\s]{8,})["\']?', 'PASSWORD'),
    (r'(secret|client[_-]?secret)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', 'SECRET'),
    (r'(cookie)\s*[:=]\s*["\']?([^"\'\s]{20,})["\']?', 'COOKIE'),
    (r'(authorization:\s*bearer\s+)([a-zA-Z0-9_\-\.]{20,})', 'BEARER_TOKEN'),
    (r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', 'EMAIL'),
]


class DiagnosticsExporter:
    """
    診断情報エクスポートクラス

    - アプリケーション状態を収集
    - 機密情報をマスク
    - ZIPファイルにパッケージング
    """

    def __init__(
        self,
        data_dir: str = "data",
        logs_dir: str = "logs",
        output_dir: str = "diagnostics"
    ):
        """
        初期化

        Args:
            data_dir: データディレクトリパス
            logs_dir: ログディレクトリパス
            output_dir: 出力ディレクトリパス
        """
        self.data_dir = Path(data_dir)
        self.logs_dir = Path(logs_dir)
        self.output_dir = Path(output_dir)
        self.logger = self._setup_logger()

        # 出力ディレクトリを作成
        self.output_dir.mkdir(exist_ok=True)

    def _setup_logger(self) -> logging.Logger:
        """ロガーをセットアップ"""
        logger = logging.getLogger("DiagnosticsExporter")
        logger.setLevel(logging.INFO)
        return logger

    def mask_sensitive_data(self, text: str) -> str:
        """
        機密情報をマスク

        Args:
            text: 元のテキスト

        Returns:
            マスク後のテキスト
        """
        masked_text = text

        for pattern, label in SENSITIVE_PATTERNS:
            def replace_func(match):
                if len(match.groups()) >= 2:
                    # キーと値の両方がある場合
                    prefix = match.group(1)
                    value = match.group(2)
                    masked_value = f"***{label}_MASKED***"
                    return f"{prefix}={masked_value}"
                else:
                    # 値のみの場合
                    return f"***{label}_MASKED***"

            masked_text = re.sub(pattern, replace_func, masked_text, flags=re.IGNORECASE)

        return masked_text

    def collect_files(self) -> List[tuple]:
        """
        診断に含めるファイルを収集

        Returns:
            (ファイルパス, ZIP内パス) のタプルリスト
        """
        files_to_include = []

        # データファイル
        data_files = [
            "session_state.json",
            "workflow_state.json",
            "diff_risk_report.json",
            "workflow_history.json",
            "project_profiles.json",      # Phase 1.3
            "mcp_policies.json",           # Phase 1.3
            "current_project.json",        # Phase 1.3
            # Phase 3.5: Thermal & Local LLM
            "llm_manager_config.json",
            "thermal_config.json",
            "thermal_policy_config.json",
            "local_connector_config.json",
        ]

        for file_name in data_files:
            file_path = self.data_dir / file_name
            if file_path.exists():
                files_to_include.append((file_path, f"data/{file_name}"))

        # ログファイル
        log_files = [
            "app.log",
            "claude.log",
            "gemini.log",
            "workflow.log",
            "session_manager.log",
            "risk_audit.log",
            "mcp_audit.log",
            "routing_decisions.jsonl",   # Phase 2.5
            "budget_events.jsonl",        # Phase 2.8
            "usage_metrics.jsonl",        # Phase 2.3
            # Phase 3.5: Thermal & Local LLM
            "local_llm_manager.log",
            "llm_state_transitions.jsonl",
            "thermal_monitor.log",
            "thermal_readings.jsonl",
            "thermal_policy.log",
            "thermal_policy_events.jsonl",
            "cloud_adapter.log",
        ]

        for file_name in log_files:
            file_path = self.logs_dir / file_name
            if file_path.exists():
                files_to_include.append((file_path, f"logs/{file_name}"))

        return files_to_include

    def create_system_info(self) -> Dict[str, Any]:
        """
        システム情報を収集

        Returns:
            システム情報の辞書
        """
        import platform
        import sys

        system_info = {
            "timestamp": datetime.now().isoformat(),
            "platform": platform.platform(),
            "python_version": sys.version,
            "architecture": platform.architecture(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        }

        return system_info

    def export_diagnostics(self, include_logs: bool = True) -> Optional[str]:
        """
        診断情報をZIPファイルにエクスポート

        Args:
            include_logs: ログファイルを含めるか

        Returns:
            生成されたZIPファイルのパス（失敗時None）
        """
        try:
            # タイムスタンプ付きファイル名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"helix_diagnostics_{timestamp}.zip"
            zip_path = self.output_dir / zip_filename

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # システム情報を追加
                system_info = self.create_system_info()
                system_info_json = json.dumps(system_info, indent=2, ensure_ascii=False)
                zipf.writestr("system_info.json", system_info_json)

                # ファイルを収集して追加
                files = self.collect_files()

                for file_path, arc_name in files:
                    # ログファイルをスキップする場合
                    if not include_logs and arc_name.startswith("logs/"):
                        continue

                    try:
                        # ファイルを読み込み、機密情報をマスク
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        # JSON/ログファイルはマスク処理
                        if file_path.suffix in ['.json', '.log']:
                            content = self.mask_sensitive_data(content)

                        # ZIPに追加
                        zipf.writestr(arc_name, content)
                        self.logger.info(f"Added to diagnostics: {arc_name}")

                    except Exception as e:
                        self.logger.warning(f"Failed to add {file_path}: {e}")
                        # エラーメッセージをZIPに追加
                        error_msg = f"Error reading file: {e}"
                        zipf.writestr(f"{arc_name}.error.txt", error_msg)

                # READMEを追加
                readme_content = self._create_readme()
                zipf.writestr("README.txt", readme_content)

            self.logger.info(f"Diagnostics exported to: {zip_path}")
            return str(zip_path)

        except Exception as e:
            self.logger.error(f"Failed to export diagnostics: {e}")
            return None

    def _create_readme(self) -> str:
        """診断ZIPのREADMEを生成"""
        readme = f"""
Helix AI Studio - Diagnostics Package
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

【内容】
- system_info.json: システム情報
- data/: アプリケーション状態ファイル
  - session_state.json: セッション状態（承認情報含む）
  - workflow_state.json: ワークフロー状態
  - diff_risk_report.json: 直近のDiff危険度レポート
  - workflow_history.json: ワークフロー履歴
- logs/: ログファイル
  - app.log: アプリケーションログ
  - claude.log: Claude APIログ
  - gemini.log: Gemini APIログ
  - workflow.log: ワークフローログ
  - risk_audit.log: Risk Gate監査ログ
  - mcp_audit.log: MCP監査ログ

【機密保護】
全てのファイルで以下の機密情報はマスクされています：
- APIキー
- トークン
- パスワード
- Cookieシークレット
- メールアドレス

【用途】
このパッケージはサポートやデバッグのために使用されます。
機密情報は既にマスクされていますが、念のため取り扱いには注意してください。

【問題報告】
バグや問題を報告する際は、このZIPファイルを添付してください。
問題の再現と解決に役立ちます。
        """
        return readme.strip()

    def get_latest_diagnostics(self) -> Optional[str]:
        """
        最新の診断ZIPファイルを取得

        Returns:
            最新のZIPファイルパス（存在しない場合None）
        """
        try:
            zip_files = list(self.output_dir.glob("helix_diagnostics_*.zip"))
            if not zip_files:
                return None

            # 最新のファイルを返す
            latest_file = max(zip_files, key=lambda f: f.stat().st_mtime)
            return str(latest_file)

        except Exception as e:
            self.logger.error(f"Failed to get latest diagnostics: {e}")
            return None

    def cleanup_old_diagnostics(self, keep_count: int = 5) -> int:
        """
        古い診断ZIPファイルを削除

        Args:
            keep_count: 保持する最新ファイル数

        Returns:
            削除したファイル数
        """
        try:
            zip_files = list(self.output_dir.glob("helix_diagnostics_*.zip"))
            if len(zip_files) <= keep_count:
                return 0

            # 古い順にソート
            zip_files.sort(key=lambda f: f.stat().st_mtime)

            # 古いファイルを削除
            files_to_delete = zip_files[:-keep_count]
            deleted_count = 0

            for file_path in files_to_delete:
                try:
                    file_path.unlink()
                    deleted_count += 1
                    self.logger.info(f"Deleted old diagnostics: {file_path.name}")
                except Exception as e:
                    self.logger.warning(f"Failed to delete {file_path}: {e}")

            return deleted_count

        except Exception as e:
            self.logger.error(f"Failed to cleanup old diagnostics: {e}")
            return 0


# グローバルインスタンス
_global_diagnostics_exporter: Optional[DiagnosticsExporter] = None


def get_diagnostics_exporter() -> DiagnosticsExporter:
    """
    グローバルなDiagnosticsExporterインスタンスを取得

    Returns:
        DiagnosticsExporter インスタンス
    """
    global _global_diagnostics_exporter
    if _global_diagnostics_exporter is None:
        _global_diagnostics_exporter = DiagnosticsExporter()
    return _global_diagnostics_exporter


def export_diagnostics(include_logs: bool = True) -> Optional[str]:
    """
    診断情報をエクスポートする便利関数

    Args:
        include_logs: ログファイルを含めるか

    Returns:
        生成されたZIPファイルのパス（失敗時None）
    """
    exporter = get_diagnostics_exporter()
    return exporter.export_diagnostics(include_logs)
