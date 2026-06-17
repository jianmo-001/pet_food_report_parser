from textwrap import dedent

from pdf_report_ingestor.templates import (
    TemplateRule,
    _extract_cti_items,
    _normalize_scientific_notation,
    _parse_sgs_item_block,
    extract_report,
    select_template,
)


def test_select_template_and_extract_report() -> None:
    text = """
    检测报告
    报告编号：R001
    样品名称：鸡肉味犬粮
    检测机构：通用检测机构
    委托单位：测试客户
    报告日期：2026-06-08
    检验结论：合格
    粗蛋白 28.5 % 符合标准 合格
    """
    template = TemplateRule(
        name="generic",
        version="1",
        enabled=True,
        lab=None,
        keywords=["检测报告", "报告编号"],
        fields={
            "report_no": [r"报告编号[:：\s]*([A-Za-z0-9\-_]+)"],
            "sample_name": [r"样品名称[:：\s]*([^\n\r]+)"],
            "lab": [r"检测机构[:：\s]*([^\n\r]+)"],
            "client": [r"委托单位[:：\s]*([^\n\r]+)"],
            "report_date": [r"报告日期[:：\s]*(\d{4}-\d{2}-\d{2})"],
            "conclusion": [r"检验结论[:：\s]*([^\n\r]+)"],
        },
        item_patterns=[r"([^\n\r\d]{2,30})\s+([0-9]+(?:\.[0-9]+)?)\s*([%％a-zA-Z/]+)?\s+([^\n\r]{0,40})\s+(合格|不合格|符合|未检出)"],
    )

    selected = select_template(text, [template])
    assert selected == template

    report = extract_report(text, template, "pdf_text")
    assert report.report_no == "R001"
    assert report.sample_name == "鸡肉味犬粮"
    assert report.lab == "通用检测机构"
    assert report.items[0].name == "粗蛋白"
    assert report.items[0].value == "28.5"


def test_normalize_scientific_notation_values() -> None:
    assert _normalize_scientific_notation("3.43×104") == "3.43×10^4"
    assert _normalize_scientific_notation("1.1×102") == "1.1×10^2"
    assert _normalize_scientific_notation("1.26x103") == "1.26×10^3"
    assert _normalize_scientific_notation("37.35") == "37.35"


def test_cti_sample_name_stops_before_client_label() -> None:
    text = dedent("""
    华测检测
    Centre Testing International
    报告编号
    A2260312375101009C
    样品名称：
    诚实一口®全阶段全价烘焙猫粮BK01
    委托单位：
    上海简谟生物技术有限公司
    检验结论：
    合格
    """)
    template = TemplateRule(
        name="cti_cn_inspection_report",
        version="1",
        enabled=True,
        lab="青岛市华测检测技术有限公司",
        keywords=["华测检测"],
        fields={
            "report_no": [r"报告编号[:：]?\s*\n?([A-Z][A-Z0-9]+)"],
            "sample_name": [r"样品名称\s*：\s*\n?([^\n\r]+(?:\n[^\n\r]+)?)"],
            "client": [r"委托单位[:：]?\s*\n?([^\n\r]+)"],
        },
        item_patterns=[],
    )

    report = extract_report(text, template, "pdf_text")

    assert report.sample_name == "诚实一口®全阶段全价烘焙猫粮BK01"
    assert report.client == "上海简谟生物技术有限公司"


def test_cti_sample_name_trims_inline_client_label() -> None:
    text = dedent("""
    华测检测
    Centre Testing International
    报告编号：A2260312375101031C
    样品名称： 诚实一口®全价猫用主食餐盒 鸡肉石榴口味 委托单位： 上海简谟生物技术有限公司
    检验类型： 委托检验
    """)
    template = TemplateRule(
        name="cti_cn_inspection_report",
        version="1",
        enabled=True,
        lab="青岛市华测检测技术有限公司",
        keywords=["华测检测"],
        fields={
            "report_no": [r"报告编号[:：]?\s*\n?([A-Z][A-Z0-9]+)"],
            "sample_name": [r"样品名称\s*：([^\n\r]+(?:\n[^\n\r]+)?)"],
            "client": [r"委托单位[:：]?\s*\n?([^\n\r]+)"],
        },
        item_patterns=[],
    )

    report = extract_report(text, template, "pdf_text")

    assert report.sample_name == "诚实一口®全价猫用主食餐盒 鸡肉石榴口味"


def test_sgs_method_section_is_not_parsed_as_result() -> None:
    item = _parse_sgs_item_block(
        [
            "20",
            "2,4,4'-三氯",
            "联苯",
            "(PCB28)",
            "µg/kg",
            "GB 5009.190-2014",
            "第二法",
            "ND",
        ]
    )

    assert item is not None
    assert item.name == "2,4,4'-三氯联苯(PCB28)"
    assert item.unit == "µg/kg"
    assert item.method == "GB 5009.190-2014 第二法"
    assert item.value == "ND"
    assert item.standard is None


def test_sgs_method_section_preserves_result_limit_and_standard() -> None:
    item = _parse_sgs_item_block(
        [
            "27",
            "多氯联苯",
            "µg/kg",
            "GB 5009.190-2014",
            "第二法",
            "ND",
            "-",
            "≤40",
            "符合",
        ]
    )

    assert item is not None
    assert item.name == "多氯联苯"
    assert item.method == "GB 5009.190-2014 第二法"
    assert item.value == "ND"
    assert item.extra_fields["定量限"] == "-"
    assert item.standard == "≤40"
    assert item.conclusion == "符合"


def test_sgs_year_method_section_is_not_parsed_as_result() -> None:
    item = _parse_sgs_item_block(
        [
            "2",
            "#Δ生物素",
            "mg/kg",
            "参照GB 5009.259-",
            "2023 第二法 12.3.1",
            "0.694",
            "2.5(μg/1",
            "00 g)",
            "≥0.07",
            "符合",
        ]
    )

    assert item is not None
    assert item.name == "#Δ生物素"
    assert item.method == "参照GB 5009.259- 2023 第二法 12.3.1"
    assert item.value == "0.694"
    assert item.extra_fields["定量限"] == "2.5(μg/1"
    assert item.standard == "00 g) ≥0.07"
    assert item.conclusion == "符合"


def test_sgs_lab_method_item_is_parsed() -> None:
    item = _parse_sgs_item_block(
        [
            "15",
            "#Δ泛酸",
            "mg/kg",
            "实验室方法LC-",
            "MSMS",
            "245",
            "0.20(mg",
            "/100 g)",
            "≥5.75",
            "符合",
        ]
    )

    assert item is not None
    assert item.name == "#Δ泛酸"
    assert item.method == "实验室方法LC- MSMS"
    assert item.value == "245"
    assert item.standard == "/100 g) ≥5.75"
    assert item.conclusion == "符合"


def test_sgs_wrapped_revision_method_is_not_parsed_as_result() -> None:
    item = _parse_sgs_item_block(
        [
            "7",
            "#Δ维生素",
            "B1（以硫胺",
            "素计）",
            "mg/kg",
            "参照GB 5009.84-",
            "2016 (含第1 号修改",
            "单) 第一法",
            "19.1",
            "0.10(mg",
            "/100 g)",
            "≥5.6",
            "符合",
        ]
    )

    assert item is not None
    assert item.name == "#Δ维生素B1（以硫胺素计）"
    assert item.method == "参照GB 5009.84- 2016 (含第1 号修改 单) 第一法"
    assert item.value == "19.1"


def test_sgs_chapter_method_is_not_parsed_as_result() -> None:
    item = _parse_sgs_item_block(
        [
            "29",
            "Δ碘（I）",
            "mg/kg",
            "GB/T 13882-2023",
            "第四章节",
            "4.87",
            "0.1(mg/",
            "kg)",
            "1.8~9.0",
            "符合",
        ]
    )

    assert item is not None
    assert item.name == "Δ碘（I）"
    assert item.method == "GB/T 13882-2023 第四章节"
    assert item.value == "4.87"


def test_sgs_q_standard_sensory_item_is_parsed() -> None:
    item = _parse_sgs_item_block(
        [
            "1",
            "色泽",
            "Q/371421QX001-",
            "2024",
            "具有产品固有的色泽",
            "具有产品固的色泽。",
            "符合",
        ]
    )

    assert item is not None
    assert item.name == "色泽"
    assert item.method == "Q/371421QX001- 2024"
    assert item.value == "具有产品固有的色泽"
    assert item.standard == "具有产品固的色泽。"
    assert item.conclusion == "符合"


def test_sgs_q_standard_wrapped_sensory_result_is_joined() -> None:
    item = _parse_sgs_item_block(
        [
            "2",
            "气味",
            "Q/371421QX001-",
            "2024",
            "具有本产品固有的气",
            "味，无异味",
            "具有本产品固有的气",
            "味，无异味。",
            "符合",
        ]
    )

    assert item is not None
    assert item.name == "气味"
    assert item.value == "具有本产品固有的气味，无异味"
    assert item.standard == "具有本产品固有的气味，无异味。"


def test_sgs_jjf_net_weight_item_is_parsed() -> None:
    item = _parse_sgs_item_block(
        [
            "5",
            "*净含量：",
            "单件净含量",
            "g",
            "JJF 1070-2023",
            "1805",
            "-",
            "-",
            "-",
        ]
    )

    assert item is not None
    assert item.name == "*净含量：单件净含量"
    assert item.unit == "g"
    assert item.method == "JJF 1070-2023"
    assert item.value == "1805"


def test_cti_simple_table_keeps_mg_per_100g_item_separate() -> None:
    text = dedent("""
    检测结果:
    序号
    检测项目
    单位
    检测结果
    检测方法
    1
    丙二醛
    mg/kg
    2.66
    GB/T 28717-2012
    2
    过氧化值
    g/100g
    0.053
    参考GB 5009.227-
    2023
    第一法
    3
    挥发性盐基氮
    mg/100g
    16.7
    参考GB 5009.228-
    2016
    第二法
    以下空白
    """)

    items = _extract_cti_items(text)

    assert [item.name for item in items] == ["丙二醛", "过氧化值", "挥发性盐基氮"]
    assert items[2].value == "16.7"
    assert items[2].unit == "mg/100g"
    assert items[2].method == "参考GB 5009.228- 2016 第二法"


def test_cti_net_content_kg_item_is_parsed() -> None:
    text = dedent("""
    检测结果：
    序号
    检验项目
    单位
    检测结果
    限量要求
    结论
    检测方法
    1
    净含量(单件定量
    包装商品)
    kg
    1.512
    ≥1.478
    符合
    JJF 1070-2023
    2
    黄曲霉毒素B₁
    μg/kg
    未检出(＜2)
    ≤10
    符合
    NY/T 2071-2011
    """)

    items = _extract_cti_items(text)

    assert items[0].name == "净含量(单件定量包装商品)"
    assert items[0].value == "1.512"
    assert items[0].unit == "kg"
    assert items[0].standard == "≥1.478"
    assert items[0].conclusion == "符合"


def test_cti_wrapped_sensory_text_is_joined_until_conclusion() -> None:
    text = dedent("""
    检测结果:
    序号
    检验项目
    单位
    检测结果
    限量要求
    结论
    检测方法
    1
    气味
    /
    具有产品固有的
    气味、无霉味及
    其它异味。
    具有产品固有的
    气味、无霉味及
    其它异味。
    符合
    Q/0613YZC008-2024
    """)

    items = _extract_cti_items(text)

    assert items[0].name == "气味"
    assert items[0].value == "具有产品固有的气味、无霉味及其它异味。"
    assert items[0].standard == "具有产品固有的气味、无霉味及其它异味。"
    assert items[0].conclusion == "符合"
    assert items[0].method == "Q/0613YZC008-2024"
