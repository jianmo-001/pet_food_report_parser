from pdf_report_ingestor.templates import TemplateRule, extract_report, select_template


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
