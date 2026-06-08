from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .models import ParsedReport, ReportItem


@dataclass(frozen=True)
class TemplateRule:
    name: str
    version: str
    enabled: bool
    lab: str | None
    keywords: list[str]
    fields: dict[str, list[str]]
    item_patterns: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TemplateRule":
        return cls(
            name=data["name"],
            version=str(data.get("version", "1.0")),
            enabled=bool(data.get("enabled", True)),
            lab=data.get("lab"),
            keywords=list(data.get("keywords", [])),
            fields={key: list(value or []) for key, value in (data.get("fields") or {}).items()},
            item_patterns=list((data.get("items") or {}).get("line_patterns") or []),
        )

    def score(self, text: str) -> int:
        return sum(1 for keyword in self.keywords if keyword in text)


def load_templates(path: Path) -> list[TemplateRule]:
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    return [TemplateRule.from_dict(item) for item in data.get("templates", []) if item.get("enabled", True)]


def select_template(text: str, templates: list[TemplateRule]) -> TemplateRule | None:
    scored = [(template.score(text), template) for template in templates]
    scored = [(score, template) for score, template in scored if score > 0]
    if not scored:
        return None
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[0][1]


def extract_report(text: str, template: TemplateRule, text_source: str) -> ParsedReport:
    values = {field: _first_match(patterns, text) for field, patterns in template.fields.items()}
    if template.name == "sgs_cn_inspection_report":
        items = _extract_sgs_items(text)
        extra_fields = _extract_sgs_extra_fields(text)
    elif template.name == "cti_cn_inspection_report":
        items = _extract_cti_items(text)
        extra_fields = _extract_cti_extra_fields(text)
        values["sample_name"] = _clean_multiline(values.get("sample_name"))
        values["conclusion"] = _clean_multiline(values.get("conclusion"))
    elif template.name == "merieux_cn_analysis_certificate":
        items = _extract_merieux_items(text)
        extra_fields = _extract_merieux_extra_fields(text)
    elif template.name == "intertek_cn_inspection_report":
        items = _extract_intertek_items(text)
        extra_fields = _extract_intertek_extra_fields(text)
    else:
        items = _extract_items(text, template.item_patterns)
        extra_fields = {}
    return ParsedReport(
        report_no=values.get("report_no"),
        sample_name=values.get("sample_name"),
        lab=values.get("lab") or template.lab,
        client=values.get("client"),
        report_date=values.get("report_date"),
        conclusion=values.get("conclusion"),
        template_name=template.name,
        template_version=template.version,
        text_source=text_source,
        raw_text=text,
        extra_fields=extra_fields,
        items=items,
    )


def _first_match(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.MULTILINE | re.S)
        if match:
            return match.group(1).strip()
    return None


def _clean_multiline(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(line.strip() for line in value.splitlines() if line.strip())


def _extract_items(text: str, patterns: list[str]) -> list[ReportItem]:
    items: list[ReportItem] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        for pattern in patterns:
            match = re.search(pattern, line)
            if not match:
                continue
            groups = [group.strip() if group else None for group in match.groups()]
            items.append(
                ReportItem(
                    name=groups[0] or "",
                    value=groups[1] if len(groups) > 1 else None,
                    unit=groups[2] if len(groups) > 2 else None,
                    standard=groups[3] if len(groups) > 3 else None,
                    conclusion=groups[4] if len(groups) > 4 else None,
                    source_text=line,
                )
            )
            break
    return items


def _extract_sgs_extra_fields(text: str) -> dict[str, Any]:
    fields = {
        "客户地址": _label_value(text, "客户地址"),
        "样品批号": _label_value(text, "样品批号"),
        "生产日期": _label_value(text, "生产日期"),
        "生产商": _label_value(text, "生产商"),
        "样品接收日期": _label_value(text, "样品接收日期"),
        "检测周期": _label_value(text, "检测周期"),
        "检测要求": _label_value(text, "检测要求"),
        "检测方法说明": _label_value(text, "检测方法"),
        "检测结果说明": _label_value(text, "检测结果"),
        "检测样品描述": _extract_sgs_sample_description(text),
        "备注": _extract_sgs_notes(text),
    }
    return {key: value for key, value in fields.items() if value not in (None, "", [])}


def _label_value(text: str, label: str) -> str | None:
    pattern = rf"{re.escape(label)}[:：]?[\t ]*\n([^\n\r]+)"
    match = re.search(pattern, text)
    return match.group(1).strip() if match else None


def _extract_sgs_sample_description(text: str) -> dict[str, str] | None:
    match = re.search(
        r"样品编号\s*\nSGS 样品ID\s*\n样品描述\s*\n([^\n]+)\n([^\n]+)\n([^\n]+)",
        text,
    )
    if not match:
        return None
    return {
        "样品编号": match.group(1).strip(),
        "SGS样品ID": match.group(2).strip(),
        "样品描述": match.group(3).strip(),
    }


def _extract_sgs_notes(text: str) -> list[str]:
    notes: list[str] = []
    for match in re.finditer(r"备注[:：]\s*\n(.+?)(?=\n--- page|\n样品照片|\n注意事项|\n\*\*\*结束\*\*\*)", text, flags=re.S):
        note = " ".join(line.strip() for line in match.group(1).splitlines() if line.strip())
        if note:
            notes.append(note)
    return notes


def _extract_cti_extra_fields(text: str) -> dict[str, Any]:
    fields = {
        "验证码": _first_match([r"验证码[:：]\s*([A-Z0-9]+)"], text),
        "客户地址": _label_value(text, "地址"),
        "CTI样品编号": _cti_label_value(text, "CTI 样品编号"),
        "样品数量": _cti_label_value(text, "样品数量"),
        "样品状态": _cti_label_value(text, "样品状态"),
        "生产日期": _cti_label_value(text, "生产日期"),
        "样品规格": _cti_label_value(text, "样品规格"),
        "生产商": _cti_label_value(text, "生产商"),
        "样品接收日期": _cti_label_value(text, "样品接收日期"),
        "样品检测日期": _cti_label_value(text, "样品检测日期"),
        "检测项目概述": _first_match([r"检测项目[:：]\s*(.+?)\s*检测结果[:：]"], text),
        "备注": _extract_section(text, "备注：", ["声明：", "*** 报告结束 ***"]),
        "声明": _extract_section(text, "声明：", ["*** 报告结束 ***"]),
    }
    return {key: _clean_multiline(value) if isinstance(value, str) else value for key, value in fields.items() if value}


def _cti_label_value(text: str, label: str) -> str | None:
    return _first_match([rf"{re.escape(label)}\s*\n：([^\n\r]+)"], text)


def _extract_cti_items(text: str) -> list[ReportItem]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    starts = [(index, line) for index, line in enumerate(lines) if _is_cti_item_start(lines, index)]
    items: list[ReportItem] = []
    for position, (start, item_no) in enumerate(starts):
        number = int(item_no)
        if number > 80:
            continue
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        block = _trim_cti_block(lines[start:end])
        item = _parse_cti_item_block(block)
        if item:
            items.append(item)
    return items


def _trim_cti_block(block: list[str]) -> list[str]:
    stop_values = {"以下空白", "备注：", "声明：", "样品图片"}
    trimmed: list[str] = []
    for value in block:
        if value.startswith("--- page") or value in stop_values:
            break
        if value in {"检测结果:", "序号", "检验项目", "单位", "检测结果", "限量要求", "结论", "检测方法"}:
            continue
        trimmed.append(value)
    return trimmed


def _parse_cti_item_block(block: list[str]) -> ReportItem | None:
    if len(block) < 7 or not re.fullmatch(r"\d{1,2}", block[0]):
        return None
    body = block[1:]
    unit_index = next((index for index, value in enumerate(body) if _looks_like_unit(value) or value == "/"), None)
    if unit_index is None:
        return None
    name = _join_wrapped_name(body[:unit_index])
    unit = body[unit_index]
    tail = body[unit_index + 1 :]
    if len(tail) < 4:
        return None
    value, standard, conclusion = tail[0], tail[1], tail[2]
    method = " ".join(tail[3:])
    return ReportItem(
        name=name,
        value=value,
        unit=unit,
        standard=standard,
        method=method,
        conclusion=conclusion,
        source_text=" | ".join(block),
    )


def _is_cti_item_start(lines: list[str], index: int) -> bool:
    value = lines[index]
    if not re.fullmatch(r"\d{1,2}", value):
        return False
    number = int(value)
    if number < 1 or number > 80:
        return False
    if index + 1 >= len(lines) or re.fullmatch(r"\d+(?:\.\d+)?", lines[index + 1]):
        return False
    if _looks_like_limit(lines[index + 1]) or lines[index + 1] in {"符合", "不符合", "未检出", "ND", "/", "——"}:
        return False
    lookahead = lines[index + 1 : min(len(lines), index + 8)]
    return any(_looks_like_unit(item) or item in {"/", "IU/kg"} for item in lookahead)


def _extract_merieux_extra_fields(text: str) -> dict[str, Any]:
    page2_fields = _extract_merieux_page2_fields(text)
    fields = {
        **page2_fields,
        "样品编号": _first_match([r"Sample Number 样品编号[:：]([A-Z0-9\\-]+)"], text),
        "检测开始日期": _first_match([r"Start Test Date 检测开始日期[:：]([0-9\\-]+)"], text),
        "检测结束日期": _first_match([r"End Test Date 检测结束日期[:：]([0-9\\-]+)"], text),
        "备注": _extract_section(text, "Notes\n备注", ["编制人", "Results 结果"]),
        "声明": _extract_section(text, "Decision Rule", ["Sample Photo"]),
    }
    return {key: _clean_multiline(value) if isinstance(value, str) else value for key, value in fields.items() if value}


def _merieux_pair_value(text: str, english: str, chinese: str) -> str | None:
    pattern = rf"{re.escape(english)}\s*\n{re.escape(chinese)}\s*\n([^\n\r]+)"
    return _first_match([pattern], text)


def _extract_merieux_page2_fields(text: str) -> dict[str, str]:
    if "--- page 2 ---" not in text:
        return {}
    page2 = text.split("--- page 2 ---", 1)[1].split("--- page 3 ---", 1)[0]
    lines = [line.strip() for line in page2.splitlines() if line.strip()]

    def after(label: str, offset: int = 1) -> str | None:
        try:
            return lines[lines.index(label) + offset]
        except (ValueError, IndexError):
            return None

    def join_after(label: str, offsets: list[int]) -> str | None:
        values: list[str] = []
        try:
            start = lines.index(label)
        except ValueError:
            return None
        for offset in offsets:
            index = start + offset
            if index < len(lines):
                values.append(lines[index])
        return "".join(values) if values else None

    return {
        "规格型号": after("规格型号", 1),
        "批号": after("商标", 1),
        "商标": after("商标", 2),
        "委托单位地址": join_after("委托单位地址", [2, 3]),
        "生产单位": after("生产单位", 4),
        "生产日期": after("生产日期", 1),
        "样品等级或状态": " ".join(value for value in [after("检验类别", 1), after("检验类别", 2)] if value),
        "检验类别": " ".join(value for value in [after("样品等级或状态", 1), after("样品等级或状态", 2)] if value),
        "样品量": after("样品量", 3),
        "到样日期": after("到样日期", 2),
        "主要仪器": join_after("所用主要仪器", [1, 2]),
        "实验室环境条件": join_after("实验室环境条件", [1, 2]),
    }


def _extract_merieux_items(text: str) -> list[ReportItem]:
    section_match = re.search(r"Sample ID 样品编号[:：][^\n]+\n(.+?)(?:◆：|The specifications|Decision Rule|Sample Photo)", text, flags=re.S)
    if not section_match:
        return []
    lines = [line.strip() for line in section_match.group(1).splitlines() if line.strip()]
    starts = _find_merieux_item_starts(lines)
    items: list[ReportItem] = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        block = lines[start:end]
        item = _parse_merieux_item_block(block)
        if item:
            items.append(item)
    return items


def _find_merieux_item_starts(lines: list[str]) -> list[int]:
    starts: list[int] = []
    for index in range(len(lines)):
        if index > 0 and not _looks_like_merieux_previous_method(lines[index - 1]):
            continue
        loq_index = _find_merieux_loq_index(lines, index)
        if loq_index is None:
            continue
        if _split_merieux_name_and_unit(lines[index:loq_index])[1]:
            starts.append(index)
    return starts


def _looks_like_merieux_previous_method(value: str) -> bool:
    return _looks_like_method(value) or value.startswith("参考") or value in {"第一法", "第二法", "第三法"}


def _find_merieux_loq_index(lines: list[str], start: int) -> int | None:
    for index in range(start + 1, min(len(lines), start + 8)):
        if lines[index] == "---":
            return index
        if re.fullmatch(r"<?\d+(?:\.\d+)?", lines[index]) and index + 1 < len(lines) and "LOQ" in lines[index + 1]:
            return index
    return None


def _parse_merieux_item_block(block: list[str]) -> ReportItem | None:
    loq_index = _find_merieux_loq_index(block, 0)
    if loq_index is None:
        return None
    name, unit = _split_merieux_name_and_unit(block[:loq_index])
    loq = block[loq_index]
    cursor = loq_index + 1
    if cursor < len(block) and "LOQ" in block[cursor]:
        loq = f"{loq} {block[cursor]}"
        cursor += 1
    if cursor >= len(block):
        return None
    department = block[cursor]
    cursor += 1
    decision_parts: list[str] = []
    while cursor < len(block) and block[cursor] in {"Pass", "符合", "---"}:
        decision_parts.append(block[cursor])
        cursor += 1
        if len(decision_parts) >= 2:
            break
    result_parts: list[str] = []
    while cursor < len(block):
        if not result_parts:
            result_parts.append(block[cursor])
            cursor += 1
            continue
        if block[cursor] in {"未检出"}:
            result_parts.append(block[cursor])
            cursor += 1
            continue
        break
    if cursor >= len(block):
        return None
    standard = block[cursor]
    method_parts = block[cursor + 1 :]
    return ReportItem(
        name=name,
        unit=unit,
        value=" ".join(result_parts),
        standard=standard,
        method=" ".join(method_parts),
        conclusion=" ".join(decision_parts),
        source_text=" | ".join(block),
        extra_fields={"定量限/检出限": loq, "部门": department},
    )


def _split_merieux_name_and_unit(parts: list[str]) -> tuple[str, str | None]:
    joined = " ".join(parts)
    joined = joined.replace("/2 5g", "/25g")
    match = re.search(r"\((%|g/kg|μg/kg|µg/kg|mg/kg|/25g|/25 g)\)\s*(?:◆)?\s*$", joined)
    if match:
        return joined[: match.start()].strip(), match.group(1)
    return joined, None


def _extract_intertek_extra_fields(text: str) -> dict[str, Any]:
    fields = {
        "替代报告编号": _first_match([r"此报告替代\s*([A-Z0-9]+)"], text),
        "样品编号": _first_match([r"样品编号([A-Z0-9.]+)"], text),
        "检验类别": _first_match([r"检验类别([^\n\r]+)"], text),
        "样品来源": _first_match([r"样品来源([^\n\r]+)"], text),
        "样品规格": _first_match([r"样品规格([^\n\r]+)"], text),
        "生产日期": _first_match([r"生产日期([^\n\r]+)"], text),
        "生产商": _first_match([r"生产商([^\n\r]+)"], text),
        "到样时间": _first_match([r"到样时间([^\n\r]+)"], text),
        "检测周期": _first_match([r"检测周期([^\n\r]+)"], text),
        "客户地址": _first_match([r"客户地址([^\n\r]+)"], text),
        "判定标准": _extract_intertek_standard_summary(text),
        "备注": _extract_section(text, "备注：", ["测试结果："]),
        "感官描述": _extract_section(text, "感官描述", ["第 2 页"]),
        "报告说明": _extract_section(text, "检测报告说明", ["第 4 页"]),
    }
    return {key: _clean_multiline(value) if isinstance(value, str) else value for key, value in fields.items() if value}


def _extract_intertek_standard_summary(text: str) -> str | None:
    match = re.search(r"样品名称\s*\n判定标准\s*\n结论\s*\n(.+?)\n备注：", text, flags=re.S)
    return match.group(1).strip() if match else None


def _extract_intertek_items(text: str) -> list[ReportItem]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    starts = [(index, line) for index, line in enumerate(lines) if _is_intertek_item_start(lines, index)]
    items: list[ReportItem] = []
    for position, (start, _) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        block = _trim_intertek_block(lines[start:end])
        item = _parse_intertek_item_block(block)
        if item:
            items.append(item)
    return items


def _is_intertek_item_start(lines: list[str], index: int) -> bool:
    if not re.fullmatch(r"\d{1,2}", lines[index]):
        return False
    if index + 1 >= len(lines) or re.fullmatch(r"\d+(?:\.\d+)?", lines[index + 1]):
        return False
    if _looks_like_limit(lines[index + 1]) or lines[index + 1] in {"符合", "不符合", "未检出", "ND", "——"}:
        return False
    lookahead = lines[index + 1 : min(len(lines), index + 8)]
    return any(_looks_like_unit(value) or value in {"g"} for value in lookahead)


def _trim_intertek_block(block: list[str]) -> list[str]:
    stop_values = {"感官描述", "报告结束", "备注：", "结束"}
    ignored = {"序号", "测试项目", "单位", "检测方法", "技术要求", "报告检出限", "测试结果", "单项判定"}
    trimmed: list[str] = []
    for value in block:
        if value.startswith("--- page") or value in stop_values or value.startswith("备注："):
            break
        if value in ignored:
            continue
        trimmed.append(value)
    return trimmed


def _parse_intertek_item_block(block: list[str]) -> ReportItem | None:
    if len(block) < 8 or not re.fullmatch(r"\d{1,2}", block[0]):
        return None
    body = block[1:]
    unit_index = next((index for index, value in enumerate(body) if _looks_like_unit(value) or value in {"g"}), None)
    if unit_index is None:
        return None
    name = _join_wrapped_name(body[:unit_index])
    unit = body[unit_index]
    tail = body[unit_index + 1 :]
    if len(tail) < 5:
        return None
    judgement = tail[-1]
    result = tail[-2]
    lod = tail[-3]
    method_and_requirement = tail[:-3]
    if len(method_and_requirement) >= 2 and (
        "允许短缺" in method_and_requirement[-2] or method_and_requirement[-1].startswith("量")
    ):
        requirement = "".join(method_and_requirement[-2:])
        method = " ".join(method_and_requirement[:-2])
    else:
        requirement = method_and_requirement[-1]
        method = " ".join(method_and_requirement[:-1])
    return ReportItem(
        name=name,
        unit=unit,
        method=method,
        standard=requirement,
        value=result,
        conclusion=judgement,
        source_text=" | ".join(block),
        extra_fields={"报告检出限": lod},
    )


def _extract_section(text: str, start: str, ends: list[str]) -> str | None:
    start_index = text.find(start)
    if start_index < 0:
        return None
    body = text[start_index + len(start) :]
    end_indexes = [body.find(end) for end in ends if body.find(end) >= 0]
    if end_indexes:
        body = body[: min(end_indexes)]
    return body.strip()


def _extract_sgs_items(text: str) -> list[ReportItem]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    item_starts = [(index, line) for index, line in enumerate(lines) if re.fullmatch(r"\d{1,2}", line)]
    items: list[ReportItem] = []
    for position, (start_index, item_no) in enumerate(item_starts):
        if int(item_no) > 80:
            continue
        end_index = item_starts[position + 1][0] if position + 1 < len(item_starts) else len(lines)
        block = lines[start_index:end_index]
        item = _parse_sgs_item_block(block)
        if item:
            items.append(item)
    return items


def _parse_sgs_item_block(block: list[str]) -> ReportItem | None:
    if len(block) < 5:
        return None

    body = _trim_sgs_block(block[1:])
    method_index = next((index for index, value in enumerate(body) if _looks_like_method(value)), None)
    if method_index is None or method_index == 0:
        return None

    name_parts = body[:method_index]
    unit = None
    if name_parts and _looks_like_unit(name_parts[-1]):
        unit = name_parts[-1]
        name_parts = name_parts[:-1]
    name = _join_wrapped_name(name_parts)
    method_parts = [body[method_index]]
    cursor = method_index + 1
    while cursor < len(body) and _looks_like_method_continuation(body[cursor], method_parts[-1]):
        method_parts.append(body[cursor])
        cursor += 1
    method = " ".join(method_parts)

    tail = body[cursor:]
    conclusion = tail[-1] if tail and tail[-1] in {"符合", "合格", "不合格", "未检出", "-"} else None
    if conclusion:
        tail = tail[:-1]
    if len(tail) >= 4 and _looks_like_method_numeric_section(tail[0]):
        method = f"{method} {tail[0]}"
        tail = tail[1:]

    result = tail[0] if tail else None
    quantitation_limit = None
    standard = None
    if len(tail) == 2:
        standard = tail[1]
    elif len(tail) >= 3:
        quantitation_limit = tail[1]
        standard = " ".join(tail[2:])

    return ReportItem(
        name=name,
        value=result,
        unit=unit,
        standard=standard,
        method=method,
        conclusion=conclusion,
        source_text=" | ".join([block[0], *body]),
        extra_fields={"定量限": quantitation_limit} if quantitation_limit is not None else {},
    )


def _join_wrapped_name(parts: list[str]) -> str:
    value = "".join(parts)
    value = value.replace("（以干基计）", "（以干基计）")
    return re.sub(r"\s+", "", value)


def _trim_sgs_block(body: list[str]) -> list[str]:
    ignored = {
        "理化检测",
        "微生物检测",
        "编号",
        "检测项目",
        "单位",
        "检测方法",
        "检测结果",
        "0001",
        "定量限",
        "限值",
        "单项说明",
    }
    trimmed: list[str] = []
    seen_method = False
    for value in body:
        if value.startswith("--- page") or value in {"备注：", "备注:", "样品照片：", "注意事项："}:
            break
        if value in ignored:
            continue
        if _looks_like_method(value):
            seen_method = True
        trimmed.append(value)
        if seen_method and value in {"符合", "合格", "不合格", "未检出"}:
            break
    return trimmed


def _looks_like_unit(value: str) -> bool:
    return value in {"%", "％", "µg/kg", "μg/kg", "ug/kg", "mg/kg", "g/kg", "/25 g", "/25g", "IU/kg"}


def _looks_like_method(value: str) -> bool:
    return bool(re.search(r"(GB/T|NY/T|GB|SN/T|ISO|AOAC)", value))


def _looks_like_method_continuation(value: str, previous: str) -> bool:
    return value == "B" and bool(re.search(r"\d\s*$", previous))


def _looks_like_method_numeric_section(value: str) -> bool:
    return bool(re.fullmatch(r"\d+(?:\.\d+)?", value))


def _looks_like_limit(value: str) -> bool:
    return value.startswith(("≤", "≥", "<", ">")) or value in {"不得检出"}
