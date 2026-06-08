from __future__ import annotations

from pathlib import Path

from .models import ParsedReport
from .ocr import extract_ocr_text
from .pdf_text import extract_pdf_text, text_is_usable
from .templates import extract_report, load_templates, select_template


class ParseError(RuntimeError):
    pass


def parse_pdf(path: Path, template_config: Path, tmp_dir: Path | None = None) -> ParsedReport:
    text = extract_pdf_text(path)
    text_source = "pdf_text"
    if not text_is_usable(text):
        text = extract_ocr_text(path, tmp_dir=tmp_dir)
        text_source = "ocr"

    if not text_is_usable(text):
        raise ParseError("PDF 文本为空或 OCR 结果不可用")

    templates = load_templates(template_config)
    template = select_template(text, templates)
    if template is None:
        raise ParseError("未匹配到可用模板，请在 config/templates.yaml 新增规则")

    report = extract_report(text=text, template=template, text_source=text_source)
    if not report.report_no and not report.sample_name:
        raise ParseError("已匹配模板，但未提取到报告编号或样品名称")
    return report
