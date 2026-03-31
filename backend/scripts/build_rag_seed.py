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
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", name).strip()
    return cleaned or "rag_seed_generated"


def _build_prompt(raw_text: str) -> str:
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
