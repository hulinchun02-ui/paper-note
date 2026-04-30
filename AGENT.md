# AGENT.md

## 项目概览

这是一个论文自动总结 CLI 项目。主程序读取可复制文本的论文 PDF，按页抽取正文，调用 OpenAI-compatible API（默认 DeepSeek），生成中文“论文笔记”。

默认输出：

- `*.docx`：接近模板样式的 Word 表格。
- `*.md`：同内容 Markdown 笔记。
- `*.evidence.json`：每个字段对应页码、短原文片段、可信度和备注。
- `*.summary.json`：完整结构化结果。

## 关键文件

- `paper_note_summarizer.py`：主 CLI、PDF 抽取、模型调用、schema 校验、DOCX/MD/JSON 渲染。
- `requirements.txt`：运行依赖。
- `tests/test_paper_note_summarizer.py`：单元测试，覆盖 schema、Markdown/evidence 输出和分块页码保持。
- `skills/paper-note-summarizer/SKILL.md`：Codex skill 使用说明。
- `skills/paper-note-summarizer/scripts/paper_note_summarizer.py`：skill 包装脚本，复用项目根目录主程序。

## 环境准备

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

DeepSeek 默认配置。推荐复制 `.env.example` 到 `.env` 后填写真实 key：

```bash
cp .env.example .env
```

`.env` 内容：

```bash
DEEPSEEK_API_KEY=你的DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

仍兼容 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`。CLI 参数优先级最高，真实环境变量优先级高于 `.env`。

## 常用命令

运行 dry-run，验证项目可启动和渲染链路：

```bash
.venv/bin/python paper_note_summarizer.py --dry-run --out outputs --title-hint 测试论文
```

总结真实论文：

```bash
.venv/bin/python paper_note_summarizer.py --pdf /path/to/paper.pdf --out outputs
```

带论文和代码链接：

```bash
.venv/bin/python paper_note_summarizer.py \
  --pdf paper.pdf \
  --out outputs \
  --pdf-link "https://..." \
  --code-link "https://github.com/..."
```

运行测试：

```bash
.venv/bin/python -m unittest discover -s tests
```

## 实现要点

- 扫描版 PDF 暂不支持 OCR。若抽取文本少于 500 字符，程序会提示换成可复制文本 PDF。
- 模型必须返回固定 JSON schema，每个字段包含 `value` 和 `evidence`。
- 如果模型输出不合法，程序会尝试调用模型修复一次。
- `response_format` 不被某些兼容服务支持时，代码会在 HTTP 400 且错误文本包含 `response_format` 时自动重试。
- 不要编造论文未明确说明的信息；缺失字段统一使用“论文未明确说明”。

## Git 注意

`.venv/`、`outputs/`、测试输出、缓存和 `.DS_Store` 已忽略。提交时主要关注源码、skill、测试、依赖和文档。
