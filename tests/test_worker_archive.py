import os
from pathlib import Path

from pdf_report_ingestor.models import ParsedReport
from pdf_report_ingestor.settings import Settings
from pdf_report_ingestor.worker import archive_pdf

RULES = Path("config/archive_rules.yaml").resolve()


class FakeArchiveClient:
    def __init__(self, top_folders: dict[str, str] | None = None) -> None:
        self.top_folders = top_folders or {}
        self.uploads: list[tuple[Path, str, str]] = []
        self.updates: list[tuple[str, str, dict[str, str]]] = []
        self.existing_file_token: str | None = None
        self.finds: list[tuple[str, str, int | None]] = []

    def list_subfolders(self, folder_token: str) -> dict[str, str]:
        # 顶层返回配置好的产品文件夹；二级一律返回空 → 触发回落根目录
        return self.top_folders if folder_token == "root" else {}

    def find_file_in_folder(self, folder_token: str, file_name: str, file_size: int | None = None) -> str | None:
        self.finds.append((folder_token, file_name, file_size))
        return self.existing_file_token

    def upload_file_to_folder(self, path: Path, file_name: str, folder_token: str) -> str:
        self.uploads.append((path, file_name, folder_token))
        return "uploaded_token"

    def update_record(self, table_id: str, record_id: str, fields: dict[str, str]) -> None:
        self.updates.append((table_id, record_id, fields))


def test_archive_pdf_skips_existing_archive_url(tmp_path: Path) -> None:
    client = FakeArchiveClient()
    settings = Settings(feishu_archive_enabled=True, feishu_archive_root_token="root")

    archive_pdf(
        client,  # type: ignore[arg-type]
        settings,
        "rec001",
        ParsedReport(sample_name="诚实一口®BK01"),
        tmp_path / "demo.pdf",
        "demo.pdf",
        existing_archive_url="https://example.feishu.cn/file/old",
    )

    assert client.uploads == []
    assert client.updates == []


def test_archive_pdf_writes_archive_error_when_unmatched(tmp_path: Path) -> None:
    client = FakeArchiveClient(top_folders={})
    settings = Settings(
        feishu_archive_enabled=True,
        feishu_archive_rules=RULES,
        feishu_archive_root_token="root",
        feishu_wide_table_id="tbl",
    )
    cwd = os.getcwd()
    os.chdir(tmp_path)  # 让“未匹配清单”落在临时目录，避免污染仓库
    try:
        archive_pdf(
            client,  # type: ignore[arg-type]
            settings,
            "rec001",
            ParsedReport(sample_name="诚实一口®神秘新品"),
            tmp_path / "demo.pdf",
            "demo.pdf",
        )
    finally:
        os.chdir(cwd)

    assert client.uploads == []
    assert client.updates[0][0] == "tbl"
    assert client.updates[0][1] == "rec001"
    assert "未匹配到归档文件夹" in client.updates[0][2]["归档错误"]
    assert (tmp_path / "output" / "archive_unmatched.csv").exists()


def test_archive_pdf_reuses_existing_file_and_writes_path(tmp_path: Path) -> None:
    client = FakeArchiveClient(top_folders={"BK01 & BK01Plus & BN01": "folder_bk01"})
    client.existing_file_token = "existing_token"
    pdf = tmp_path / "demo.pdf"
    pdf.write_bytes(b"demo")
    settings = Settings(
        feishu_archive_enabled=True,
        feishu_archive_rules=RULES,
        feishu_archive_root_token="root",
        feishu_wide_table_id="tbl",
        feishu_archive_domain="https://example.feishu.cn",
    )

    archive_pdf(
        client,  # type: ignore[arg-type]
        settings,
        "rec001",
        ParsedReport(sample_name="诚实一口®BK01全价猫粮"),
        pdf,
        "20260511-基础项-诚实一口®BK01全价猫粮.pdf",
    )

    assert client.finds == [("folder_bk01", "20260511-基础项-诚实一口®BK01全价猫粮.pdf", 4)]
    assert client.uploads == []
    table_id, record_id, fields = client.updates[0]
    assert (table_id, record_id) == ("tbl", "rec001")
    assert fields["归档路径"] == "诚实一口大货报告/BK01 & BK01Plus & BN01"
    assert fields["归档文件链接"] == "https://example.feishu.cn/file/existing_token"
    assert fields["归档错误"] == ""
