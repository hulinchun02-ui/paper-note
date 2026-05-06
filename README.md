# Paper Note Summarizer

将学术论文 PDF 自动总结为结构化的中文「论文笔记」，支持 DOCX、Markdown 和 Evidence JSON 三种输出格式。

## 功能特性

- **PDF 文本抽取**：使用 `pypdf` 提取论文原文，按页码组织
- **大文本分块**：自动将长论文切分为多个 chunk，避免超出模型上下文限制
- **结构化输出**：生成包含论文概述、论文内容、实验、论文亮点、论文总结五大板块的笔记
- **证据溯源**：每个字段记录页码引用、原文摘录、可信度评级和备注
- **多格式导出**：支持 DOCX 可编辑表格、Markdown 和 JSON 三种输出
- **DeepSeek 默认配置**：默认使用 DeepSeek 的 OpenAI-compatible 接口，同时保留 `OPENAI_*` 兼容环境变量
- **Schema 校验**：对模型输出进行严格的字段校验和修复
- **Dry-run 模式**：无需 PDF 和 API Key 即可验证渲染链路

## 安装

```bash
pip install -r requirements.txt
```

依赖包括：
- `pypdf>=4.0.0` — PDF 文本抽取
- `python-docx>=1.1.0` — DOCX 文件生成
- `requests>=2.31.0` — API 调用

## 快速开始

### DeepSeek API 配置

推荐复制示例文件并填写真实 key：

```bash
cp .env.example .env
```

然后编辑 `.env`：

```bash
DEEPSEEK_API_KEY=你的DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

`.env` 已加入 `.gitignore`，不会提交到 GitHub。

也可以直接用终端环境变量：

```bash
export DEEPSEEK_API_KEY="your-api-key"
export DEEPSEEK_BASE_URL="https://api.deepseek.com"  # 可选，默认 DeepSeek
export DEEPSEEK_MODEL="deepseek-v4-flash"            # 可选，默认 deepseek-v4-flash
```

也可继续使用 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL` 接入其他 OpenAI-compatible 服务。CLI 参数优先级高于环境变量，真实环境变量优先级高于 `.env`。

### 基本用法

```bash
.venv/bin/python paper_note_summarizer.py --pdf /path/to/paper.pdf --out outputs
```

### 完整参数示例

```bash
.venv/bin/python paper_note_summarizer.py \
    --pdf paper.pdf \
    --out outputs \
    --title-hint "论文标题提示" \
    --pdf-link "https://arxiv.org/pdf/xxx" \
    --code-link "https://github.com/xxx"
```

### Dry-run 模式

不调用 API，生成示例输出验证渲染链路：

```bash
.venv/bin/python paper_note_summarizer.py --dry-run --out outputs
```

### 仅生成 JSON

跳过 DOCX 和 Markdown 生成：

```bash
.venv/bin/python paper_note_summarizer.py --pdf paper.pdf --json-only --out outputs
```

## 输出文件

以 `paper.pdf` 为例，输出目录将包含：

| 文件 | 说明 |
|------|------|
| `paper.docx` | 可编辑的论文笔记表格 |
| `paper.md` | Markdown 格式笔记 |
| `paper.evidence.json` | 每个字段的证据信息（页码、原文摘录、可信度） |
| `paper.summary.json` | 完整的结构化笔记 JSON |

## 输出字段说明

### 论文概述
- 论文题目
- 作者
- 期刊/会议（如 ICLR2025）
- 论文 PDF 链接
- 论文代码（GitHub 地址）

### 论文内容
- 主要思想
- 所解决的问题
- 论文主要内容（框架图及模块介绍）
- 方法的核心步骤
- 其他补充

### 实验
- 数据集
- 对比方法
- 评价指标
- 实验结果及结论

### 论文亮点

### 论文总结（个人理解）

## 项目结构

```
paper-note/
├── paper_note_summarizer.py   # 主程序
├── requirements.txt           # 依赖
├── tests/
│   └── test_paper_note_summarizer.py
├── skills/
│   └── paper-note-summarizer/
│       ├── SKILL.md           # Skill 定义文档
│       ├── agents/
│       │   └── openai.yaml
│       └── scripts/
│           └── paper_note_summarizer.py
└── outputs_test/              # 测试输出示例
```

## 作为 Skill 使用

本项目可作为 Trae IDE 的 Skill 使用，详见 [skills/paper-note-summarizer/SKILL.md](skills/paper-note-summarizer/SKILL.md)。

## 架构关系图

每个文件的作用、调用链和 Mermaid 关系图见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 运行测试

```bash
.venv/bin/python -m unittest discover -s tests
```

## 注意事项

- 仅支持可复制文本的 PDF，扫描版 PDF 暂不支持 OCR
- 若 PDF 可抽取文本少于 500 字符，将提示错误
- 模型输出不符合 Schema 时，程序会自动尝试修复
- evidence.json 中的 `confidence` 字段表示该字段的可信度（high/medium/low），需人工复核
