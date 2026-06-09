from datetime import datetime
from zoneinfo import ZoneInfo

from pdf_report_ingestor.feishu import _convert_dates


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
