from __future__ import annotations

from pathlib import Path
from typing import Any

from .exporter import export_report
from .output_importer import import_output_to_feishu
from .parser import parse_pdf
from .settings import Settings


def process_pdf_folder(
    input_dir: Path,
    output_dir: Path,
    settings: Settings,
    import_to_feishu: bool = False,
    allow_partial: bool = False,
) -> dict[str, Any]:
    pdf_paths = sorted(path for path in input_dir.rglob("*") if path.is_file() and path.suffix.lower() == ".pdf")
    if not pdf_paths:
        raise RuntimeError(f"未找到 PDF 文件：{input_dir}")

    successes: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for pdf_path in pdf_paths:
        try:
            report = parse_pdf(pdf_path, settings.template_config, tmp_dir=settings.tmp_dir)
            exported_paths = export_report(report, pdf_path, output_dir)
            successes.append(
                {
                    "pdf": str(pdf_path),
                    "report_no": report.report_no,
                    "template": report.template_name,
                    "items": len(report.items),
                    "outputs": [str(path) for path in exported_paths],
                }
            )
        except Exception as exc:
            failures.append({"pdf": str(pdf_path), "error": str(exc)})

    if failures and not allow_partial:
        return {
            "status": "failed",
            "message": "存在解析失败的 PDF，未执行飞书导入。可加 --allow-partial 导入已成功解析的报告。",
            "successes": successes,
            "failures": failures,
        }

    result: dict[str, Any] = {
        "status": "ok" if not failures else "partial",
        "successes": successes,
        "failures": failures,
    }
    if import_to_feishu:
        result["feishu"] = import_output_to_feishu(output_dir, settings)
    return result
