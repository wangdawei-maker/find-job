把你收集的原始资料（JD、面经、题库整理稿）先放到这个目录，格式建议为 .txt。

示例：
- frontend_jd_samples.txt
- niuke_interview_notes.txt

然后执行：
python scripts/build_rag_seed.py

脚本会把结构化后的种子文件输出到 backend/rag_seed/，最后再执行：
python scripts/seed_rag.py
