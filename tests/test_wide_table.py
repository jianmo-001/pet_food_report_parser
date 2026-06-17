from pdf_report_ingestor.models import ParsedReport, ReportItem
from pdf_report_ingestor.wide_table import (
    WIDE_ATTACHMENT_FIELDS,
    WIDE_DATE_FIELDS,
    build_wide_row,
    normalize_item_name,
    split_brand_product,
    wide_field_names,
)


def test_split_brand_product() -> None:
    assert split_brand_product("诚实一口®全价高鲜肉烘焙猫粮") == ("诚实一口", "诚实一口®全价高鲜肉烘焙猫粮")
    assert split_brand_product("无品牌样品") == (None, "无品牌样品")


def test_normalize_item_aliases() -> None:
    assert normalize_item_name("钙#") == "钙"
    assert normalize_item_name("钙（Ca）（以干基计）") == "钙"
    assert normalize_item_name("Calcium 钙 (on dry basis 以干基计)") == "钙"
    assert normalize_item_name("Cadmium 镉 (As dry matter content of 88% 以干物质含量88%计)") == "镉"
    assert normalize_item_name("亚硝酸盐（以亚硝酸钠计）(干物质含量88%计)") == "亚硝酸盐"
    assert normalize_item_name("HT-2毒素") == "HT-2毒素"
    assert normalize_item_name("T-2、HT-2毒素之和(以88%干物质计)") == "T-2毒素+HT-2毒素"
    assert normalize_item_name("淀粉糊化度") == "淀粉糊化度"
    assert normalize_item_name("六六六(HCH)(以干物质含量88%计)β-六六六(以干物质含量88%计)") == "β-HCH"
    assert normalize_item_name("六六六(HCH)(以干物质含量88%计)δ-六六六(以干物质含量88%计)") == "δ-HCH"
    assert normalize_item_name("(亚油酸+花生四烯):(亚麻酸+EPA+DHA)ª") == "脂肪酸比例"
    assert normalize_item_name("粗蛋白质(以干物质计)#") == "粗蛋白"
    assert normalize_item_name("Crude protein (on dry basis 以干基计)") == "粗蛋白"
    assert normalize_item_name("钙磷比值(以干基计)ª") == "钙磷比"
    assert normalize_item_name("维生素B₆(以干基计)ª*1") == "维生素B6"
    assert normalize_item_name("水溶性氯化物（以Cl-计）（以干基计）") == "氯化物"


def test_build_wide_row_values_and_unmapped_items() -> None:
    report = ParsedReport(
        report_no="R001",
        sample_name="诚实一口®测试产品",
        lab="测试机构",
        report_date="2026-06-10",
        items=[
            ReportItem(name="粗蛋白（以干基计）", value="46.94", unit="%"),
            ReportItem(name="维生素A(以干基计)ª", value="3.43×10^4", unit="IU/kg"),
            ReportItem(name="未知项目", value="1", unit="mg/kg"),
        ],
    )
    row = build_wide_row(report, "demo.pdf", "http://127.0.0.1:8000/report/rec001")

    assert row["品牌名称"] == "诚实一口"
    assert row["产品名称"] == "诚实一口®测试产品"
    assert row["粗蛋白（%）"] == "46.94"
    assert row["维生素A（IU/kg）"] == "3.43×10^4"
    assert "未知项目" in row["未映射检测项目JSON"]


def test_wide_field_names_include_required_fields() -> None:
    fields = wide_field_names()

    assert fields[0] == "产品名称"
    assert "PDF文件名" in fields
    assert "PDF附件" in fields
    assert "解析状态" in fields
    assert "错误原因" in fields
    assert "归档文件链接" in fields
    assert "归档错误" in fields
    assert "品牌名称" in fields
    assert "粗蛋白（%）" in fields
    assert "维生素A（IU/kg）" in fields
    assert "未映射检测项目JSON" in fields
    assert "δ-HCH（μg/kg）" in fields
    assert WIDE_DATE_FIELDS == {"报告日期", "样品接收日期", "检测开始日期", "检测结束日期"}
    assert WIDE_ATTACHMENT_FIELDS == {"PDF附件"}


def test_conflicting_unit_field_keeps_unit_in_value() -> None:
    report = ParsedReport(items=[ReportItem(name="淀粉", value="134", unit="g/kg")])
    row = build_wide_row(report)

    assert row["淀粉"] == "134 g/kg"


def test_net_content_kg_is_converted_to_grams_for_wide_field() -> None:
    report = ParsedReport(items=[ReportItem(name="净含量(单件定量包装商品)", value="1.512", unit="kg")])
    row = build_wide_row(report)

    assert row["净含量（g）"] == "1512"
