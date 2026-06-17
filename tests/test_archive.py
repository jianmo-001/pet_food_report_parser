from pathlib import Path

import pytest

from pdf_report_ingestor.archive import archived_file_url, load_archive_rules, select_archive_rule
from pdf_report_ingestor.models import ParsedReport


def test_load_archive_rules_and_select_longest_keyword(tmp_path: Path) -> None:
    config = tmp_path / "archive.csv"
    config.write_text(
        "brand,product_keyword,folder_token,folder_name\n"
        "诚实一口,BK01,folder_short,BK01\n"
        "诚实一口,BK01 PLUS,folder_long,BK01 PLUS\n",
        encoding="utf-8",
    )

    rules = load_archive_rules(config)
    report = ParsedReport(sample_name="诚实一口®BK01 PLUS 全阶段全价烘焙猫粮")

    selected = select_archive_rule(report, rules)

    assert selected.folder_token == "folder_long"


def test_select_archive_rule_raises_for_missing_mapping() -> None:
    report = ParsedReport(sample_name="诚实一口®未知产品")

    with pytest.raises(RuntimeError, match="未找到归档目录映射"):
        select_archive_rule(report, [])


def test_archived_file_url_uses_file_token() -> None:
    assert archived_file_url("https://example.feishu.cn/", "file_token") == "https://example.feishu.cn/file/file_token"
