"""Helix AI Studio — Promotion Engine

sandbox 内の変更をホストに安全に適用する。
差分生成、プレビュー、選択適用、バックアップ、ロールバック機能を提供。

SandboxBackend / SandboxManager のどちらも引数として受け付ける（後方互換）。
"""

import logging
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# バイナリ拡張子（Promotion 時に自動除外）
BINARY_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".pyc", ".pyo",
    ".class", ".jar", ".war", ".o", ".a",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".mp3", ".mp4", ".avi", ".mov", ".mkv",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".woff", ".woff2", ".ttf", ".eot",
    ".db", ".sqlite", ".sqlite3",
}

# 機密ファイルパターン（特別警告）
SENSITIVE_PATTERNS = [
    ".env", "config/*.json", "*.key", "*.pem", "*.p12",
    "credentials*", "secret*", "token*",
]

# 巨大ファイル閾値
LARGE_FILE_THRESHOLD = 1 * 1024 * 1024  # 1MB


@dataclass
class FileChange:
    """変更ファイル情報"""
    path: str
    change_type: str  # added / modified / deleted
    additions: int = 0
    deletions: int = 0
    is_binary: bool = False
    is_sensitive: bool = False
    is_large: bool = False
    size: int = 0


@dataclass
class PromotionResult:
    """本番適用の結果"""
    success: bool
    applied_files: list = field(default_factory=list)
    skipped_files: list = field(default_factory=list)
    backup_path: str = ""
    error: Optional[str] = None


class PromotionEngine:
    """sandbox → host の差分適用エンジン"""

    def __init__(self):
        pass

    def generate_diff(self, backend) -> str:
        """sandbox 内の変更を unified diff 形式で取得

        Args:
            backend: SandboxBackend または SandboxManager インスタンス
        """
        if not backend or backend.get_status().value != "running":
            return ""
        return backend.get_diff()

    def preview_changes(self, diff: str) -> list:
        """diff を解析して変更ファイル一覧を返す"""
        changes = []
        if not diff:
            return changes

        # unified diff 形式をパース
        current_file = None
        additions = 0
        deletions = 0

        for line in diff.split("\n"):
            # --- a/path or +++ b/path
            if line.startswith("diff --git"):
                if current_file:
                    changes.append(self._create_file_change(current_file, additions, deletions))
                match = re.search(r"b/(.+)$", line)
                if match:
                    current_file = match.group(1)
                    additions = 0
                    deletions = 0
            elif line.startswith("+") and not line.startswith("+++"):
                additions += 1
            elif line.startswith("-") and not line.startswith("---"):
                deletions += 1

        # 最後のファイル
        if current_file:
            changes.append(self._create_file_change(current_file, additions, deletions))

        # diff -rq 形式（git が無い場合）
        if not changes:
            for line in diff.split("\n"):
                line = line.strip()
                if line.startswith("Files") and "differ" in line:
                    match = re.search(r"Files .+ and (.+) differ", line)
                    if match:
                        changes.append(FileChange(
                            path=match.group(1).replace("/workspace/", ""),
                            change_type="modified",
                        ))
                elif line.startswith("Only in /workspace"):
                    match = re.search(r"Only in /workspace/?(.*):\s*(.+)", line)
                    if match:
                        subdir = match.group(1)
                        filename = match.group(2)
                        full = f"{subdir}/{filename}" if subdir else filename
                        changes.append(FileChange(path=full, change_type="added"))

        return changes

    def apply(
        self,
        backend,
        target_path: str,
        selected_files: Optional[list] = None,
    ) -> PromotionResult:
        """sandbox の変更をホストに適用

        Args:
            backend: SandboxBackend または SandboxManager インスタンス
        """
        if not backend or backend.get_status().value != "running":
            return PromotionResult(success=False, error="Sandbox not running")

        target = Path(target_path)
        if not target.is_dir():
            return PromotionResult(success=False, error=f"Target path not found: {target_path}")

        # 1. バックアップ作成
        backup_dir = target / f".helix-backup-{int(time.time())}"
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return PromotionResult(success=False, error=f"Backup creation failed: {e}")

        applied = []
        skipped = []

        try:
            # 2. 差分取得
            diff = self.generate_diff(backend)
            changes = self.preview_changes(diff)

            if not changes:
                return PromotionResult(
                    success=True,
                    applied_files=[],
                    skipped_files=[],
                    backup_path=str(backup_dir),
                    error="No changes detected",
                )

            # 3. 選択ファイルのみ適用
            for change in changes:
                file_path = change.path

                # 選択フィルタ
                if selected_files and file_path not in selected_files:
                    skipped.append(file_path)
                    continue

                # セキュリティチェック
                if not self._validate_path(file_path):
                    skipped.append(file_path)
                    logger.warning(f"[Promotion] Skipped (path traversal): {file_path}")
                    continue

                # バイナリ除外
                if change.is_binary:
                    skipped.append(file_path)
                    continue

                # 既存ファイルのバックアップ
                host_file = target / file_path
                if host_file.exists():
                    backup_file = backup_dir / file_path
                    backup_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(host_file, backup_file)

                # sandbox からファイルを取得
                # SandboxBackend: read_file returns bytes
                # SandboxManager: read_file returns dict {"content": ..., "error": ...}
                raw = backend.read_file(f"/workspace/{file_path}")
                if isinstance(raw, dict):
                    # SandboxManager 互換
                    if "error" in raw:
                        skipped.append(file_path)
                        continue
                    content = raw.get("content", "")
                elif isinstance(raw, bytes):
                    # SandboxBackend
                    if not raw:
                        skipped.append(file_path)
                        continue
                    content = raw.decode("utf-8", errors="replace")
                else:
                    skipped.append(file_path)
                    continue

                # ホストに書き込み
                host_file.parent.mkdir(parents=True, exist_ok=True)
                host_file.write_text(content, encoding="utf-8")
                applied.append(file_path)

            return PromotionResult(
                success=True,
                applied_files=applied,
                skipped_files=skipped,
                backup_path=str(backup_dir),
            )

        except Exception as e:
            logger.error(f"[Promotion] Apply failed: {e}")
            return PromotionResult(
                success=False,
                applied_files=applied,
                skipped_files=skipped,
                backup_path=str(backup_dir),
                error=str(e),
            )

    def rollback(self, backup_path: str, target_path: str) -> bool:
        """直前の適用をロールバック"""
        backup = Path(backup_path)
        target = Path(target_path)

        if not backup.is_dir():
            logger.error(f"[Promotion] Backup not found: {backup_path}")
            return False

        try:
            for backup_file in backup.rglob("*"):
                if backup_file.is_file():
                    rel = backup_file.relative_to(backup)
                    dest = target / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_file, dest)

            logger.info(f"[Promotion] Rollback completed from: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"[Promotion] Rollback failed: {e}")
            return False

    # ─── 内部ヘルパー ───

    def _create_file_change(self, path: str, additions: int, deletions: int) -> FileChange:
        """FileChange オブジェクトを生成"""
        ext = Path(path).suffix.lower()
        is_binary = ext in BINARY_EXTENSIONS
        is_sensitive = any(
            re.match(pattern.replace("*", ".*"), path)
            for pattern in SENSITIVE_PATTERNS
        )

        change_type = "modified"
        if deletions == 0 and additions > 0:
            change_type = "added"
        elif additions == 0 and deletions > 0:
            change_type = "deleted"

        return FileChange(
            path=path,
            change_type=change_type,
            additions=additions,
            deletions=deletions,
            is_binary=is_binary,
            is_sensitive=is_sensitive,
        )

    def _validate_path(self, path: str) -> bool:
        """パストラバーサル検査"""
        normalized = os.path.normpath(path)
        if ".." in normalized:
            return False
        if os.path.isabs(normalized):
            return False
        return True
