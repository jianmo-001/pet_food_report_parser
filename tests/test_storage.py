from pathlib import Path

from pdf_report_ingestor.models import ParsedReport, ReportItem
from pdf_report_ingestor.settings import Settings
from pdf_report_ingestor.storage import get_report, init_db, save_report_pdf, upsert_report


def test_upsert_report_replaces_items(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'reports.db'}",
        report_pdf_dir=tmp_path / "pdf",
        detail_base_url="http://example.test",
        public_base_url="",  # 显式清空，避免读到真实 .env 的 PUBLIC_BASE_URL
    )
    init_db(settings)
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF-1.4 test")
    saved_pdf = save_report_pdf(source_pdf, settings, "rec_123", "report.pdf")

    first = ParsedReport(
        report_no="R001",
        sample_name="样品A",
        lab="实验室",
        client="客户",
        report_date="2026-02-13",
        conclusion="合格",
        template_name="test",
        template_version="1.0",
        raw_text="raw",
        items=[ReportItem(name="水分", value="5.0", unit="%", standard="≤10", conclusion="符合")],
    )
    upsert_report(settings, "rec_123", first, saved_pdf, "report.pdf", settings.detail_url("rec_123"))

    second = ParsedReport(
        report_no="R001",
        sample_name="样品A",
        lab="实验室",
        client="客户",
        report_date="2026-02-13",
        conclusion="合格",
        template_name="test",
        template_version="1.0",
        raw_text="raw2",
        items=[
            ReportItem(name="粗蛋白", value="30", unit="%", standard="≥25", conclusion="符合"),
            ReportItem(name="水分", value="5.0", unit="%", standard="≤10", conclusion="符合"),
        ],
    )
    upsert_report(settings, "rec_123", second, saved_pdf, "report.pdf", settings.detail_url("rec_123"))

    data = get_report(settings, "rec_123")
    assert data is not None
    assert data["report"]["report_no"] == "R001"
    assert data["report"]["detail_url"] == "http://example.test/report/rec_123"
    assert len(data["items"]) == 2
    assert [item["item_name"] for item in data["items"]] == ["粗蛋白", "水分"]
    assert data["payload"]["raw_text"] == "raw2"
    assert data["wide"]["product_name"] == "样品A"
    assert "粗蛋白" in data["wide"]["wide_json"]
