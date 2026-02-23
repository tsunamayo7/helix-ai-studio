"""
Helix AI Studio - Codex CLI Backend (v11.0.0)

GPT-5.3-Codex CLI実行バックエンド。
`codex exec` コマンドを使用してGPT-5.3-Codexを呼び出す。

コマンドパターン:
  codex exec --model gpt-5.3-codex [-c model_reasoning_effort=<effort>] "<PROMPT>"

effortが"default"の場合は -c オプションを省略する。

v11.0.0: Windows上でnpm .cmdファイルを正しく検出・実行するため、
         shutil.which()でフルパスを取得し、shell=True付きで実行する。
"""

import subprocess
import shutil
import sys
import logging

from ..utils.subprocess_utils import run_hidden

logger = logging.getLogger(__name__)

CODEX_MODEL = "gpt-5.3-codex"

# v11.0.0: キャッシュされたcodexパス（初回検出後に保持）
_codex_resolved_path: str | None = None


def _resolve_codex_path() -> str | None:
    """codexコマンドのフルパスを解決する（Windows .cmd対応）"""
    global _codex_resolved_path
    if _codex_resolved_path is not None:
        return _codex_resolved_path

    import os

    # 1. shutil.which（PATHから検索）
    path = shutil.which("codex")
    if path:
        _codex_resolved_path = path
        return path

    # 2. Windows npm globalの既知パスを検索
    if os.name == 'nt':
        appdata = os.environ.get('APPDATA', '')
        candidates = []
        if appdata:
            candidates.extend([
                os.path.join(appdata, 'npm', 'codex.cmd'),
                os.path.join(appdata, 'npm', 'codex'),
            ])
        userprofile = os.environ.get('USERPROFILE', '')
        if userprofile:
            candidates.append(os.path.join(userprofile, '.npm-global', 'codex.cmd'))

        for p in candidates:
            if os.path.isfile(p):
                _codex_resolved_path = p
                return p
    else:
        # Linux/Mac
        home = os.path.expanduser("~")
        for p in [
            os.path.join(home, ".npm-global", "bin", "codex"),
            "/usr/local/bin/codex",
            "/usr/bin/codex",
        ]:
            if os.path.isfile(p):
                _codex_resolved_path = p
                return p

    return None


def _run_codex(args: list, **kwargs) -> subprocess.CompletedProcess:
    """codexコマンドを実行する（Windows .cmd対応）

    Windows上ではshell=Trueを使用して.cmdファイルを正しく実行する。
    """
    resolved = _resolve_codex_path()

    if resolved:
        cmd = [resolved] + args
    else:
        cmd = ["codex"] + args

    # Windows上では.cmdファイルの実行にshell=Trueが必要
    if sys.platform == "win32":
        # shell=True時はコマンドを文字列で渡す
        cmd_str = subprocess.list2cmdline(cmd)
        kwargs["shell"] = True
        return run_hidden(cmd_str, **kwargs)
    else:
        return run_hidden(cmd, **kwargs)


def run_codex_cli(
    prompt: str,
    effort: str = "default",
    run_cwd: str = None,
    timeout: int = 600,
) -> str:
    """
    Codex CLI (codex exec) を呼び出してプロンプトを実行する。

    Args:
        prompt: 送信するプロンプトテキスト
        effort: 推論努力度 ("default" / "minimal" / "low" / "medium" / "high" / "xhigh")
                "default" の場合は -c オプションを省略する
        run_cwd: 実行時の作業ディレクトリ（省略時はNone）
        timeout: タイムアウト秒数（デフォルト600秒）

    Returns:
        Codex CLIの出力テキスト

    Raises:
        RuntimeError: Codex CLIがエラーを返した場合
        subprocess.TimeoutExpired: タイムアウトした場合
    """
    args = ["exec", "--model", CODEX_MODEL]

    # effort が "default" 以外の場合のみ -c オプションを付加
    if effort and effort != "default":
        args += ["-c", f"model_reasoning_effort={effort}"]

    args.append(prompt)

    logger.debug(f"Codex CLI command: codex {' '.join(args[:4])}... (cwd={run_cwd})")

    try:
        result = _run_codex(
            args,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout,
            cwd=run_cwd,
        )

        stdout = result.stdout or ""
        stderr = result.stderr or ""

        if result.returncode == 0:
            return stdout.strip()
        else:
            raise RuntimeError(
                f"Codex CLI終了コード {result.returncode}: "
                f"{stderr[:500] if stderr else 'エラー詳細なし'}"
            )

    except FileNotFoundError:
        raise RuntimeError(
            "Codex CLI が見つかりません。\n\n"
            "【インストール方法】\n"
            "1. Node.js をインストール\n"
            "2. npm install -g @openai/codex\n"
            "3. codex auth でログイン\n\n"
            "参考: https://github.com/openai/codex"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"Codex CLIがタイムアウト({timeout}秒)しました"
        )


def check_codex_cli_available() -> tuple[bool, str]:
    """Codex CLIが利用可能かチェックする (v11.0.0: Windows .cmd完全対応)

    Returns:
        (available: bool, message: str)
    """
    # 1. パス解決を試みる
    resolved = _resolve_codex_path()
    if resolved:
        try:
            result = _run_codex(
                ["--version"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                return True, f"Codex CLI found: {version} ({resolved})"
        except Exception as e:
            logger.debug(f"Codex path resolved ({resolved}) but exec failed: {e}")

    # 2. npx経由を試行
    npx_path = shutil.which("npx")
    if npx_path:
        try:
            if sys.platform == "win32":
                cmd_str = subprocess.list2cmdline([npx_path, "codex", "--version"])
                result = run_hidden(cmd_str, capture_output=True, text=True, timeout=15, shell=True)
            else:
                result = run_hidden([npx_path, "codex", "--version"], capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                return True, f"Codex CLI (via npx): {result.stdout.strip()}"
        except Exception:
            pass

    # 3. shell=True で直接試行（最終手段）
    try:
        result = run_hidden(
            "codex --version",
            capture_output=True, text=True, timeout=10, shell=True,
        )
        if result.returncode == 0:
            return True, f"Codex CLI found: {result.stdout.strip()}"
        else:
            return False, f"Codex CLI returned error: {result.stderr}"
    except FileNotFoundError:
        return False, (
            "Codex CLI が見つかりません。\n\n"
            "【インストール方法】\n"
            "1. Node.js をインストール\n"
            "2. npm install -g @openai/codex\n"
            "3. codex auth でログイン\n\n"
            "参考: https://github.com/openai/codex"
        )
    except subprocess.TimeoutExpired:
        return False, "Codex CLI のバージョン確認がタイムアウトしました"
    except Exception as e:
        return False, f"Codex CLI チェック中にエラー: {e}"
