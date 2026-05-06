# 项目文件说明与调用关系

本文档说明本项目每个文件的作用，以及它们在“读取论文 PDF -> 调用 DeepSeek -> 生成论文笔记”流程中的交互关系。

## 文件作用

| 文件/目录 | 作用 | 是否直接运行 |
|---|---|---|
| `paper_note_summarizer.py` | 项目主程序。负责读取 `.env`、解析命令行参数、抽取 PDF 文本、调用 DeepSeek/OpenAI-compatible API、校验模型 JSON、生成 DOCX/Markdown/evidence JSON。 | 是 |
| `.env.example` | DeepSeek 配置模板。复制为 `.env` 后填写真实 API key。 | 否 |
| `.env` | 本地真实配置文件，保存 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`。已被 `.gitignore` 忽略，不会提交。 | 否 |
| `requirements.txt` | Python 依赖列表，包括 `pypdf`、`python-docx`、`requests`。 | 否 |
| `README.md` | 面向用户的使用说明，包含安装、配置 DeepSeek、运行命令和输出文件说明。 | 否 |
| `AGENT.md` | 面向下次 Codex/开发者快速接手的项目记忆，记录关键文件、常用命令、实现要点和 Git 注意事项。 | 否 |
| `ARCHITECTURE.md` | 当前文件。说明文件职责、模块调用关系和流程图。 | 否 |
| `.gitignore` | 忽略本地敏感配置、虚拟环境、输出文件、缓存和论文 PDF，避免误提交。 | 否 |
| `papers/.gitkeep` | 保留 `papers/` 目录结构。真实论文 PDF 放在 `papers/` 下，但 `papers/*.pdf` 被忽略。 | 否 |
| `skills/paper-note-summarizer/SKILL.md` | Codex skill 使用说明。告诉 Codex 什么时候触发该 skill、如何运行脚本、如何检查 evidence。 | 否 |
| `skills/paper-note-summarizer/agents/openai.yaml` | skill 的 UI 元信息，包括显示名、简短描述和默认提示词。 | 否 |
| `skills/paper-note-summarizer/scripts/paper_note_summarizer.py` | skill 包装脚本。它不实现总结逻辑，只定位项目根目录主程序并通过 `runpy` 执行。 | 是 |
| `tests/test_paper_note_summarizer.py` | 单元测试。验证 schema 校验、Markdown/evidence 输出、分块页码保持和 `.env` 读取优先级。 | 是 |
| `.venv/` | 本地虚拟环境。安装项目依赖，已被忽略。 | 否 |
| `outputs/` | 程序输出目录，保存 `.docx`、`.md`、`.evidence.json`、`.summary.json`，已被忽略。 | 否 |

## 文件关系图

```mermaid
flowchart TD
    User["用户 / 命令行"] --> CLI["paper_note_summarizer.py"]
    User --> Papers["papers/*.pdf<br/>本地论文 PDF"]
    User --> Env[".env<br/>DeepSeek API 配置"]

    EnvExample[".env.example<br/>配置模板"] -.复制为.-> Env
    Requirements["requirements.txt<br/>项目依赖"] -.安装到.-> Venv[".venv/<br/>虚拟环境"]
    Venv -.运行.-> CLI

    Papers --> CLI
    Env --> CLI

    CLI --> PDFExtract["pypdf<br/>按页抽取文本"]
    CLI --> DeepSeek["DeepSeek / OpenAI-compatible<br/>/chat/completions"]
    CLI --> Schema["schema 校验与修复<br/>validate_and_normalize / repair_summary_json"]
    CLI --> Render["输出渲染<br/>DOCX / Markdown / Evidence JSON"]

    Render --> Outputs["outputs/<br/>生成结果"]

    SkillMD["skills/.../SKILL.md<br/>skill 使用说明"] --> SkillWrapper["skills/.../scripts/paper_note_summarizer.py<br/>skill 包装入口"]
    SkillYaml["skills/.../agents/openai.yaml<br/>skill UI 元信息"] --> SkillWrapper
    SkillWrapper --> CLI

    Tests["tests/test_paper_note_summarizer.py"] --> CLI
    Readme["README.md<br/>用户说明"] -.描述.-> CLI
    Agent["AGENT.md<br/>开发者/Agent 说明"] -.描述.-> CLI
    Gitignore[".gitignore"] -.忽略.-> Env
    Gitignore -.忽略.-> Venv
    Gitignore -.忽略.-> Outputs
    Gitignore -.忽略.-> Papers
```

## 主程序内部调用流程

```mermaid
flowchart TD
    Start["python paper_note_summarizer.py --pdf ... --out outputs"] --> Main["main()"]
    Main --> LoadEnv["load_env_file()<br/>读取 .env"]
    LoadEnv --> Args["build_arg_parser()<br/>解析 CLI 参数"]

    Args --> DryRun{"是否 --dry-run?"}
    DryRun -- 是 --> Sample["sample_summary()<br/>生成示例 summary"]
    DryRun -- 否 --> CheckPDF["检查 --pdf 是否存在<br/>检查 API key"]

    CheckPDF --> Extract["extract_pdf_pages()<br/>pypdf 按页抽取文本"]
    Extract --> Normalize["normalize_text()<br/>清理每页文本"]
    Normalize --> Summarize["summarize_with_model()"]

    Summarize --> Chunk["chunk_pages()<br/>按页分块"]
    Chunk --> OneChunk{"是否单 chunk?"}
    OneChunk -- 是 --> Source["pages_to_source()<br/>拼接带页码原文"]
    OneChunk -- 否 --> ChunkPrompt["chunk_extraction_prompt()<br/>生成分块证据抽取 prompt"]
    ChunkPrompt --> ChunkAPI["call_chat_completion()<br/>逐块调用模型抽证据"]
    ChunkAPI --> EvidenceNotes["汇总 chunk evidence"]

    Source --> FinalPrompt["final_summary_prompt()<br/>生成最终总结 prompt"]
    EvidenceNotes --> FinalPrompt
    FinalPrompt --> FinalAPI["call_chat_completion()<br/>调用 DeepSeek 生成 JSON"]
    FinalAPI --> Parse["parse_json_object()<br/>解析模型 JSON"]
    Parse --> Validate["validate_and_normalize()<br/>schema 校验与规范化"]

    Validate --> Valid{"校验是否通过?"}
    Valid -- 否 --> Repair["repair_summary_json()<br/>调用模型修复一次"]
    Repair --> Validate
    Valid -- 是 --> FinalSummary["规范 summary"]
    Sample --> FinalSummary

    FinalSummary --> Stem["safe_stem()<br/>生成安全文件名前缀"]
    Stem --> WriteSummary["写 *.summary.json"]
    Stem --> WriteEvidence["write_evidence()<br/>写 *.evidence.json"]
    Stem --> JsonOnly{"是否 --json-only?"}
    JsonOnly -- 否 --> Markdown["render_markdown()<br/>写 *.md"]
    JsonOnly -- 否 --> Docx["render_docx()<br/>写 *.docx"]
    JsonOnly -- 是 --> Done["完成"]
    Markdown --> Done
    Docx --> Done
    WriteSummary --> Done
    WriteEvidence --> Done
```

## 数据结构关系

```mermaid
classDiagram
    class FieldSpec {
        +str group_key
        +str group_label
        +str field_key
        +str field_label
        +bool long_text
    }

    class SummaryField {
        +str value
        +Evidence evidence
    }

    class Evidence {
        +list~int~ page_refs
        +list~str~ source_quotes
        +str confidence
        +str notes
    }

    class Summary {
        +paper_overview
        +paper_content
        +experiments
        +paper_highlights
        +paper_summary
    }

    FieldSpec --> Summary : 决定字段路径和输出顺序
    Summary --> SummaryField : 每个字段
    SummaryField --> Evidence : 原文依据
```

## 运行时输入输出

```mermaid
flowchart LR
    PDF["papers/xxx.pdf"] --> Program["paper_note_summarizer.py"]
    DotEnv[".env<br/>DEEPSEEK_API_KEY"] --> Program
    Program --> Docx["outputs/xxx.docx<br/>Word 表格笔记"]
    Program --> Md["outputs/xxx.md<br/>Markdown 笔记"]
    Program --> Evidence["outputs/xxx.evidence.json<br/>证据页码与短引文"]
    Program --> Summary["outputs/xxx.summary.json<br/>完整结构化结果"]
```

## 典型调用方式

普通 CLI 调用：

```bash
.venv/bin/python paper_note_summarizer.py \
  --pdf "papers/论文文件名.pdf" \
  --out outputs
```

skill 包装调用：

```bash
.venv/bin/python skills/paper-note-summarizer/scripts/paper_note_summarizer.py \
  --pdf "papers/论文文件名.pdf" \
  --out outputs
```

两种方式最终都会执行项目根目录的 `paper_note_summarizer.py`，因此输出行为一致。
