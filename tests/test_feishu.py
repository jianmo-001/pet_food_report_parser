from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
import requests

from pdf_report_ingestor.feishu import FeishuClient, _convert_dates
from pdf_report_ingestor.models import PendingReport
from pdf_report_ingestor.settings import Settings


def test_convert_dates_to_feishu_milliseconds() -> None:
    row = _convert_dates({"报告日期": "2026-02-13", "样品接收日期": "2026-02-04"})

    expected_report_date = datetime(2026, 2, 13, tzinfo=ZoneInfo("Asia/Shanghai"))
    expected_receive_date = datetime(2026, 2, 4, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert row["报告日期"] == int(expected_report_date.timestamp() * 1000)
    assert row["样品接收日期"] == int(expected_receive_date.timestamp() * 1000)
    assert row["报告日期"] > 1_000_000_000_000


def test_start_and_end_dates_convert_to_feishu_milliseconds() -> None:
    row = _convert_dates({"检测开始日期": "2026-02-04", "检测结束日期": "2026-02-13"})

    expected_start_date = datetime(2026, 2, 4, tzinfo=ZoneInfo("Asia/Shanghai"))
    expected_end_date = datetime(2026, 2, 13, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert row["检测开始日期"] == int(expected_start_date.timestamp() * 1000)
    assert row["检测结束日期"] == int(expected_end_date.timestamp() * 1000)


def test_download_attachment_retries_retryable_server_error(monkeypatch, tmp_path) -> None:
    settings = Settings(dry_run=False, tmp_dir=tmp_path, feishu_app_id="app", feishu_app_secret="secret")
    client = FeishuClient(settings)
    client._tenant_access_token = "token"
    calls = []

    def fake_get(url, headers, params, timeout):
        calls.append((url, headers, params, timeout))
        response = requests.Response()
        response.status_code = 500 if len(calls) == 1 else 200
        response._content = b"" if response.status_code == 500 else b"%PDF-1.5"
        return response

    monkeypatch.setattr("pdf_report_ingestor.feishu.requests.get", fake_get)
    monkeypatch.setattr("pdf_report_ingestor.feishu.time.sleep", lambda _: None)

    downloaded = client.download_attachment(PendingReport(record_id="rec", attachment_token="tok", file_name="demo.pdf"))

    assert downloaded.path.read_bytes() == b"%PDF-1.5"
    assert len(calls) == 2


def test_download_attachment_does_not_retry_permission_error(monkeypatch, tmp_path) -> None:
    settings = Settings(dry_run=False, tmp_dir=tmp_path, feishu_app_id="app", feishu_app_secret="secret")
    client = FeishuClient(settings)
    client._tenant_access_token = "token"
    calls = []

    def fake_get(url, headers, params, timeout):
        calls.append(url)
        response = requests.Response()
        response.status_code = 403
        response._content = b"forbidden"
        return response

    monkeypatch.setattr("pdf_report_ingestor.feishu.requests.get", fake_get)

    with pytest.raises(requests.HTTPError):
        client.download_attachment(PendingReport(record_id="rec", attachment_token="tok", file_name="demo.pdf"))

    assert len(calls) == 1


def test_find_file_in_folder_matches_name_and_size(monkeypatch) -> None:
    settings = Settings(dry_run=False, feishu_app_id="app", feishu_app_secret="secret")
    client = FeishuClient(settings)

    monkeypatch.setattr(
        client,
        "list_folder_files",
        lambda folder_token: [
            {"name": "demo.pdf", "token": "wrong_size", "size": "10"},
            {"name": "demo.pdf", "token": "matched", "size": "4"},
            {"name": "other.pdf", "token": "other", "size": "4"},
        ],
    )

    assert client.find_file_in_folder("folder", "demo.pdf", 4) == "matched"
    assert client.find_file_in_folder("folder", "demo.pdf", 99) is None
