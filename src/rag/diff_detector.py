"""
Helix AI Studio - Diff Detector (v8.5.0)
情報収集フォルダのファイル変更差分を検出する
"""

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict

from ..utils.constants import SUPPORTED_DOC_EXTENSIONS
from ..utils.i18n import t

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """ファイル情報"""
    path: str
    name: str
    hash: str
    size: int
    modified: float


@dataclass
class DiffResult:
    """差分検出結果"""
    new_files: List[FileInfo]
    modified_files: List[FileInfo]
    deleted_files: List[str]
    unchanged_files: List[FileInfo]

    @property
    def has_changes(self) -> bool:
        return bool(self.new_files or self.modified_files or self.deleted_files)

    @property
    def summary(self) -> str:
        parts = []
        if self.new_files:
            parts.append(t('desktop.infoTab.diffSummaryNew', count=len(self.new_files)))
        if self.modified_files:
            parts.append(t('desktop.infoTab.diffSummaryModified', count=len(self.modified_files)))
        if self.deleted_files:
            parts.append(t('desktop.infoTab.diffSummaryDeleted', count=len(self.deleted_files)))
        if self.unchanged_files:
            parts.append(t('desktop.infoTab.diffSummaryUnchanged', count=len(self.unchanged_files)))
        return ", ".join(parts) if parts else t('desktop.infoTab.diffSummaryNoChanges')


class DiffDetector:
    """ファイル変更の差分検出"""

    def __init__(self, db_conn_factory=None):
        """
        Args:
            db_conn_factory: sqlite3.Connection を返す callable
        """
        self._db_conn_factory = db_conn_factory

    def detect_changes(self, folder_path: str) -> DiffResult:
        """情報収集フォルダの変更を検出"""
        current_files = self._scan_folder(folder_path)
        stored_hashes = self._get_stored_hashes()

        current_paths = {f.path for f in current_files}
        stored_paths = set(stored_hashes.keys())

        new_files = [f for f in current_files if f.path not in stored_paths]
        modified_files = [
            f for f in current_files
            if f.path in stored_paths and f.hash != stored_hashes[f.path]
        ]
        deleted_files = [p for p in stored_paths if p not in current_paths]
        unchanged_files = [
            f for f in current_files
            if f.path in stored_paths and f.hash == stored_hashes[f.path]
        ]

        result = DiffResult(
            new_files=new_files,
            modified_files=modified_files,
            deleted_files=deleted_files,
            unchanged_files=unchanged_files,
        )
        logger.info(f"Diff detection: {result.summary}")
        return result

    def _scan_folder(self, path: str) -> List[FileInfo]:
        """フォルダ内ファイルをスキャンしハッシュ計算"""
        results = []
        folder = Path(path)
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
            return results

        for f in folder.rglob('*'):
            if f.is_file() and f.suffix.lower() in SUPPORTED_DOC_EXTENSIONS:
                try:
                    content = f.read_bytes()
                    file_hash = hashlib.sha256(content).hexdigest()
                    results.append(FileInfo(
                        path=str(f.name),  # フォルダからの相対名
                        name=f.name,
                        hash=file_hash,
                        size=len(content),
                        modified=f.stat().st_mtime,
                    ))
                except Exception as e:
                    logger.warning(f"Failed to scan {f}: {e}")

        return results

    def _get_stored_hashes(self) -> Dict[str, str]:
        """DBから保存済みファイルハッシュを取得"""
        if not self._db_conn_factory:
            return {}
        try:
            conn = self._db_conn_factory()
            try:
                rows = conn.execute(
                    "SELECT DISTINCT source_file, source_hash FROM documents"
                ).fetchall()
                # 同一ファイルの最新ハッシュを取得
                result = {}
                for row in rows:
                    result[row["source_file"] if hasattr(row, '__getitem__') and isinstance(row, dict)
                           else row[0]] = (row["source_hash"] if hasattr(row, '__getitem__') and isinstance(row, dict)
                                           else row[1])
                return result
            finally:
                conn.close()
        except Exception as e:
            logger.debug(f"No stored hashes available: {e}")
            return {}
