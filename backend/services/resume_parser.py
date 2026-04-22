"""
简历/文档文本提取。

根据文件扩展名选择解析方式，供简历诊断与 RAG 文件入库复用。
"""

import io
import os

from docx import Document
from fastapi import HTTPException
from pypdf import PdfReader


def _parse_error(code: str, message: str, hint: str | None = None) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"code": code, "message": message, "hint": hint},
    )


def extract_resume_text(filename: str, raw_bytes: bytes) -> str:
    """
    从上传文件的二进制内容中提取纯文本。

    支持：``.pdf``、``.docx``、``.txt``、``.md``。不支持老式 ``.doc``。

    Args:
        filename: 原始文件名（用于判断扩展名）。
        raw_bytes: 文件完整字节内容。

    Returns:
        去除首尾空白后的文本；页与段之间用换行拼接。

    Raises:
        HTTPException: 不支持的格式、解析失败或文本为空相关场景。
    """
    ext = os.path.splitext(filename.lower())[1]
    if ext == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(raw_bytes))
            return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
        except Exception as exc:
            raise _parse_error(
                code="pdf_parse_failed",
                message="PDF 解析失败：文件可能损坏、加密，或为图片扫描版",
                hint=f"请尝试导出为可复制文本的 PDF 或 docx（error: {exc}）",
            ) from exc

    if ext == ".docx":
        try:
            doc = Document(io.BytesIO(raw_bytes))
            return "\n".join(p.text for p in doc.paragraphs).strip()
        except Exception as exc:
            raise _parse_error(
                code="docx_parse_failed",
                message="DOCX 解析失败：请确认文件未损坏并使用标准 .docx 格式",
                hint=f"可尝试重新另存为 docx 后上传（error: {exc}）",
            ) from exc

    if ext in {".txt", ".md"}:
        return raw_bytes.decode("utf-8", errors="ignore").strip()

    if ext == ".doc":
        raise _parse_error(
            code="doc_not_supported",
            message="暂不支持 .doc 二进制格式",
            hint="请另存为 .docx 或导出为 .pdf 后上传",
        )

    raise _parse_error(
        code="file_type_not_supported",
        message="仅支持 .pdf / .docx / .txt / .md 文件",
        hint="请转换为支持的文件格式后重试",
    )
