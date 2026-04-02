"""
使用 DeepSeek 将 ``backend/rag_raw/*.txt`` 整理为结构化种子文本，输出到 ``backend/rag_seed/*_seed.txt``。

用于把原始资料转为适合 RAG 切块的格式；完成后需再运行 ``seed_rag.py`` 入库。

用法::

    python scripts/build_rag_seed.py
"""

from pathlib import Path
import re
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.deepseek import call_deepseek

RAW_DIR = ROOT / "rag_raw"
SEED_DIR = ROOT / "rag_seed"


def _sanitize_filename(name: str) -> str:
    """
    将字符串转为安全文件名（去除非法字符）。

    Args:
        name: 原始词干或标题。

    Returns:
        可用作文件名的字符串。
    """
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", name).strip()
    return cleaned or "rag_seed_generated"


def _build_prompt(raw_text: str) -> str:
    """
    构造「原始资料 -> 结构化 RAG 种子」的提示词。

    Args:
        raw_text: 原始文本（过长时截断）。

    Returns:
        发给模型的完整 user prompt。
    """
    return f"""
你是求职知识整理助手。请把下面原始资料整理为可用于 RAG 检索的结构化文本。
输出必须是纯文本，不要 markdown 代码块，不要多余说明。
每条知识点按以下格式输出，并至少输出 5 条：

[主题] ...
[适用岗位] ...
[问题] ...
[要点]
- ...
- ...
[示例回答]
...
[关键词] ...

原始资料：
{raw_text[:12000]}
""".strip()


def transform_one_file(path: Path) -> Path:
    """
    对单个 ``rag_raw`` 下的 ``.txt`` 调用 DeepSeek，写入对应 ``*_seed.txt``。

    Args:
        path: 输入文件路径。

    Returns:
        输出种子文件路径。

    Raises:
        ValueError: 输入为空。
        RuntimeError: 重试后仍失败。
    """
    raw_text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw_text:
        raise ValueError(f"Empty input file: {path.name}")

    prompt = _build_prompt(raw_text)
    output = None
    last_error = None
    for attempt in range(1, 4):
        try:
            output = call_deepseek(
                messages=[
                    {"role": "system", "content": "你只输出干净的结构化纯文本内容。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                timeout_seconds=120.0,
            )
            break
        except Exception as exc:
            last_error = exc
            print(f"[WARN] {path.name} attempt {attempt}/3 failed: {exc}")
    if output is None:
        raise RuntimeError(f"Build seed failed for {path.name}: {last_error}")

    SEED_DIR.mkdir(parents=True, exist_ok=True)
    out_name = f"{_sanitize_filename(path.stem)}_seed.txt"
    out_path = SEED_DIR / out_name
    out_path.write_text(output.strip() + "\n", encoding="utf-8")
    return out_path


def main() -> None:
    """
    批量处理 ``rag_raw`` 中所有 ``.txt`` 文件。

    Returns:
        None；进度打印到 stdout。
    """
    load_dotenv(ROOT / ".env")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    SEED_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(RAW_DIR.glob("*.txt"))
    if not files:
        print("No input files found. Put .txt files into backend/rag_raw first.")
        return

    for f in files:
        out = transform_one_file(f)
        print(f"Built seed from {f.name} -> {out.name}")

    print("Done. Now run: python scripts/seed_rag.py")


if __name__ == "__main__":
    main()
