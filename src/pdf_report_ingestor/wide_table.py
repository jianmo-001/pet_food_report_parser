from __future__ import annotations

import json
import re
from typing import Any

from .exporter import to_main_fields
from .models import ParsedReport, ReportItem


WIDE_VALUE_FIELDS = [
    "粗蛋白",
    "粗脂肪",
    "水分",
    "粗灰分",
    "粗纤维",
    "钙",
    "总磷",
    "钙磷比",
    "钠",
    "钾",
    "镁",
    "锌",
    "铁",
    "铜",
    "锰",
    "碘",
    "硒",
    "牛磺酸",
    "淀粉",
    "黄曲霉毒素B1",
    "沙门氏菌",
    "氯化物",
    "维生素A",
    "维生素D",
    "维生素E",
    "维生素B1",
    "维生素B6",
    "维生素B12",
    "叶酸",
    "胆碱",
    "胆固醇",
    "烟酸",
    "泛酸",
    "核黄素",
    "乳糖",
    "净含量",
    "感官",
    "感官指标",
    "色泽",
    "气味",
    "气味和滋味",
    "状态",
    "形状",
    "组织状态",
    "外观",
    "异物",
    "杂质",
    "微生物",
    "丙二醛",
    "己醛",
    "组胺",
    "过氧化值",
    "酸价",
    "挥发性盐基氮",
    "肌醇",
    "精氨酸",
    "组氨酸",
    "异亮氨酸",
    "亮氨酸",
    "赖氨酸",
    "苯丙氨酸",
    "苯丙氨酸+酪氨酸",
    "苏氨酸",
    "酪氨酸",
    "缬氨酸",
    "胱氨酸",
    "蛋氨酸",
    "蛋氨酸+胱氨酸",
    "色氨酸",
    "天门冬氨酸",
    "丝氨酸",
    "谷氨酸",
    "脯氨酸",
    "甘氨酸",
    "丙氨酸",
    "18项氨基酸总和",
    "无机砷",
    "总砷",
    "氟",
    "镉",
    "铬",
    "汞",
    "铅",
    "玉米赤霉烯酮",
    "伏马毒素B1",
    "伏马毒素B2",
    "伏马毒素B1+B2",
    "脱氧雪腐镰刀菌烯醇",
    "赭曲霉毒素A",
    "T-2毒素",
    "HT-2毒素",
    "T-2毒素+HT-2毒素",
    "氰化物",
    "三聚氰胺",
    "亚硝酸盐",
    "PCB28",
    "PCB52",
    "PCB101",
    "PCB138",
    "PCB153",
    "PCB180",
    "多氯联苯",
    "o,p'-DDT",
    "p,p'-DDD",
    "p,p'-DDE",
    "p,p'-DDT",
    "滴滴涕",
    "α-HCH",
    "β-HCH",
    "γ-HCH",
    "δ-HCH",
    "六六六",
    "六氯苯",
    "生物素",
    "儿茶素",
    "表儿茶素",
    "表没食子儿茶素",
    "表儿茶素没食子酸酯",
    "儿茶素类总量",
    "α-生育酚",
    "吡哆醇",
    "吡哆醛",
    "吡哆胺",
    "烟酰胺",
    "亚油酸",
    "α-亚麻酸",
    "花生四烯酸",
    "EPA",
    "DHA",
    "DHA+EPA",
    "ω-3脂肪酸",
    "ω-6脂肪酸",
    "细菌总数",
    "肠杆菌科",
    "胃蛋白酶消化率",
    "淀粉糊化度",
    "商业无菌",
    "胶类定性",
    "鸽子成分",
    "鹅源性成分",
    "脂肪酸比例",
]

WIDE_FIELD_UNITS = {
    "18项氨基酸总和": "%",
    "PCB101": "μg/kg",
    "PCB138": "μg/kg",
    "PCB153": "μg/kg",
    "PCB180": "μg/kg",
    "PCB28": "μg/kg",
    "PCB52": "μg/kg",
    "o,p'-DDT": "mg/kg",
    "p,p'-DDT": "mg/kg",
    "α-HCH": "mg/kg",
    "α-亚麻酸": "%",
    "β-HCH": "mg/kg",
    "γ-HCH": "mg/kg",
    "δ-HCH": "μg/kg",
    "三聚氰胺": "mg/kg",
    "丙二醛": "mg/kg",
    "丙氨酸": "%",
    "丝氨酸": "%",
    "亚油酸": "%",
    "亚硝酸盐": "mg/kg",
    "亮氨酸": "%",
    "伏马毒素B1": "mg/kg",
    "伏马毒素B1+B2": "mg/kg",
    "伏马毒素B2": "mg/kg",
    "儿茶素": "%",
    "儿茶素类总量": "%",
    "六氯苯": "mg/kg",
    "乳糖": "g/100g",
    "净含量": "g",
    "叶酸": "mg/kg",
    "吡哆胺": "mg/kg",
    "吡哆醇": "mg/kg",
    "吡哆醛": "mg/kg",
    "多氯联苯": "μg/kg",
    "天门冬氨酸": "%",
    "己醛": "mg/kg",
    "异亮氨酸": "%",
    "总砷": "mg/kg",
    "总磷": "%",
    "无机砷": "mg/kg",
    "核黄素": "mg/kg",
    "氟": "mg/kg",
    "氯化物": "%",
    "氰化物": "mg/kg",
    "水分": "%",
    "汞": "mg/kg",
    "沙门氏菌": "/25g",
    "泛酸": "mg/kg",
    "淀粉糊化度": "%",
    "滴滴涕": "mg/kg",
    "烟酸": "mg/kg",
    "牛磺酸": "%",
    "玉米赤霉烯酮": "mg/kg",
    "甘氨酸": "%",
    "生物素": "mg/kg",
    "硒": "mg/kg",
    "碘": "mg/kg",
    "粗灰分": "%",
    "粗纤维": "%",
    "粗脂肪": "%",
    "粗蛋白": "%",
    "精氨酸": "%",
    "组氨酸": "%",
    "组胺": "mg/kg",
    "维生素A": "IU/kg",
    "维生素B1": "mg/kg",
    "维生素B12": "mg/kg",
    "维生素B6": "mg/kg",
    "维生素D": "IU/kg",
    "维生素E": "IU/kg",
    "缬氨酸": "%",
    "肌醇": "mg/kg",
    "胃蛋白酶消化率": "%",
    "胆碱": "mg/kg",
    "胆固醇": "mg/kg",
    "胱氨酸": "%",
    "脯氨酸": "%",
    "脱氧雪腐镰刀菌烯醇": "mg/kg",
    "色氨酸": "%",
    "苏氨酸": "%",
    "苯丙氨酸": "%",
    "苯丙氨酸+酪氨酸": "%",
    "蛋氨酸": "%",
    "蛋氨酸+胱氨酸": "%",
    "表儿茶素": "%",
    "表儿茶素没食子酸酯": "%",
    "表没食子儿茶素": "%",
    "谷氨酸": "%",
    "赖氨酸": "%",
    "赭曲霉毒素A": "mg/kg",
    "酪氨酸": "%",
    "钙": "%",
    "钠": "%",
    "钾": "%",
    "铁": "mg/kg",
    "铅": "mg/kg",
    "铜": "mg/kg",
    "铬": "mg/kg",
    "锌": "mg/kg",
    "锰": "mg/kg",
    "镁": "%",
    "镉": "mg/kg",
    "黄曲霉毒素B1": "μg/kg",
}

WIDE_BASE_FIELDS = [
    "产品名称",
    "PDF文件名",
    "PDF附件",
    "解析状态",
    "错误原因",
    "品牌名称",
    "报告编号",
    "样品名称",
    "检测机构",
    "报告日期",
    "样品接收日期",
    "检测开始日期",
    "检测结束日期",
    "详情页链接",
    "归档文件链接",
    "归档错误",
]

WIDE_EXTRA_FIELDS = ["未映射检测项目JSON"]

WIDE_DATE_FIELDS = {"报告日期", "样品接收日期", "检测开始日期", "检测结束日期"}
WIDE_ATTACHMENT_FIELDS = {"PDF附件"}


def wide_field_names() -> list[str]:
    return [*WIDE_BASE_FIELDS, *[_wide_field_name(field) for field in WIDE_VALUE_FIELDS], *WIDE_EXTRA_FIELDS]


def _wide_field_name(field: str) -> str:
    unit = WIDE_FIELD_UNITS.get(field)
    return f"{field}（{unit}）" if unit else field


def split_brand_product(sample_name: str | None) -> tuple[str | None, str | None]:
    if not sample_name:
        return None, None
    value = sample_name.strip()
    if "®" not in value:
        return None, value
    brand, _ = value.split("®", 1)
    return brand.strip() or None, value


def build_wide_row(
    report: ParsedReport,
    pdf_file_name: str | None = None,
    detail_url: str | None = None,
) -> dict[str, Any]:
    main_fields = to_main_fields(report, pdf_file_name)
    brand, product = split_brand_product(report.sample_name)
    row: dict[str, Any] = {
        "产品名称": product,
        "PDF文件名": pdf_file_name,
        "品牌名称": brand,
        "报告编号": report.report_no,
        "样品名称": report.sample_name,
        "检测机构": report.lab,
        "报告日期": main_fields.get("报告日期"),
        "样品接收日期": main_fields.get("样品接收日期"),
        "检测开始日期": main_fields.get("检测开始日期"),
        "检测结束日期": main_fields.get("检测结束日期"),
    }
    if detail_url:
        row["详情页链接"] = detail_url

    unmapped: list[dict[str, Any]] = []
    for item in report.items:
        field = normalize_item_name(item.name)
        if not field:
            unmapped.append(_unmapped_item(item))
            continue
        output_field = _wide_field_name(field)
        if output_field in row and row[output_field] not in (None, ""):
            unmapped.append(_unmapped_item(item, reason=f"重复字段：{output_field}"))
            continue
        row[output_field] = format_item_value(item, include_unit=field not in WIDE_FIELD_UNITS, target_unit=WIDE_FIELD_UNITS.get(field))
    row["未映射检测项目JSON"] = json.dumps(unmapped, ensure_ascii=False) if unmapped else ""
    return row


def normalize_item_name(name: str | None) -> str | None:
    if not name:
        return None
    normalized = _normalize_name_text(name)
    if normalized.startswith("多氯联苯"):
        return "多氯联苯"
    if normalized.startswith("滴滴涕"):
        return "滴滴涕"
    if "α六六六" in normalized or "αhch" in normalized:
        return "α-HCH"
    if "β六六六" in normalized or "βhch" in normalized:
        return "β-HCH"
    if "γ六六六" in normalized or "γhch" in normalized:
        return "γ-HCH"
    if "δ六六六" in normalized or "δhch" in normalized:
        return "δ-HCH"
    if normalized.startswith("六六六"):
        return "六六六"
    if "亚油酸+花生四烯" in normalized and "亚麻酸+epa+dha" in normalized:
        return "脂肪酸比例"
    rules = [
        ("黄曲霉毒素B1", ["黄曲霉毒素b1", "aflatoxinsb1"]),
        ("沙门氏菌", ["沙门氏菌", "salmonella"]),
        ("粗蛋白", ["粗蛋白质", "粗蛋白", "crudeprotein"]),
        ("粗脂肪", ["粗脂肪", "crudefat"]),
        ("粗灰分", ["粗灰分", "crudeash"]),
        ("粗纤维", ["粗纤维", "crudefiber"]),
        ("水分", ["水分", "moisture"]),
        ("钙磷比", ["钙磷比"]),
        ("总磷", ["总磷", "磷"]),
        ("氯化物", ["水溶性氯化物", "氯化物"]),
        ("无机砷", ["无机砷"]),
        ("总砷", ["总砷", "砷as"]),
        ("氟", ["氟f", "氟"]),
        ("镉", ["镉cd", "镉"]),
        ("铬", ["铬cr", "铬"]),
        ("汞", ["汞hg", "汞"]),
        ("铅", ["铅pb", "铅"]),
        ("亚硝酸盐", ["亚硝酸盐", "nano2"]),
        ("钙", ["钙", "calcium"]),
        ("钠", ["钠"]),
        ("钾", ["钾"]),
        ("镁", ["镁"]),
        ("锌", ["锌"]),
        ("铁", ["铁"]),
        ("铜", ["铜"]),
        ("锰", ["锰"]),
        ("碘", ["碘"]),
        ("硒", ["硒"]),
        ("牛磺酸", ["牛磺酸"]),
        ("淀粉糊化度", ["淀粉糊化度"]),
        ("淀粉", ["淀粉", "starch"]),
        ("维生素A", ["维生素a"]),
        ("维生素D", ["维生素d"]),
        ("维生素E", ["维生素e"]),
        ("维生素B12", ["维生素b12"]),
        ("维生素B6", ["维生素b6"]),
        ("维生素B1", ["维生素b1", "硫胺素"]),
        ("叶酸", ["叶酸"]),
        ("胆碱", ["胆碱"]),
        ("胆固醇", ["胆固醇"]),
        ("烟酸", ["烟酸"]),
        ("泛酸", ["泛酸"]),
        ("核黄素", ["核黄素", "维生素b2"]),
        ("净含量", ["净含量"]),
        ("乳糖", ["乳糖"]),
        ("感官指标", ["感官指标"]),
        ("感官", ["感官"]),
        ("色泽", ["色泽"]),
        ("气味和滋味", ["气味和滋味"]),
        ("气味", ["气味"]),
        ("形状", ["形状"]),
        ("组织状态", ["组织状态"]),
        ("状态", ["状态"]),
        ("外观", ["外观"]),
        ("异物", ["异物"]),
        ("杂质", ["杂质"]),
        ("微生物", ["微生物"]),
        ("丙二醛", ["丙二醛"]),
        ("己醛", ["己醛"]),
        ("组胺", ["组胺"]),
        ("过氧化值", ["过氧化值"]),
        ("酸价", ["酸价"]),
        ("挥发性盐基氮", ["挥发性盐基氮"]),
        ("18项氨基酸总和", ["18项氨基酸总和"]),
        ("苯丙氨酸+酪氨酸", ["苯丙氨酸+酪氨酸"]),
        ("蛋氨酸+胱氨酸", ["蛋氨酸+胱氨酸"]),
        ("精氨酸", ["精氨酸"]),
        ("组氨酸", ["组氨酸"]),
        ("异亮氨酸", ["异亮氨酸"]),
        ("亮氨酸", ["亮氨酸"]),
        ("赖氨酸", ["赖氨酸"]),
        ("苯丙氨酸", ["苯丙氨酸"]),
        ("苏氨酸", ["苏氨酸"]),
        ("酪氨酸", ["酪氨酸"]),
        ("缬氨酸", ["缬氨酸"]),
        ("胱氨酸", ["胱氨酸"]),
        ("蛋氨酸", ["蛋氨酸"]),
        ("色氨酸", ["色氨酸"]),
        ("天门冬氨酸", ["天门冬氨酸", "天冬氨酸"]),
        ("丝氨酸", ["丝氨酸"]),
        ("谷氨酸", ["谷氨酸"]),
        ("脯氨酸", ["脯氨酸"]),
        ("甘氨酸", ["甘氨酸"]),
        ("丙氨酸", ["丙氨酸"]),
        ("玉米赤霉烯酮", ["玉米赤霉烯酮"]),
        ("伏马毒素B1+B2", ["伏马毒素b1+b2", "伏马毒素b₁+b₂", "伏马毒素b1b2", "伏马毒素b₁b₂"]),
        ("伏马毒素B1", ["伏马毒素b1", "伏马毒素b₁"]),
        ("伏马毒素B2", ["伏马毒素b2", "伏马毒素b₂"]),
        ("脱氧雪腐镰刀菌烯醇", ["脱氧雪腐镰刀菌烯醇", "呕吐毒素"]),
        ("赭曲霉毒素A", ["赭曲霉毒素a"]),
        ("T-2毒素+HT-2毒素", ["ht2毒素与t2毒素之和", "t2、ht2毒素之和", "t2毒素和ht2毒素", "t2和ht2", "t2毒素+ht2毒素"]),
        ("HT-2毒素", ["ht2毒素"]),
        ("T-2毒素", ["t2毒素"]),
        ("氰化物", ["氰化物", "hcn"]),
        ("三聚氰胺", ["三聚氰胺"]),
        ("PCB28", ["pcb28", "244三氯联苯"]),
        ("PCB52", ["pcb52", "2255四氯联苯"]),
        ("PCB101", ["pcb101", "22455五氯联苯"]),
        ("PCB138", ["pcb138", "223445六氯联苯"]),
        ("PCB153", ["pcb153", "224455六氯联苯"]),
        ("PCB180", ["pcb180", "2234455七氯联苯"]),
        ("多氯联苯", ["多氯联苯"]),
        ("o,p'-DDT", ["op滴滴涕", "opddt"]),
        ("p,p'-DDD", ["pp滴滴滴", "ppddd"]),
        ("p,p'-DDE", ["pp滴滴伊", "ppdde"]),
        ("p,p'-DDT", ["pp滴滴涕", "ppddt"]),
        ("滴滴涕", ["滴滴涕", "ddt"]),
        ("α-HCH", ["α六六六", "alphahch", "αhch"]),
        ("β-HCH", ["β六六六", "betahch", "βhch"]),
        ("γ-HCH", ["γ六六六", "gammahch", "γhch"]),
        ("δ-HCH", ["δ六六六", "deltahch", "δhch"]),
        ("六六六", ["六六六", "hch"]),
        ("六氯苯", ["六氯苯", "hcb"]),
        ("生物素", ["生物素", "维生素b7"]),
        ("儿茶素类总量", ["儿茶素类总量"]),
        ("表儿茶素没食子酸酯", ["表儿茶素没食子酸酯", "ecg"]),
        ("表没食子儿茶素", ["表没食子儿茶素", "egc"]),
        ("表儿茶素", ["表儿茶素", "ec"]),
        ("儿茶素", ["儿茶素+c", "儿茶素"]),
        ("肌醇", ["肌醇"]),
        ("α-生育酚", ["α生育酚", "alphatocopherol"]),
        ("吡哆醇", ["吡哆醇"]),
        ("吡哆醛", ["吡哆醛"]),
        ("吡哆胺", ["吡哆胺"]),
        ("烟酰胺", ["烟酰胺"]),
        ("DHA+EPA", ["dha+epa"]),
        ("亚油酸", ["亚油酸", "c18:2"]),
        ("α-亚麻酸", ["α亚麻酸", "ala", "c18:3"]),
        ("花生四烯酸", ["花生四烯酸", "ara", "c20:4"]),
        ("EPA", ["epa", "c20:5"]),
        ("DHA", ["dha", "c22:6"]),
        ("ω-3脂肪酸", ["ω3脂肪酸", "omega3脂肪酸"]),
        ("ω-6脂肪酸", ["ω6脂肪酸", "omega6脂肪酸"]),
        ("细菌总数", ["细菌总数"]),
        ("肠杆菌科", ["肠杆菌科"]),
        ("胃蛋白酶消化率", ["胃蛋白酶消化率"]),
        ("商业无菌", ["商业无菌"]),
        ("胶类定性", ["胶类定性"]),
        ("鸽子成分", ["鸽子成分"]),
        ("鹅源性成分", ["鹅源性成分"]),
        ("脂肪酸比例", ["亚油酸+花生四烯", "亚麻酸+epa+dha"]),
    ]
    for field, aliases in rules:
        if any(alias in normalized for alias in aliases):
            return field
    return None


def format_item_value(item: ReportItem, include_unit: bool = True, target_unit: str | None = None) -> str | None:
    if item.value in (None, ""):
        return None
    value = str(item.value).strip()
    if target_unit:
        value = _convert_value_unit(value, item.unit, target_unit)
    if not include_unit:
        return value
    unit = str(item.unit).strip() if item.unit else ""
    if unit and unit != "/" and unit not in value:
        return f"{value} {unit}"
    return value


def _convert_value_unit(value: str, source_unit: str | None, target_unit: str) -> str:
    source = (source_unit or "").strip()
    if source == target_unit:
        return value
    if source == "kg" and target_unit == "g":
        try:
            converted = float(value) * 1000
        except ValueError:
            return value
        return f"{converted:g}"
    return value


def _normalize_name_text(value: str) -> str:
    text = value.lower()
    subscript_map = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
    text = text.translate(subscript_map)
    text = text.replace("Δ", "")
    text = text.replace("α-", "α").replace("β-", "β").replace("γ-", "γ")
    text = text.replace("ω-", "ω").replace("Ω-", "ω")
    text = re.sub(r"[#*ª®'’\s（）()，,⁻\-_]+", "", text)
    text = text.replace("以干基计", "").replace("以干物质计", "")
    text = text.replace("ondrybasis", "").replace("asdrymattercontentof88%", "")
    text = text.replace("以干物质含量88%计", "").replace("干物质含量88%计", "")
    text = text.replace("以脂肪计", "")
    text = text.replace("以干基计", "").replace("以湿基计", "")
    return text


def _unmapped_item(item: ReportItem, reason: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "检测项目": item.name,
        "检测结果": item.value,
        "单位": item.unit,
        "限值": item.standard,
        "单项结论": item.conclusion,
    }
    if reason:
        payload["原因"] = reason
    return payload
