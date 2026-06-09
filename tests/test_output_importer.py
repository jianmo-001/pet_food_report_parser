from pathlib import Path

from pdf_report_ingestor.output_importer import _field_names, _read_csv_files


def test_read_exported_output_csv() -> None:
    output_dir = Path("output")
    if not output_dir.exists():
        return

    main_rows = _read_csv_files(output_dir, "*/*_main.csv")
    item_rows = _read_csv_files(output_dir, "*/*_items.csv")

    assert len(main_rows) == 4
    assert len(item_rows) == 60
    assert "报告编号" in _field_names(main_rows)
    assert "检测项目" in _field_names(item_rows)
