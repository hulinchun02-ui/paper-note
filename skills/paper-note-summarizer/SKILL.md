---
name: paper-note-summarizer
description: Summarize academic paper PDFs into rigorous Chinese paper-note tables matching a fixed template, with DOCX, Markdown, and evidence JSON outputs. Use when Codex is asked to read, summarize, extract, or create notes for a research paper PDF, especially when the user wants fields such as title, authors, venue, method, experiments, highlights, and conclusion with evidence grounded in the original paper.
---

# Paper Note Summarizer

## Overview

Use this skill to turn a paper PDF into the fixed Chinese “论文笔记” structure. The bundled wrapper calls the project-level script, which extracts text with page numbers, calls an OpenAI-compatible API, validates the schema, then writes DOCX, Markdown, and evidence JSON files.

## Workflow

1. Confirm the input is a machine-readable PDF. If extraction reports too little text, tell the user the current version does not perform OCR.
2. Install dependencies from the project root when needed:

```bash
pip install -r requirements.txt
```

3. Run the summarizer from the project root:

```bash
python paper_note_summarizer.py --pdf /path/to/paper.pdf --out outputs
```

4. Prefer a local `.env` file copied from `.env.example`:

```bash
cp .env.example .env
```

Then fill in:

```bash
DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

The script also accepts real environment variables, CLI flags, and `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL` for other OpenAI-compatible providers.

5. If the user provides a known paper URL or code URL, pass it explicitly:

```bash
python paper_note_summarizer.py --pdf paper.pdf --out outputs --pdf-link "https://..." --code-link "https://github.com/..."
```

## Output Contract

Expect four files in the output directory:

- `<paper>.docx`: editable table styled like the paper-note template.
- `<paper>.md`: same content in Markdown.
- `<paper>.evidence.json`: page references, short quotes, confidence, and notes for each field.
- `<paper>.summary.json`: full structured value plus evidence object.

The fixed fields are:

- 论文概述：论文题目、作者、期刊/会议、论文 PDF 链接、论文代码链接。
- 论文内容：主要思想、所解决的问题、论文主要内容、方法核心步骤、其他补充。
- 实验：数据集、对比方法、评价指标、实验结果及结论。
- 论文亮点。
- 论文总结。

## Rigor Rules

- Do not invent missing facts. If the paper does not state a field, keep “论文未明确说明”.
- Prefer claims that can be tied to evidence pages and short quotes.
- Check `evidence.json` before presenting results. If important fields have `low` confidence, mention that they need manual review.
- Keep source quotes short. Use the generated DOCX/Markdown as the user-facing note, not the evidence file.

## Script Resource

Use `scripts/paper_note_summarizer.py` only as a convenience wrapper. The implementation lives at the project root in `paper_note_summarizer.py` so project users and this skill share the same code path.
