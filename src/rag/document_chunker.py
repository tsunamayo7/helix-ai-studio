"""
Helix AI Studio - Document Chunker (v8.5.0)
ドキュメントをRAG用チャンクに分割する
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from ..utils.constants import SUPPORTED_DOC_EXTENSIONS, DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """チャンクデータ"""
    content: str
    chunk_index: int
    source_file: str
    metadata: dict = field(default_factory=dict)
    embedding: Optional[bytes] = None
    summary: Optional[str] = None
    keywords: Optional[List[str]] = None
    entities: Optional[List[str]] = None


class DocumentChunker:
    """ドキュメントをRAG用チャンクに分割"""

    def chunk_file(self, file_path: str, strategy: str = "fixed",
                   chunk_size: int = DEFAULT_CHUNK_SIZE,
                   overlap: int = DEFAULT_CHUNK_OVERLAP) -> List[Chunk]:
        """
        ファイルをチャンクに分割

        Args:
            file_path: ファイルパス
            strategy: "fixed" | "semantic" | "sentence"
            chunk_size: チャンクサイズ（文字数近似）
            overlap: オーバーラップ文字数

        Returns:
            チャンクのリスト
        """
        text = self._read_file(file_path)
        if not text or not text.strip():
            logger.warning(f"Empty or unreadable file: {file_path}")
            return []

        file_name = Path(file_path).name
        ext = Path(file_path).suffix.lower()

        if strategy == "semantic":
            chunks = self._semantic_chunk(text, chunk_size, overlap)
        elif strategy == "sentence":
            chunks = self._sentence_chunk(text, chunk_size)
        else:
            chunks = self._fixed_chunk(text, chunk_size, overlap)

        result = []
        for i, chunk_text in enumerate(chunks):
            if chunk_text.strip():
                result.append(Chunk(
                    content=chunk_text.strip(),
                    chunk_index=i,
                    source_file=file_name,
                    metadata={
                        "file_type": ext,
                        "strategy": strategy,
                        "full_path": str(file_path),
                    }
                ))

        logger.info(f"Chunked {file_name}: {len(result)} chunks (strategy={strategy})")
        return result

    def _read_file(self, path: str) -> str:
        """ファイル形式に応じた読込"""
        ext = Path(path).suffix.lower()
        try:
            if ext in ('.txt', '.md', '.csv', '.json'):
                return Path(path).read_text(encoding='utf-8')
            elif ext == '.pdf':
                return self._read_pdf(path)
            elif ext == '.docx':
                return self._read_docx(path)
            else:
                return Path(path).read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            logger.error(f"Failed to read {path}: {e}")
            return ""

    def _read_pdf(self, path: str) -> str:
        """PDFファイルをテキスト抽出"""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(path)
            pages = []
            for page_num, page in enumerate(doc):
                text = page.get_text()
                if text.strip():
                    pages.append(text)
            doc.close()
            return '\n\n'.join(pages)
        except ImportError:
            logger.warning("PyMuPDF not installed. PDF reading unavailable.")
            return ""
        except Exception as e:
            logger.error(f"PDF read error: {e}")
            return ""

    def _read_docx(self, path: str) -> str:
        """DOCXファイルをテキスト抽出"""
        try:
            import docx
            doc = docx.Document(path)
            return '\n'.join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            logger.warning("python-docx not installed. DOCX reading unavailable.")
            return ""
        except Exception as e:
            logger.error(f"DOCX read error: {e}")
            return ""

    def _fixed_chunk(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """固定長分割"""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - overlap
            if start >= len(text):
                break
        return chunks

    def _semantic_chunk(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """段落・セクション境界優先の分割"""
        # 段落で分割
        paragraphs = re.split(r'\n\s*\n', text)
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) + 1 <= chunk_size:
                current_chunk += ("\n\n" + para if current_chunk else para)
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                # 段落自体がchunk_sizeを超える場合は固定長分割
                if len(para) > chunk_size:
                    sub_chunks = self._fixed_chunk(para, chunk_size, overlap)
                    chunks.extend(sub_chunks)
                    current_chunk = ""
                else:
                    # オーバーラップ: 前チャンクの末尾を含める
                    if chunks and overlap > 0:
                        prev_tail = chunks[-1][-overlap:]
                        current_chunk = prev_tail + "\n\n" + para
                    else:
                        current_chunk = para

        if current_chunk.strip():
            chunks.append(current_chunk)

        return chunks

    def _sentence_chunk(self, text: str, chunk_size: int) -> List[str]:
        """文単位の分割（短いドキュメント向け）"""
        # 日本語・英語の文末を考慮
        sentences = re.split(r'(?<=[。.!?！？\n])\s*', text)
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if len(current_chunk) + len(sentence) + 1 <= chunk_size:
                current_chunk += (" " + sentence if current_chunk else sentence)
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence

        if current_chunk.strip():
            chunks.append(current_chunk)

        return chunks

    @staticmethod
    def get_file_preview(file_path: str, max_chars: int = 500) -> str:
        """ファイルの先頭プレビューを取得"""
        try:
            ext = Path(file_path).suffix.lower()
            if ext in ('.txt', '.md', '.csv', '.json'):
                text = Path(file_path).read_text(encoding='utf-8', errors='replace')
            elif ext == '.pdf':
                try:
                    import fitz
                    doc = fitz.open(file_path)
                    text = doc[0].get_text() if len(doc) > 0 else ""
                    doc.close()
                except (ImportError, Exception):
                    text = "(PDF preview unavailable)"
            else:
                text = Path(file_path).read_text(encoding='utf-8', errors='replace')
            return text[:max_chars]
        except Exception:
            return "(preview unavailable)"
