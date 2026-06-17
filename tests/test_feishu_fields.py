from pdf_report_ingestor.feishu import FeishuClient
from pdf_report_ingestor.settings import Settings


class FakeFieldClient(FeishuClient):
    def __init__(self) -> None:
        super().__init__(Settings(dry_run=True))
        self.created: list[tuple[str, int]] = []

    def list_table_fields(self, app_token: str, table_id: str) -> list[dict[str, object]]:
        return [{"field_name": "产品名称"}]

    def create_table_field(self, app_token: str, table_id: str, field_name: str, field_type: int = 1) -> str | None:
        self.created.append((field_name, field_type))
        return f"fld_{field_name}"


def test_ensure_table_fields_skips_existing_and_uses_date_type() -> None:
    client = FakeFieldClient()

    result = client.ensure_table_fields("app", "tbl", ["产品名称", "PDF附件", "报告日期", "粗蛋白"])

    assert result["skipped"] == ["产品名称"]
    assert result["created"] == ["PDF附件", "报告日期", "粗蛋白"]
    assert client.created == [("PDF附件", 17), ("报告日期", 5), ("粗蛋白", 1)]
