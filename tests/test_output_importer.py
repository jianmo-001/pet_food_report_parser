from pathlib import Path

from pdf_report_ingestor.output_importer import _field_names, _read_csv_files


def test_read_exported_output_csv(tmp_path: Path) -> None:
    # 自建临时 output 夹具，避免读到真实 output/ 里累积的几百份结果
    out = tmp_path / "output"
    (out / "SGS").mkdir(parents=True)
    (out / "SGS" / "R1_main.csv").write_text(
        "报告编号,产品名称\nR1,产品A\n", encoding="utf-8-sig"
    )
    (out / "SGS" / "R1_items.csv").write_text(
        "检测项目,检测结果\n水分,5.0\n粗蛋白,30\n", encoding="utf-8-sig"
    )

    main_rows = _read_csv_files(out, "*/*_main.csv")
    item_rows = _read_csv_files(out, "*/*_items.csv")

    assert len(main_rows) == 1
    assert len(item_rows) == 2
    assert "报告编号" in _field_names(main_rows)
    assert "检测项目" in _field_names(item_rows)
