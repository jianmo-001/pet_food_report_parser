from pathlib import Path

from fastapi.testclient import TestClient

from pdf_report_ingestor.models import ParsedReport, ReportItem
from pdf_report_ingestor.settings import Settings
from pdf_report_ingestor.storage import save_report_pdf, upsert_report


def test_report_page_and_pdf_endpoint(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'reports.db'}")
    monkeypatch.setenv("REPORT_PDF_DIR", str(tmp_path / "pdf"))
    monkeypatch.setenv("DETAIL_BASE_URL", "http://example.test")
    settings = Settings()
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF-1.4 test")
    saved_pdf = save_report_pdf(source_pdf, settings, "rec_web", "report.pdf")
    report = ParsedReport(
        report_no="R-WEB",
        sample_name="网页测试样品",
        lab="测试实验室",
        template_name="test",
        template_version="1.0",
        raw_text="raw",
        items=[ReportItem(name="水分", value="5.0", unit="%", conclusion="符合")],
    )
    upsert_report(settings, "rec_web", report, saved_pdf, "report.pdf", settings.detail_url("rec_web"))

    from pdf_report_ingestor.web import create_app

    client = TestClient(create_app())
    page = client.get("/report/rec_web")
    assert page.status_code == 200
    assert "网页测试样品" in page.text
    assert "水分" in page.text

    pdf = client.get("/pdf/rec_web")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["content-disposition"] == "inline"
