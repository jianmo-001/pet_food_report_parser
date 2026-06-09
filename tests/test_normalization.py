from pdf_report_ingestor.normalization import normalize_date, normalize_date_range, split_date_range


def test_normalize_date_formats() -> None:
    assert normalize_date("2026-02-13") == "2026-02-13"
    assert normalize_date("2026 年04 月07 日") == "2026-04-07"
    assert normalize_date("2026年3月25日") == "2026-03-25"
    assert normalize_date("2025.12.19") == "2025-12-19"
    assert normalize_date("20260328") == "2026-03-28"


def test_normalize_date_range_formats() -> None:
    assert normalize_date_range("2026-02-04 ~ 2026-02-13") == "2026-02-04 ~ 2026-02-13"
    assert normalize_date_range("2026 年03 月30 日～2026 年04 月07 日") == "2026-03-30 ~ 2026-04-07"
    assert normalize_date_range("2026年3月12日到2026年3月25日") == "2026-03-12 ~ 2026-03-25"


def test_split_date_range_formats() -> None:
    assert split_date_range("2026-02-04 ~ 2026-02-13") == ("2026-02-04", "2026-02-13")
    assert split_date_range("2026 年03 月30 日～2026 年04 月07 日") == ("2026-03-30", "2026-04-07")
    assert split_date_range("2026年3月12日到2026年3月25日") == ("2026-03-12", "2026-03-25")
