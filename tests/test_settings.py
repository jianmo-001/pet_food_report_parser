from pdf_report_ingestor.settings import Settings


def test_wide_upload_mode_uses_wide_table() -> None:
    settings = Settings(
        dry_run=False,
        feishu_app_id="app",
        feishu_app_secret="secret",
        feishu_bitable_app_token="base",
        feishu_report_table_id="tbl_report",
        feishu_wide_table_id="tbl_wide",
        feishu_upload_table_mode="wide",
    )

    assert settings.feishu_upload_table_id == "tbl_wide"
    assert settings.is_wide_upload_mode is True
    assert settings.feishu_enabled is True


def test_report_upload_mode_uses_report_table() -> None:
    settings = Settings(
        dry_run=False,
        feishu_app_id="app",
        feishu_app_secret="secret",
        feishu_bitable_app_token="base",
        feishu_report_table_id="tbl_report",
        feishu_wide_table_id="tbl_wide",
        feishu_upload_table_mode="report",
    )

    assert settings.feishu_upload_table_id == "tbl_report"
    assert settings.is_wide_upload_mode is False
    assert settings.feishu_enabled is True


def test_public_base_url_overrides_detail_base_url() -> None:
    settings = Settings(
        detail_base_url="http://127.0.0.1:8000",
        public_base_url="http://123.57.19.15",
    )

    assert settings.detail_url("rec001") == "http://123.57.19.15/report/rec001"
