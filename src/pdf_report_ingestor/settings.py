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

    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_bitable_app_token: str = ""
    feishu_report_table_id: str = ""
    feishu_item_table_id: str = ""
    feishu_bot_webhook: str = ""
    feishu_folder_token: str = ""
    feishu_output_bitable_name: str = "宠物食品检测报告解析结果"
    feishu_link_share_entity: str = "tenant_editable"

    field_pdf: str = Field(default="PDF附件")
    field_status: str = Field(default="解析状态")
    field_error: str = Field(default="错误原因")
    field_report_no: str = Field(default="报告编号")
    field_sample_name: str = Field(default="样品名称")
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

    @property
    def feishu_enabled(self) -> bool:
        required = [
            self.feishu_app_id,
            self.feishu_app_secret,
            self.feishu_bitable_app_token,
            self.feishu_report_table_id,
            self.feishu_item_table_id,
        ]
        return all(required)
