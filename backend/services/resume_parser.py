import io
import os

from docx import Document
from fastapi import HTTPException
from pypdf import PdfReader


def extract_resume_text(filename: str, raw_bytes: bytes) -> str:
    # 根据扩展名做不同解析：pdf/docx/txt
    ext = os.path.splitext(filename.lower())[1]
    if ext == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(raw_bytes))
            return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"PDF 解析失败：文件可能损坏、加密，或为图片扫描版（error: {exc})",
            ) from exc

    if ext == ".docx":
        try:
            doc = Document(io.BytesIO(raw_bytes))
            return "\n".join(p.text for p in doc.paragraphs).strip()
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"DOCX 解析失败：请确认文件未损坏并使用标准 .docx 格式（error: {exc})",
            ) from exc

    if ext == ".txt":
        return raw_bytes.decode("utf-8", errors="ignore").strip()

    if ext == ".doc":
        # .doc 是老二进制格式，跨平台解析复杂且不稳定，这里给出明确提示
        raise HTTPException(
            status_code=400,
            detail="暂不支持 .doc 二进制格式，请另存为 .docx 或导出为 .pdf 后上传",
        )

    raise HTTPException(status_code=400, detail="仅支持 .pdf / .docx / .txt 文件")
