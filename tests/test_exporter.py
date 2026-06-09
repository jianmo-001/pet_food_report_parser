from pdf_report_ingestor.exporter import to_main_fields
from pdf_report_ingestor.models import ParsedReport


def test_sgs_nested_sample_id_maps_to_main_sample_number() -> None:
    report = ParsedReport(
        report_no="ASH26-0011333-01",
        extra_fields={
            "检测样品描述": {
                "样品编号": "0001",
                "SGS样品ID": "ASH26-0011333-0001",
                "样品描述": "定型包装 包装完好",
            }
        },
    )

    assert to_main_fields(report)["样品编号"] == "ASH26-0011333-0001"


def test_date_period_maps_to_start_and_end_dates() -> None:
    report = ParsedReport(extra_fields={"检测周期": "2026年3月12日到2026年3月25日"})
    fields = to_main_fields(report)

    assert fields["检测开始日期"] == "2026-03-12"
    assert fields["检测结束日期"] == "2026-03-25"
    assert "检测周期" not in fields
