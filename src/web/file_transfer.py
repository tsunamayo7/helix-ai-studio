"""
Web UIファイル転送の制限・バリデーション定義 (v9.5.0)。
"""

from pathlib import Path

# アップロード制限
UPLOAD_MAX_SIZE_MB = 10
UPLOAD_MAX_SIZE_BYTES = UPLOAD_MAX_SIZE_MB * 1024 * 1024

UPLOAD_ALLOWED_EXTENSIONS = {
    # テキスト系
    '.txt', '.md', '.csv', '.json', '.yaml', '.yml', '.toml',
    '.xml', '.html', '.css', '.log', '.ini', '.cfg', '.env',
    # コード系
    '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.c', '.cpp',
    '.h', '.hpp', '.cs', '.go', '.rs', '.rb', '.php', '.swift',
    '.kt', '.scala', '.sh', '.bat', '.ps1', '.sql',
    # ドキュメント系
    '.pdf', '.docx',
    # 画像系
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg',
}

UPLOAD_BLOCKED_EXTENSIONS = {
    '.exe', '.dll', '.msi', '.scr', '.com',
    '.vbs', '.wsf', '.wsh',
    '.zip', '.rar', '.7z', '.tar', '.gz',
}


def validate_upload(filename: str, size: int = None) -> str | None:
    """アップロードファイルのバリデーション。エラーメッセージを返す。Noneなら OK。"""
    if not filename:
        return "ファイル名が空です"

    ext = Path(filename).suffix.lower()

    if ext in UPLOAD_BLOCKED_EXTENSIONS:
        return f"セキュリティ上の理由で {ext} ファイルはアップロードできません"

    if ext not in UPLOAD_ALLOWED_EXTENSIONS:
        return f"{ext} ファイルは対応していません。対応形式: テキスト, コード, 画像, PDF, DOCX"

    if size and size > UPLOAD_MAX_SIZE_BYTES:
        return f"ファイルサイズ ({size // (1024*1024)}MB) が上限 ({UPLOAD_MAX_SIZE_MB}MB) を超えています"

    return None
