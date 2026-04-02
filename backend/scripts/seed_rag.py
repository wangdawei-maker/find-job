"""
将 ``backend/rag_seed/`` 下所有 ``*_seed.txt`` 读入并写入 RAG 向量库。

依赖 ``backend/.env`` 中的 Embedding 配置；需先安装依赖并在 ``backend`` 包路径下运行。

用法（在 ``backend`` 目录）::

    python scripts/seed_rag.py
"""

from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.rag_service import ingest_document_text


def main() -> None:
    """
    扫描 ``rag_seed`` 目录，对每个 ``*_seed.txt`` 调用 ``ingest_document_text``。

    Returns:
        None；过程信息打印到 stdout。
    """
    load_dotenv(ROOT / ".env")
    seed_dir = ROOT / "rag_seed"
    files = sorted(seed_dir.glob("*_seed.txt"))
    if not files:
        print("No *_seed.txt files found in backend/rag_seed")
        return

    total = 0
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        chunks = ingest_document_text(source=f.name, title=f.stem, text=text)
        total += chunks
        print(f"Ingested {f.name}: {chunks} chunks")

    print(f"Done. Total chunks: {total}")


if __name__ == "__main__":
    main()
