from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict
from pathlib import Path

from .models import ParsedReport
from .normalization import normalize_date, normalize_date_range


def export_report(report: ParsedReport, pdf_path: Path, output_root: Path) -> list[Path]:
    folder = output_root / _folder_name(report)
    folder.mkdir(parents=True, exist_ok=True)
    base = _safe_name(report.report_no or pdf_path.stem)

    json_path = folder / f"{base}.json"
    md_path = folder / f"{base}.md"
    main_csv_path = folder / f"{base}_main.csv"
    items_csv_path = folder / f"{base}_items.csv"

    payload = asdict(report)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    main_fields = _main_fields(report, pdf_path)
    md_path.write_text(_render_markdown(report, main_fields), encoding="utf-8")
    _write_main_csv(main_csv_path, main_fields, report)
    _write_items_csv(items_csv_path, report)
    return [md_path, json_path, main_csv_path, items_csv_path]


def _folder_name(report: ParsedReport) -> str:
    if report.template_name and report.template_name.startswith("sgs"):
        return "SGS"
    if report.template_name and report.template_name.startswith("cti"):
        return "华测"
    if report.template_name and report.template_name.startswith("merieux"):
        return "梅里埃"
    if report.template_name and report.template_name.startswith("intertek"):
        return "天祥"
    return "未知模板"


def _safe_name(value: str) -> str:
    value = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", value.strip())
    return value.strip("_") or "report"


def _main_fields(report: ParsedReport, pdf_path: Path) -> dict[str, object]:
    extra = report.extra_fields
    return {
        "PDF文件名": pdf_path.name,
        "报告编号": report.report_no,
        "替代报告编号": extra.get("替代报告编号"),
        "样品名称": report.sample_name,
        "样品编号": _first_extra(extra, "样品编号", "SGS样品ID", "CTI样品编号"),
        "样品批号": _first_extra(extra, "样品批号", "批号"),
        "样品规格": _first_extra(extra, "样品规格", "规格型号"),
        "样品数量": _first_extra(extra, "样品数量", "样品量"),
        "样品状态": _first_extra(extra, "样品状态", "样品等级或状态"),
        "样品来源": extra.get("样品来源"),
        "客户名称": report.client,
        "客户地址": _first_extra(extra, "客户地址", "委托单位地址"),
        "检测机构": report.lab,
        "检测机构地址": extra.get("检测机构地址"),
        "报告日期": normalize_date(report.report_date),
        "发布日期": normalize_date(extra.get("发布日期")),
        "签发日期": normalize_date(extra.get("签发日期")),
        "样品接收日期": normalize_date(_first_extra(extra, "样品接收日期", "到样日期", "到样时间")),
        "检测开始日期": normalize_date(extra.get("检测开始日期")),
        "检测结束日期": normalize_date(extra.get("检测结束日期")),
        "检测周期": normalize_date_range(_first_extra(extra, "检测周期", "样品检测日期")),
        "生产日期": normalize_date(extra.get("生产日期")),
        "生产商": _first_extra(extra, "生产商", "生产单位"),
        "检验类别": _first_extra(extra, "检验类别", "检测类型"),
        "检测项目概述": extra.get("检测项目概述"),
        "判定标准": extra.get("判定标准"),
        "报告结论": report.conclusion,
        "备注": _json_if_needed(extra.get("备注")),
        "声明": _json_if_needed(extra.get("声明")),
        "解析模板": f"{report.template_name}@{report.template_version}",
        "文本来源": report.text_source,
        "检测项目数量": len(report.items),
    }


def _render_markdown(report: ParsedReport, main_fields: dict[str, object]) -> str:
    lines = [
        "# 检测报告解析结果",
        "",
        "## 检测报告主表字段",
        "",
        "| 字段 | 值 |",
        "|---|---|",
    ]
    for key, value in main_fields.items():
        lines.append(f"| {key} | {_md_cell(value)} |")
    lines += [
        "",
        "## 其他信息JSON",
        "",
        "```json",
        json.dumps(report.extra_fields, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 检测项目明细表",
        "",
        "| 序号 | 检测项目 | 单位 | 检测方法 | 检测结果 | 定量限/检出限 | 限值 | 单项结论 |",
        "|---:|---|---|---|---:|---:|---|---|",
    ]
    for index, item in enumerate(report.items, 1):
        loq = item.extra_fields.get("定量限") or item.extra_fields.get("定量限/检出限") or item.extra_fields.get("报告检出限")
        row = [index, item.name, item.unit, item.method, item.value, loq, item.standard, item.conclusion]
        lines.append("| " + " | ".join(_md_cell(value) for value in row) + " |")
    lines += ["", "## 原文文本", "", "```text", report.raw_text, "```"]
    return "\n".join(lines)


def _write_main_csv(path: Path, main_fields: dict[str, object], report: ParsedReport) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(main_fields.keys()) + ["其他信息JSON"])
        writer.writeheader()
        writer.writerow({**main_fields, "其他信息JSON": json.dumps(report.extra_fields, ensure_ascii=False)})


def _write_items_csv(path: Path, report: ParsedReport) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "关联报告",
                "序号",
                "检测项目",
                "单位",
                "检测方法",
                "检测结果",
                "定量限/检出限",
                "限值",
                "单项结论",
                "明细额外信息JSON",
                "来源文本片段",
            ],
        )
        writer.writeheader()
        for index, item in enumerate(report.items, 1):
            loq = item.extra_fields.get("定量限") or item.extra_fields.get("定量限/检出限") or item.extra_fields.get("报告检出限")
            writer.writerow(
                {
                    "关联报告": report.report_no,
                    "序号": index,
                    "检测项目": item.name,
                    "单位": item.unit,
                    "检测方法": item.method,
                    "检测结果": item.value,
                    "定量限/检出限": loq,
                    "限值": item.standard,
                    "单项结论": item.conclusion,
                    "明细额外信息JSON": json.dumps(item.extra_fields, ensure_ascii=False),
                    "来源文本片段": item.source_text,
                }
            )


def _md_cell(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", "<br>")


def _first_extra(extra: dict[str, object], *keys: str) -> object:
    for key in keys:
        value = extra.get(key)
        if value not in (None, "", []):
            return value
    return None


def _json_if_needed(value: object) -> object:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value
