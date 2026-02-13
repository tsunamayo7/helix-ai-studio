"""
Claude CLI Backend Implementation - v3.4.0

Claude Max/Pro プランの認証を使用するCLI経由のバックエンド
ClaudeCodeと同様に `claude -p` コマンドを使用

v3.4.0: --continue フラグ対応（会話継続機能）

使用方法:
1. Claude CLI がインストールされていること: npm install -g @anthropic-ai/claude-code
2. Claude.com でログイン済みであること（Max/Proプラン）
3. Extra Usage（追加使用量）は https://support.claude.com/en/articles/12429409 で有効化

参考: https://support.claude.com/en/articles/12429409-extra-usage-for-paid-claude-plans
"""

import os
import sys
import subprocess
import threading
import queue
import time
import shutil
from typing import Optional, List, Callable
import logging

from .base import LLMBackend, BackendRequest, BackendResponse
from ..utils.subprocess_utils import run_hidden, popen_hidden

logger = logging.getLogger(__name__)


def find_claude_command() -> str:
    """
    claudeコマンドのフルパスを検出

    Returns:
        str: claudeコマンドのフルパス、見つからない場合は'claude'
    """
    # まずPATHから検索
    claude_path = shutil.which('claude')
    if claude_path:
        return claude_path

    # Windowsの一般的なnpmグローバルインストールパスを確認
    if sys.platform == 'win32':
        possible_paths = [
            os.path.join(os.environ.get('APPDATA', ''), 'npm', 'claude.cmd'),
            os.path.join(os.environ.get('APPDATA', ''), 'npm', 'claude'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'npm', 'claude.cmd'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'npm', 'claude'),
            os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Roaming', 'npm', 'claude.cmd'),
            os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Roaming', 'npm', 'claude'),
        ]
        for path in possible_paths:
            if path and os.path.exists(path):
                return path

    # 見つからない場合はデフォルト
    return 'claude'


def check_claude_cli_available() -> tuple[bool, str]:
    """
    Claude CLIが利用可能かチェック

    Returns:
        tuple[bool, str]: (利用可能か, メッセージ)
    """
    claude_cmd = find_claude_command()

    try:
        result = run_hidden(
            [claude_cmd, '--version'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            return True, f"Claude CLI found: {version}"
        else:
            return False, f"Claude CLI returned error: {result.stderr}"
    except FileNotFoundError:
        return False, (
            "Claude CLI が見つかりません。\n\n"
            "【インストール方法】\n"
            "1. Node.js をインストール\n"
            "2. npm install -g @anthropic-ai/claude-code\n"
            "3. claude login でログイン\n\n"
            "参考: https://docs.anthropic.com/claude-code"
        )
    except subprocess.TimeoutExpired:
        return False, "Claude CLI のバージョン確認がタイムアウトしました"
    except Exception as e:
        return False, f"Claude CLI チェック中にエラー: {e}"


class ClaudeCLIBackend(LLMBackend):
    """
    Claude CLI Backend 実装

    Claude Max/Pro プランの認証を使用してCLI経由でAI応答を生成
    Extra Usage（追加使用量）機能に対応

    v3.5.0: --dangerously-skip-permissions フラグ対応（権限確認スキップ）
    """

    # 思考レベルに応じたタイムアウト設定（秒）
    TIMEOUT_SETTINGS = {
        'none': 20 * 60,          # 20分 - 通常モード
        'light': 30 * 60,         # 30分 - じっくり (think)
        'medium': 50 * 60,        # 50分 - 深く (think hard)
        'medium_opus': 60 * 60,   # 60分 - 分析 (Opus計画)
        'deep': 100 * 60,         # 100分 - 最大 (ultrathink + Opus)
    }
    DEFAULT_TIMEOUT = 60 * 60  # 60分（デフォルト）

    # v7.1.0: モデルIDマッピング（UIテキスト → CLI用モデルID）
    MODEL_MAP = {
        # v7.1.0: Opus 4.6 追加
        "Claude Opus 4.6 (最高知能)": "claude-opus-4-6",
        "Claude Opus 4.5 (高品質)": "claude-opus-4-5-20250929",
        "Claude Sonnet 4.5 (高速)": "claude-sonnet-4-5-20250929",
        # 旧表示名の後方互換
        "Claude Opus 4.5 (最高性能)": "claude-opus-4-5-20250929",
        "Claude Sonnet 4.5 (推奨)": "claude-sonnet-4-5-20250929",
        "Claude Haiku 4.5 (高速)": "claude-sonnet-4-5-20250929",
        # 短縮形もサポート
        "opus-4-6": "claude-opus-4-6",
        "opus-4-5": "claude-opus-4-5-20250929",
        "sonnet-4-5": "claude-sonnet-4-5-20250929",
        # model_id直接渡しの場合はそのまま返す
        "claude-opus-4-6": "claude-opus-4-6",
        "claude-opus-4-5-20250929": "claude-opus-4-5-20250929",
        "claude-sonnet-4-5-20250929": "claude-sonnet-4-5-20250929",
    }

    def __init__(self, working_dir: str = None, thinking_level: str = "none", skip_permissions: bool = True, model: str = None):
        """
        Args:
            working_dir: 作業ディレクトリ
            thinking_level: 思考レベル (none, light, medium, medium_opus, deep)
            skip_permissions: 権限確認をスキップするか (v3.5.0)
            model: 使用するモデル名 (v3.9.4: モデル選択対応)
        """
        super().__init__("claude-cli")
        self._working_dir = working_dir or os.getcwd()
        self._thinking_level = thinking_level
        self._skip_permissions = skip_permissions  # v3.5.0: 権限スキップフラグ
        self._model = model  # v3.9.4: モデル選択対応
        self._current_process: Optional[subprocess.Popen] = None
        self._stop_requested = False
        self._process_lock = threading.Lock()
        self._streaming_callback: Optional[Callable[[str], None]] = None

        # CLI利用可能チェック
        self._cli_available, self._cli_message = check_claude_cli_available()

    @property
    def working_dir(self) -> str:
        return self._working_dir

    @working_dir.setter
    def working_dir(self, value: str):
        self._working_dir = value

    @property
    def thinking_level(self) -> str:
        return self._thinking_level

    @thinking_level.setter
    def thinking_level(self, value: str):
        self._thinking_level = value

    @property
    def skip_permissions(self) -> bool:
        """v3.5.0: 権限スキップフラグ"""
        return self._skip_permissions

    @skip_permissions.setter
    def skip_permissions(self, value: bool):
        """v3.5.0: 権限スキップフラグを設定"""
        self._skip_permissions = value

    @property
    def model(self) -> Optional[str]:
        """v3.9.4: 使用するモデル"""
        return self._model

    @model.setter
    def model(self, value: str):
        """v3.9.4: 使用するモデルを設定"""
        self._model = value

    def _get_model_id(self, model_text: str = None) -> Optional[str]:
        """v7.1.0: UIテキストまたはmodel_idからCLI用モデルIDを取得"""
        text = model_text or self._model
        if not text:
            return None
        # マッピングを確認（完全一致）
        if text in self.MODEL_MAP:
            return self.MODEL_MAP[text]
        # claude-で始まるmodel_idはそのまま返す
        if text.startswith("claude-"):
            return text
        # 部分一致でチェック
        text_lower = text.lower()
        if "4.6" in text_lower or "4-6" in text_lower:
            return self.MODEL_MAP["opus-4-6"]
        elif "opus" in text_lower:
            return self.MODEL_MAP["opus-4-5"]
        elif "sonnet" in text_lower:
            return self.MODEL_MAP["sonnet-4-5"]
        return None

    def set_streaming_callback(self, callback: Callable[[str], None]):
        """ストリーミングコールバックを設定"""
        self._streaming_callback = callback

    def is_available(self) -> bool:
        """CLIが利用可能かどうか"""
        return self._cli_available

    def get_availability_message(self) -> str:
        """利用可能性メッセージを取得"""
        return self._cli_message

    def _get_timeout(self) -> int:
        """思考レベルに応じたタイムアウト値を取得（秒）"""
        return self.TIMEOUT_SETTINGS.get(self._thinking_level, self.DEFAULT_TIMEOUT)

    def _build_command(self, extra_options: List[str] = None, use_continue: bool = False) -> List[str]:
        """コマンドを構築

        Args:
            extra_options: 追加オプション
            use_continue: --continue フラグを使用するか（会話継続時）

        v3.5.0: --dangerously-skip-permissions フラグ対応
        v3.9.4: --model フラグ対応（モデル選択）
        """
        claude_cmd = find_claude_command()
        cmd = [claude_cmd, "-p"]  # Print mode (non-interactive)

        # v3.9.4: モデル選択
        model_id = self._get_model_id()
        if model_id:
            cmd.extend(["--model", model_id])
            logger.info(f"[ClaudeCLIBackend] Using model: {model_id}")

        # v3.5.0: 権限確認スキップフラグ
        # ファイル書き込み等の操作時に毎回の確認を省略
        if self._skip_permissions:
            cmd.append("--dangerously-skip-permissions")

        # v3.4.0: 会話継続フラグ
        if use_continue:
            cmd.append("--continue")

        # 思考レベルに応じたオプション追加
        if self._thinking_level == "light":
            cmd.extend(["--think"])
        elif self._thinking_level == "medium":
            cmd.extend(["--think", "hard"])
        elif self._thinking_level in ["medium_opus", "deep"]:
            cmd.extend(["--think", "ultrathink"])

        # 追加オプション
        if extra_options:
            cmd.extend(extra_options)

        return cmd

    def send(self, request: BackendRequest) -> BackendResponse:
        """
        Claude CLIにメッセージを送信

        Args:
            request: Backend リクエスト

        Returns:
            Backend レスポンス
        """
        start_time = time.time()

        # CLI利用不可の場合
        if not self._cli_available:
            return BackendResponse(
                success=False,
                response_text=f"Claude CLI が利用できません:\n\n{self._cli_message}",
                duration_ms=0,
                error_type="CLINotAvailable",
                metadata={"backend": self.name}
            )

        try:
            # コマンド構築
            extra_options = request.context.get("extra_options", []) if request.context else []
            use_continue = request.context.get("use_continue", False) if request.context else False
            cmd = self._build_command(extra_options, use_continue=use_continue)

            # プロンプト構築
            full_prompt = self._build_prompt(request)

            # タイムアウト設定
            timeout = self._get_timeout()

            logger.info(f"[ClaudeCLIBackend] Starting CLI: session={request.session_id}, "
                       f"thinking={self._thinking_level}, timeout={timeout // 60}min")

            # プロセス実行
            with self._process_lock:
                self._stop_requested = False
                self._current_process = popen_hidden(
                    cmd,
                    cwd=self._working_dir,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                )

            # 出力収集用リスト
            stdout_data = []
            stderr_data = []

            def read_stdout():
                try:
                    if self._current_process and self._current_process.stdout:
                        for line in self._current_process.stdout:
                            if self._stop_requested:
                                break
                            stdout_data.append(line)
                            # ストリーミングコールバック
                            if self._streaming_callback:
                                self._streaming_callback(line)
                except Exception as e:
                    logger.error(f"[ClaudeCLIBackend] stdout reader error: {e}")

            def read_stderr():
                try:
                    if self._current_process and self._current_process.stderr:
                        for line in self._current_process.stderr:
                            if self._stop_requested:
                                break
                            stderr_data.append(line)
                except Exception as e:
                    logger.error(f"[ClaudeCLIBackend] stderr reader error: {e}")

            # プロンプトを stdin に送信
            try:
                if self._current_process and self._current_process.stdin:
                    self._current_process.stdin.write(full_prompt)
                    self._current_process.stdin.close()
            except Exception as e:
                return BackendResponse(
                    success=False,
                    response_text=f"プロンプト送信に失敗しました: {e}",
                    duration_ms=(time.time() - start_time) * 1000,
                    error_type="StdinError",
                    metadata={"backend": self.name}
                )

            # 出力リーダースレッド開始
            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stdout_thread.start()
            stderr_thread.start()

            # プロセス終了待機（中断可能）
            elapsed = 0.0
            poll_interval = 0.1
            while elapsed < timeout:
                if self._stop_requested:
                    self._terminate_process()
                    return BackendResponse(
                        success=False,
                        response_text="処理が中断されました",
                        duration_ms=(time.time() - start_time) * 1000,
                        error_type="Interrupted",
                        metadata={"backend": self.name}
                    )

                with self._process_lock:
                    if self._current_process is None:
                        break
                    poll_result = self._current_process.poll()

                if poll_result is not None:
                    break

                time.sleep(poll_interval)
                elapsed += poll_interval

            # リーダースレッド終了待機
            stdout_thread.join(timeout=1.0)
            stderr_thread.join(timeout=1.0)

            # タイムアウトチェック
            with self._process_lock:
                if self._current_process and self._current_process.poll() is None:
                    self._terminate_process()
                    return BackendResponse(
                        success=False,
                        response_text=f"タイムアウト: 処理が{timeout // 60}分を超えました",
                        duration_ms=(time.time() - start_time) * 1000,
                        error_type="Timeout",
                        metadata={"backend": self.name, "timeout_min": timeout // 60}
                    )

            # 出力収集
            stdout = ''.join(stdout_data)
            stderr = ''.join(stderr_data)
            duration_ms = (time.time() - start_time) * 1000

            # エラーチェック
            if stderr and not stdout:
                # 認証エラーの特別処理
                if "login" in stderr.lower() or "auth" in stderr.lower():
                    return BackendResponse(
                        success=False,
                        response_text=(
                            "Claude CLI 認証エラー:\n\n"
                            f"{stderr}\n\n"
                            "【解決方法】\n"
                            "1. ターミナルで `claude login` を実行\n"
                            "2. ブラウザでClaude.comにログイン\n"
                            "3. Max/Proプランが有効であることを確認\n\n"
                            "【Extra Usage について】\n"
                            "使用制限に達した場合も、追加使用量を有効にすることで\n"
                            "従量課金で継続使用できます。\n"
                            "詳細: https://support.claude.com/en/articles/12429409"
                        ),
                        duration_ms=duration_ms,
                        error_type="AuthError",
                        metadata={"backend": self.name, "stderr": stderr}
                    )
                return BackendResponse(
                    success=False,
                    response_text=f"エラー:\n{stderr}",
                    duration_ms=duration_ms,
                    error_type="CLIError",
                    metadata={"backend": self.name, "stderr": stderr}
                )

            logger.info(f"[ClaudeCLIBackend] Completed: session={request.session_id}, "
                       f"duration={duration_ms:.2f}ms, output_len={len(stdout)}")

            return BackendResponse(
                success=True,
                response_text=stdout,
                duration_ms=duration_ms,
                tokens_used=self._estimate_tokens(full_prompt, stdout),
                cost_est=0.0,  # Max/Proプランなのでコスト0（Extra Usageは別途課金）
                metadata={
                    "backend": self.name,
                    "thinking_level": self._thinking_level,
                    "working_dir": self._working_dir,
                    "note": "Claude Max/Proプラン使用（Extra Usage有効時は超過分のみ従量課金）"
                }
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[ClaudeCLIBackend] Error: {e}", exc_info=True)
            return BackendResponse(
                success=False,
                response_text=f"Claude CLI 実行中にエラーが発生しました:\n\n{type(e).__name__}: {e}",
                duration_ms=duration_ms,
                error_type=type(e).__name__,
                metadata={"backend": self.name}
            )

    def _build_prompt(self, request: BackendRequest) -> str:
        """プロンプトを構築"""
        parts = []

        # コンテキスト情報
        if request.context:
            if request.context.get("project_bible"):
                parts.append(f"[プロジェクト情報]\n{request.context['project_bible'][:5000]}\n")
            if request.context.get("current_files"):
                parts.append(f"[関連ファイル]\n{request.context['current_files'][:3000]}\n")

        # ユーザーメッセージ
        parts.append(request.user_text)

        return "\n".join(parts)

    def _estimate_tokens(self, prompt: str, response: str) -> int:
        """トークン数を推定（4文字=1トークンの簡易計算）"""
        total_chars = len(prompt) + len(response)
        return total_chars // 4

    def _terminate_process(self):
        """プロセスを終了"""
        with self._process_lock:
            if self._current_process:
                try:
                    self._current_process.terminate()
                    self._current_process.wait(timeout=5.0)
                except Exception:
                    try:
                        self._current_process.kill()
                    except Exception:
                        pass
                finally:
                    self._current_process = None

    def stop(self):
        """処理を停止"""
        self._stop_requested = True
        self._terminate_process()

    def supports_tools(self) -> bool:
        """CLIはツール使用をサポート"""
        return True

    def send_continue(self, request: BackendRequest) -> BackendResponse:
        """
        v3.4.0: --continue フラグを使用して会話を継続

        Claudeの確認質問や続行確認に対して文脈を維持したまま応答するためのメソッド。

        Args:
            request: Backend リクエスト（user_textに継続メッセージを含む）

        Returns:
            Backend レスポンス
        """
        # contextにuse_continueフラグを設定
        if request.context is None:
            request.context = {}
        request.context["use_continue"] = True

        logger.info(f"[ClaudeCLIBackend] send_continue: message={request.user_text[:50]}...")

        return self.send(request)


# シングルトンインスタンス
_cli_backend_instance: Optional[ClaudeCLIBackend] = None
_cli_backend_lock = threading.Lock()


def get_claude_cli_backend(working_dir: str = None, skip_permissions: bool = True, model: str = None) -> ClaudeCLIBackend:
    """ClaudeCLIBackend のシングルトンインスタンスを取得

    Args:
        working_dir: 作業ディレクトリ
        skip_permissions: 権限確認をスキップするか (v3.5.0)
        model: 使用するモデル名 (v3.9.4)
    """
    global _cli_backend_instance
    if _cli_backend_instance is None:
        with _cli_backend_lock:
            if _cli_backend_instance is None:
                _cli_backend_instance = ClaudeCLIBackend(working_dir, skip_permissions=skip_permissions, model=model)
    else:
        if working_dir:
            _cli_backend_instance.working_dir = working_dir
        _cli_backend_instance.skip_permissions = skip_permissions
        if model:
            _cli_backend_instance.model = model
    return _cli_backend_instance
