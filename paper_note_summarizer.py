#!/usr/bin/env python3
"""Summarize academic PDFs into Chinese paper-note tables."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"
MISSING_TEXT = "论文未明确说明"
SCAN_TEXT_THRESHOLD = 500
CHUNK_CHAR_LIMIT = 26000


def load_env_file(env_path: Path = Path(".env")) -> None:
    """Load simple KEY=VALUE pairs from .env without overriding real env vars."""
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclasses.dataclass(frozen=True)
class FieldSpec:
    group_key: str
    group_label: str
    field_key: str
    field_label: str
    long_text: bool = False


FIELD_SPECS: tuple[FieldSpec, ...] = (
    FieldSpec("paper_overview", "论文概述", "title", "论文题目"),
    FieldSpec("paper_overview", "论文概述", "authors", "作者"),
    FieldSpec("paper_overview", "论文概述", "venue", "期刊/会议（如 ICLR2025）"),
    FieldSpec("paper_overview", "论文概述", "pdf_link", "论文 PDF 链接"),
    FieldSpec("paper_overview", "论文概述", "code_link", "论文代码（github 地址）"),
    FieldSpec("paper_content", "论文内容", "main_idea", "主要思想"),
    FieldSpec("paper_content", "论文内容", "problem", "所解决的问题"),
    FieldSpec(
        "paper_content",
        "论文内容",
        "main_content",
        "（1）论文的主要内容（这里介绍论文框架图以及框架图中的各个模块）",
        True,
    ),
    FieldSpec(
        "paper_content",
        "论文内容",
        "method_steps",
        "（2）文章所提方法的核心步骤（这里介绍推荐或者预测的主要流程）",
        True,
    ),
    FieldSpec(
        "paper_content",
        "论文内容",
        "additional_details",
        "其他补充（这里可以介绍方法部分其他细节，如其他重要图片的解释说明）",
        True,
    ),
    FieldSpec("experiments", "实验", "datasets", "数据集"),
    FieldSpec("experiments", "实验", "baselines", "对比方法"),
    FieldSpec("experiments", "实验", "metrics", "评价指标"),
    FieldSpec(
        "experiments",
        "实验",
        "results_conclusions",
        "实验结果及结论（这里介绍每个实验以及对应的结论）",
        True,
    ),
    FieldSpec("paper_highlights", "论文亮点", "highlights", "论文亮点", True),
    FieldSpec("paper_summary", "论文总结", "summary", "（个人理解，简要概括）", True),
)


def normalize_text(text: str) -> str:
    """Normalize extracted PDF text without changing technical terms."""
    text = text.replace("\x00", "")
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def extract_pdf_pages(pdf_path: Path) -> list[dict[str, Any]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise SystemExit("缺少依赖 pypdf。请先运行：pip install -r requirements.txt") from exc

    reader = PdfReader(str(pdf_path))
    pages: list[dict[str, Any]] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text = normalize_text(text)
        if text:
            pages.append({"page_number": index, "text": text})

    total_chars = sum(len(page["text"]) for page in pages)
    if total_chars < SCAN_TEXT_THRESHOLD:
        raise SystemExit("PDF 可抽取文本过少，可能是扫描版 PDF。v1 暂不做 OCR，请换成可复制文本的 PDF。")
    return pages


def pages_to_source(pages: Iterable[dict[str, Any]]) -> str:
    return "\n\n".join(f"[Page {page['page_number']}]\n{page['text']}" for page in pages)


def chunk_pages(pages: list[dict[str, Any]], limit: int = CHUNK_CHAR_LIMIT) -> list[list[dict[str, Any]]]:
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_len = 0
    for page in pages:
        page_len = len(page["text"]) + 32
        if current and current_len + page_len > limit:
            chunks.append(current)
            current = []
            current_len = 0
        current.append(page)
        current_len += page_len
    if current:
        chunks.append(current)
    return chunks


def schema_template() -> dict[str, Any]:
    template: dict[str, Any] = {}
    for spec in FIELD_SPECS:
        template.setdefault(spec.group_key, {})
        template[spec.group_key][spec.field_key] = {
            "value": "",
            "evidence": {
                "page_refs": [],
                "source_quotes": [],
                "confidence": "low",
                "notes": "",
            },
        }
    return template


def system_prompt() -> str:
    return (
        "你是一名严谨的中文学术论文阅读助手。只能依据用户提供的论文原文总结，"
        "不得编造论文没有明确说明的信息。若没有证据，字段 value 必须写"
        f"“{MISSING_TEXT}”。所有输出必须是合法 JSON，不要输出 Markdown。"
    )


def final_summary_prompt(
    source_text: str,
    title_hint: str | None = None,
    pdf_link: str | None = None,
    code_link: str | None = None,
) -> str:
    template = json.dumps(schema_template(), ensure_ascii=False, indent=2)
    hints = {
        "title_hint": title_hint or "",
        "user_supplied_pdf_link": pdf_link or "",
        "user_supplied_code_link": code_link or "",
    }
    return f"""
请根据论文原文填写“论文笔记”JSON。

要求：
1. 严格保持 JSON 结构和字段名，不要新增顶层字段。
2. value 使用中文，学术严谨，优先概括方法、实验和结论的可验证事实。
3. evidence.page_refs 填相关页码整数列表。
4. evidence.source_quotes 只放短原文片段，每条不超过 40 个英文词或 80 个中文字符。
5. evidence.confidence 只能是 high、medium、low。
6. evidence.notes 说明证据不足、字段缺失或推断边界。
7. PDF/代码链接仅在用户提供或论文原文明确出现时填写，否则写“{MISSING_TEXT}”。
8. 实验结果及结论必须对应论文中的表格、指标、消融实验或文字结论。

用户补充信息：
{json.dumps(hints, ensure_ascii=False, indent=2)}

必须返回如下 JSON 结构：
{template}

论文原文：
{source_text}
""".strip()


def chunk_extraction_prompt(source_text: str) -> str:
    return f"""
请从以下论文片段抽取后续总结可能需要的证据线索。只返回 JSON 对象，格式为：
{{"items": [{{"topic": "...", "claim": "...", "page_refs": [1], "source_quotes": ["..."]}}]}}
不要做最终总结，不要编造片段中没有的信息。

论文片段：
{source_text}
""".strip()


def call_chat_completion(
    messages: list[dict[str, str]],
    *,
    api_key: str,
    base_url: str,
    model: str,
    temperature: float = 0.1,
    timeout: int = 180,
) -> str:
    try:
        import requests
    except ImportError as exc:
        raise SystemExit("缺少依赖 requests。请先运行：pip install -r requirements.txt") from exc

    endpoint = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    response = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
    if response.status_code == 400 and "response_format" in response.text:
        payload.pop("response_format", None)
        response = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
    if response.status_code >= 400:
        raise SystemExit(f"模型接口请求失败：HTTP {response.status_code}\n{response.text}")
    data = response.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        preview = json.dumps(data, ensure_ascii=False)[:1000]
        raise SystemExit(f"模型接口返回格式异常：{preview}") from exc


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    if not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("模型输出中未找到 JSON 对象")
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def validate_and_normalize(data: dict[str, Any]) -> dict[str, Any]:
    normalized = schema_template()
    errors: list[str] = []
    for spec in FIELD_SPECS:
        raw = data.get(spec.group_key, {}).get(spec.field_key)
        path = f"{spec.group_key}.{spec.field_key}"
        if not isinstance(raw, dict):
            errors.append(f"{path} must be an object")
            continue

        value = raw.get("value", MISSING_TEXT)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{path}.value must be a non-empty string")
            value = MISSING_TEXT

        evidence = raw.get("evidence", {})
        if not isinstance(evidence, dict):
            evidence = {}
            errors.append(f"{path}.evidence must be an object")

        page_refs = evidence.get("page_refs", [])
        if not isinstance(page_refs, list):
            page_refs = []
            errors.append(f"{path}.evidence.page_refs must be a list")
        page_refs = [int(page) for page in page_refs if isinstance(page, int) or str(page).isdigit()]

        source_quotes = evidence.get("source_quotes", [])
        if not isinstance(source_quotes, list):
            source_quotes = []
            errors.append(f"{path}.evidence.source_quotes must be a list")
        source_quotes = [str(quote).strip() for quote in source_quotes if str(quote).strip()]

        confidence = evidence.get("confidence", "low")
        if confidence not in {"high", "medium", "low"}:
            confidence = "low"
            errors.append(f"{path}.evidence.confidence must be high, medium, or low")

        notes = evidence.get("notes", "")
        normalized[spec.group_key][spec.field_key] = {
            "value": value.strip(),
            "evidence": {
                "page_refs": sorted(set(page_refs)),
                "source_quotes": source_quotes[:5],
                "confidence": confidence,
                "notes": notes.strip() if isinstance(notes, str) else str(notes),
            },
        }

    if errors:
        raise ValueError("; ".join(errors))
    return normalized


def repair_summary_json(
    invalid_json_text: str,
    validation_error: str,
    *,
    api_key: str,
    base_url: str,
    model: str,
) -> dict[str, Any]:
    prompt = f"""
下面的 JSON 不符合目标 schema。请修复为合法 JSON，并严格使用目标字段。

校验错误：
{validation_error}

目标 schema：
{json.dumps(schema_template(), ensure_ascii=False, indent=2)}

待修复内容：
{invalid_json_text}
""".strip()
    repaired = call_chat_completion(
        [{"role": "system", "content": system_prompt()}, {"role": "user", "content": prompt}],
        api_key=api_key,
        base_url=base_url,
        model=model,
    )
    return validate_and_normalize(parse_json_object(repaired))


def summarize_with_model(
    pages: list[dict[str, Any]],
    *,
    api_key: str,
    base_url: str,
    model: str,
    title_hint: str | None,
    pdf_link: str | None,
    code_link: str | None,
) -> dict[str, Any]:
    chunks = chunk_pages(pages)
    if len(chunks) == 1:
        source_text = pages_to_source(chunks[0])
    else:
        evidence_notes = []
        for index, chunk in enumerate(chunks, start=1):
            content = call_chat_completion(
                [
                    {"role": "system", "content": system_prompt()},
                    {"role": "user", "content": chunk_extraction_prompt(pages_to_source(chunk))},
                ],
                api_key=api_key,
                base_url=base_url,
                model=model,
            )
            evidence_notes.append(f"[Chunk {index} evidence]\n{content}")
        source_text = "\n\n".join(evidence_notes)

    raw = call_chat_completion(
        [
            {"role": "system", "content": system_prompt()},
            {
                "role": "user",
                "content": final_summary_prompt(
                    source_text,
                    title_hint=title_hint,
                    pdf_link=pdf_link,
                    code_link=code_link,
                ),
            },
        ],
        api_key=api_key,
        base_url=base_url,
        model=model,
    )
    try:
        return validate_and_normalize(parse_json_object(raw))
    except Exception as exc:
        return repair_summary_json(raw, str(exc), api_key=api_key, base_url=base_url, model=model)


def sample_summary(title_hint: str | None = None) -> dict[str, Any]:
    data = schema_template()
    values = {
        ("paper_overview", "title"): title_hint or "Dry-run 示例论文",
        ("paper_overview", "authors"): "示例作者 A；示例作者 B",
        ("paper_overview", "venue"): "示例会议 2026",
        ("paper_overview", "pdf_link"): MISSING_TEXT,
        ("paper_overview", "code_link"): MISSING_TEXT,
        ("paper_content", "main_idea"): "该示例展示论文笔记工具的结构化输出格式。",
        ("paper_content", "problem"): "用于验证无模型调用时的渲染链路。",
        ("paper_content", "main_content"): "工具将论文信息拆分为论文概述、论文内容、实验、亮点和总结等部分。",
        ("paper_content", "method_steps"): "抽取 PDF 文本；调用模型生成结构化 JSON；校验 schema；渲染 DOCX、Markdown 和 evidence 文件。",
        ("paper_content", "additional_details"): "真实运行时此处应包含论文方法细节或关键图表解释。",
        ("experiments", "datasets"): "示例数据集",
        ("experiments", "baselines"): "示例对比方法",
        ("experiments", "metrics"): "示例评价指标",
        ("experiments", "results_conclusions"): "示例结果说明输出链路正常；真实运行时必须对应论文实验。",
        ("paper_highlights", "highlights"): "结构化、可核查、便于复用。",
        ("paper_summary", "summary"): "这是 dry-run 示例，不代表真实论文内容。",
    }
    for (group, field), value in values.items():
        data[group][field] = {
            "value": value,
            "evidence": {
                "page_refs": [1],
                "source_quotes": ["dry-run sample"],
                "confidence": "low",
                "notes": "这是 dry-run 样例数据，仅用于测试渲染。",
            },
        }
    return data


def value_of(summary: dict[str, Any], group: str, field: str) -> str:
    return summary[group][field]["value"]


def render_markdown(summary: dict[str, Any], output_path: Path) -> None:
    lines = ["# 论文笔记", ""]
    current_group = None
    for spec in FIELD_SPECS:
        if spec.group_label != current_group:
            current_group = spec.group_label
            lines.extend([f"## {current_group}", ""])
        lines.extend([f"### {spec.field_label}", "", value_of(summary, spec.group_key, spec.field_key), ""])
    output_path.write_text("\n".join(lines), encoding="utf-8")


def set_cell_text(cell: Any, text: str, *, bold: bool = False, align_center: bool = False) -> None:
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Pt

    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if align_center else WD_ALIGN_PARAGRAPH.LEFT
    run = paragraph.add_run(text)
    run.bold = bold
    run.font.name = "SimSun"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "SimSun")
    run.font.size = Pt(14 if bold else 11)


def set_table_borders(table: Any) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    borders = table._tbl.tblPr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        table._tbl.tblPr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = borders.find(qn(f"w:{edge}"))
        if element is None:
            element = OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "8")
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), "000000")


def render_docx(summary: dict[str, Any], output_path: Path) -> None:
    try:
        from docx import Document
        from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
        from docx.shared import Cm
    except ImportError as exc:
        raise SystemExit("缺少依赖 python-docx。请先运行：pip install -r requirements.txt") from exc

    document = Document()
    section = document.sections[0]
    section.top_margin = Cm(1.2)
    section.bottom_margin = Cm(1.2)
    section.left_margin = Cm(1.2)
    section.right_margin = Cm(1.2)

    table = document.add_table(rows=1, cols=3)
    table.autofit = True
    set_table_borders(table)
    title_cell = table.rows[0].cells[0].merge(table.rows[0].cells[2])
    set_cell_text(title_cell, "论文笔记", bold=True, align_center=True)

    rows_by_group: dict[str, list[Any]] = {}
    for spec in FIELD_SPECS:
        row = table.add_row()
        rows_by_group.setdefault(spec.group_key, []).append(row)
        row.cells[0].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        row.cells[1].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        row.cells[2].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_cell_text(row.cells[1], spec.field_label, align_center=not spec.long_text)
        set_cell_text(row.cells[2], value_of(summary, spec.group_key, spec.field_key))

    for group_key, rows in rows_by_group.items():
        merged = rows[0].cells[0]
        for row in rows[1:]:
            merged = merged.merge(row.cells[0])
        group_label = next(spec.group_label for spec in FIELD_SPECS if spec.group_key == group_key)
        set_cell_text(merged, group_label, align_center=True)
        merged.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

    for row in table.rows:
        row.cells[0].width = Cm(3.0)
        row.cells[1].width = Cm(7.0)
        row.cells[2].width = Cm(16.0)

    document.save(output_path)


def write_evidence(summary: dict[str, Any], output_path: Path) -> None:
    evidence: dict[str, Any] = {}
    for spec in FIELD_SPECS:
        evidence.setdefault(spec.group_key, {})
        evidence[spec.group_key][spec.field_key] = summary[spec.group_key][spec.field_key]["evidence"]
    output_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_stem(pdf_path: Path | None, title_hint: str | None) -> str:
    raw = title_hint or (pdf_path.stem if pdf_path else "paper_note")
    stem = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", raw, flags=re.UNICODE).strip("._")
    return stem or "paper_note"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="自动总结论文 PDF，生成 DOCX、Markdown 和 evidence JSON。")
    parser.add_argument("--pdf", type=Path, help="论文 PDF 路径。")
    parser.add_argument("--out", type=Path, default=Path("outputs"), help="输出目录。")
    parser.add_argument("--title-hint", help="可选论文题目提示，用于输出文件名和模型辅助。")
    parser.add_argument("--pdf-link", help="可选论文 PDF URL；若不提供且论文未写明，则输出“论文未明确说明”。")
    parser.add_argument("--code-link", help="可选代码仓库 URL；若不提供且论文未写明，则输出“论文未明确说明”。")
    parser.add_argument(
        "--api-key",
        default=os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY"),
        help="OpenAI 兼容 API key；优先读取 DEEPSEEK_API_KEY，其次 OPENAI_API_KEY。",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("DEEPSEEK_BASE_URL") or os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL),
        help="OpenAI 兼容 API base URL；默认 DeepSeek。",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("DEEPSEEK_MODEL") or os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
        help="模型名称；默认 deepseek-chat。",
    )
    parser.add_argument("--dry-run", action="store_true", help="不读取 PDF、不调用模型，生成示例输出以验证渲染链路。")
    parser.add_argument("--json-only", action="store_true", help="只写 summary JSON 和 evidence JSON，不生成 DOCX/MD。")
    return parser


def main(argv: list[str] | None = None) -> int:
    load_env_file()
    args = build_arg_parser().parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        summary = sample_summary(args.title_hint)
        pdf_path = args.pdf
    else:
        if not args.pdf:
            raise SystemExit("请提供 --pdf，或使用 --dry-run 测试输出链路。")
        if not args.pdf.exists():
            raise SystemExit(f"PDF 文件不存在：{args.pdf}")
        if not args.api_key:
            raise SystemExit("缺少 API key。请设置 DEEPSEEK_API_KEY / OPENAI_API_KEY，或使用 --api-key。")
        pdf_path = args.pdf
        pages = extract_pdf_pages(args.pdf)
        summary = summarize_with_model(
            pages,
            api_key=args.api_key,
            base_url=args.base_url,
            model=args.model,
            title_hint=args.title_hint,
            pdf_link=args.pdf_link,
            code_link=args.code_link,
        )

    summary = validate_and_normalize(summary)
    stem = safe_stem(pdf_path, args.title_hint)
    summary_path = args.out / f"{stem}.summary.json"
    evidence_path = args.out / f"{stem}.evidence.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_evidence(summary, evidence_path)

    if not args.json_only:
        md_path = args.out / f"{stem}.md"
        docx_path = args.out / f"{stem}.docx"
        render_markdown(summary, md_path)
        render_docx(summary, docx_path)
        print(f"已生成：\n- {docx_path}\n- {md_path}\n- {evidence_path}\n- {summary_path}")
    else:
        print(f"已生成：\n- {evidence_path}\n- {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
