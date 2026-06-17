from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    dry_run: bool = True
    poll_interval_seconds: int = 60
    tmp_dir: Path = Path("data/tmp")
    template_config: Path = Path("config/templates.yaml")
    database_url: str = "sqlite:///data/report_store.db"
    report_pdf_dir: Path = Path("data/reports/pdf")
    detail_base_url: str = "http://127.0.0.1:8000"
    public_base_url: str = ""

    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_bitable_app_token: str = ""
    feishu_report_table_id: str = ""
    feishu_item_table_id: str = ""
    feishu_wide_table_id: str = ""
    feishu_upload_table_mode: str = "wide"
    feishu_bot_webhook: str = ""
    feishu_folder_token: str = ""
    feishu_output_bitable_name: str = "宠物食品检测报告解析结果"
    feishu_link_share_entity: str = "tenant_editable"
    feishu_archive_enabled: bool = False
    feishu_archive_config: Path = Path("config/archive_folders.csv")
    feishu_archive_rules: Path = Path("config/archive_rules.yaml")
    feishu_archive_root_token: str = ""
    feishu_archive_domain: str = "https://zb6okqgl47.feishu.cn"

    field_pdf: str = Field(default="PDF附件")
    field_status: str = Field(default="解析状态")
    field_error: str = Field(default="错误原因")
    field_report_no: str = Field(default="报告编号")
    field_sample_name: str = Field(default="样品名称")
    field_brand_name: str = Field(default="品牌名称")
    field_product_name: str = Field(default="产品名称")
    field_lab: str = Field(default="检测机构")
    field_client: str = Field(default="委托单位")
    field_report_date: str = Field(default="报告日期")
    field_conclusion: str = Field(default="报告结论")
    field_category: str = Field(default="产品分类")
    field_template: str = Field(default="解析模板")
    field_related_report: str = Field(default="关联报告")
    field_extra_info: str = Field(default="其他信息JSON")
    field_raw_text: str = Field(default="原文文本")
    field_item_extra_info: str = Field(default="明细额外信息JSON")
    field_detail_url: str = Field(default="详情页链接")
    field_archive_url: str = Field(default="归档文件链接")
    field_archive_path: str = Field(default="归档路径")
    field_archive_error: str = Field(default="归档错误")

    @property
    def database_path(self) -> Path:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError("Only sqlite:/// DATABASE_URL is supported in v1")
        return Path(self.database_url.removeprefix(prefix))

    def detail_url(self, record_id: str) -> str:
        base_url = self.public_base_url or self.detail_base_url
        return f"{base_url.rstrip('/')}/report/{record_id}"

    @property
    def feishu_enabled(self) -> bool:
        required = [
            self.feishu_app_id,
            self.feishu_app_secret,
            self.feishu_bitable_app_token,
            self.feishu_upload_table_id,
        ]
        return all(required)

    @property
    def feishu_upload_table_id(self) -> str:
        mode = self.feishu_upload_table_mode.strip().lower()
        if mode == "wide":
            return self.feishu_wide_table_id
        if mode == "report":
            return self.feishu_report_table_id
        raise ValueError("FEISHU_UPLOAD_TABLE_MODE only supports wide or report")

    @property
    def is_wide_upload_mode(self) -> bool:
        return self.feishu_upload_table_mode.strip().lower() == "wide"
