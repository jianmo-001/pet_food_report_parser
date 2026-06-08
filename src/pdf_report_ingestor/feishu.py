from __future__ import annotations

import logging
import json
from pathlib import Path
from typing import Any

import requests

from .models import DownloadedFile, ParsedReport, PendingReport
from .settings import Settings

logger = logging.getLogger(__name__)


class FeishuClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._tenant_access_token: str | None = None

    def list_pending_reports(self) -> list[PendingReport]:
        if self.settings.dry_run or not self.settings.feishu_enabled:
            logger.info("dry-run: skip listing pending Feishu records")
            return []

        records = self._list_records(filter_text='CurrentValue.[解析状态] = "待解析"')
        pending: list[PendingReport] = []
        for record in records:
            fields = record.get("fields") or {}
            attachments = fields.get(self.settings.field_pdf) or []
            if not attachments:
                continue
            attachment = attachments[0]
            pending.append(
                PendingReport(
                    record_id=record["record_id"],
                    attachment_token=attachment.get("file_token") or attachment.get("token"),
                    file_name=attachment.get("name") or f'{record["record_id"]}.pdf',
                )
            )
        return pending

    def download_attachment(self, pending: PendingReport) -> DownloadedFile:
        if not pending.attachment_token:
            raise RuntimeError("附件 token 为空")

        self.settings.tmp_dir.mkdir(parents=True, exist_ok=True)
        output = self.settings.tmp_dir / pending.file_name
        url = (
            "https://open.feishu.cn/open-apis/drive/v1/medias/"
            f"{pending.attachment_token}/download"
        )
        response = requests.get(url, headers=self._auth_headers(), timeout=60)
        response.raise_for_status()
        output.write_bytes(response.content)
        return DownloadedFile(path=output, file_name=pending.file_name)

    def mark_processing(self, record_id: str) -> None:
        self.update_report_record(record_id, {self.settings.field_status: "解析中", self.settings.field_error: ""})

    def write_success(self, record_id: str, report: ParsedReport) -> None:
        report_fields = {
            self.settings.field_status: "解析成功",
            self.settings.field_error: "",
            self.settings.field_report_no: report.report_no,
            self.settings.field_sample_name: report.sample_name,
            self.settings.field_lab: report.lab,
            self.settings.field_client: report.client,
            self.settings.field_report_date: report.report_date,
            self.settings.field_conclusion: report.conclusion,
            self.settings.field_category: report.category,
            self.settings.field_template: _template_label(report),
            self.settings.field_extra_info: json.dumps(report.extra_fields, ensure_ascii=False),
            self.settings.field_raw_text: report.raw_text[:20000],
        }
        self.update_report_record(record_id, {key: value for key, value in report_fields.items() if value is not None})

        item_records = []
        for item in report.items:
            item_records.append(
                {
                    "fields": {
                        self.settings.field_related_report: [record_id],
                        "检测项目": item.name,
                        "检测值": item.value,
                        "单位": item.unit,
                        "标准要求": item.standard,
                        "检测方法": item.method,
                        "单项结论": item.conclusion,
                        "来源页码": item.source_page,
                        "来源文本片段": item.source_text,
                        self.settings.field_item_extra_info: json.dumps(item.extra_fields, ensure_ascii=False),
                    }
                }
            )
        if item_records:
            self.batch_create_item_records(item_records)

    def write_failure(self, record_id: str, error: str) -> None:
        self.update_report_record(record_id, {self.settings.field_status: "解析失败", self.settings.field_error: error})
        self.notify(f"检测报告解析失败\nrecord_id: {record_id}\n原因: {error}")

    def update_report_record(self, record_id: str, fields: dict[str, Any]) -> None:
        if self.settings.dry_run or not self.settings.feishu_enabled:
            logger.info("dry-run: update report %s fields=%s", record_id, fields)
            return
        url = self._record_url(self.settings.feishu_report_table_id, record_id)
        response = requests.put(url, headers=self._json_headers(), json={"fields": fields}, timeout=30)
        response.raise_for_status()
        self._ensure_ok(response.json())

    def batch_create_item_records(self, records: list[dict[str, Any]]) -> None:
        if self.settings.dry_run or not self.settings.feishu_enabled:
            logger.info("dry-run: create %d item records", len(records))
            return
        url = (
            "https://open.feishu.cn/open-apis/bitable/v1/apps/"
            f"{self.settings.feishu_bitable_app_token}/tables/{self.settings.feishu_item_table_id}/records/batch_create"
        )
        response = requests.post(url, headers=self._json_headers(), json={"records": records}, timeout=30)
        response.raise_for_status()
        self._ensure_ok(response.json())

    def notify(self, text: str) -> None:
        if not self.settings.feishu_bot_webhook:
            logger.info("bot webhook not configured: %s", text)
            return
        response = requests.post(
            self.settings.feishu_bot_webhook,
            json={"msg_type": "text", "content": {"text": text}},
            timeout=15,
        )
        response.raise_for_status()

    def _tenant_token(self) -> str:
        if self._tenant_access_token:
            return self._tenant_access_token
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        response = requests.post(
            url,
            json={"app_id": self.settings.feishu_app_id, "app_secret": self.settings.feishu_app_secret},
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        self._ensure_ok(data)
        self._tenant_access_token = data["tenant_access_token"]
        return self._tenant_access_token

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._tenant_token()}"}

    def _json_headers(self) -> dict[str, str]:
        return {**self._auth_headers(), "Content-Type": "application/json; charset=utf-8"}

    def _list_records(self, filter_text: str) -> list[dict[str, Any]]:
        url = (
            "https://open.feishu.cn/open-apis/bitable/v1/apps/"
            f"{self.settings.feishu_bitable_app_token}/tables/{self.settings.feishu_report_table_id}/records/search"
        )
        response = requests.post(
            url,
            headers=self._json_headers(),
            json={"filter": {"conjunction": "and", "conditions": []}, "automatic_fields": False},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        self._ensure_ok(data)
        records = data.get("data", {}).get("items", [])
        return [record for record in records if (record.get("fields") or {}).get(self.settings.field_status) == "待解析"]

    def _record_url(self, table_id: str, record_id: str) -> str:
        return (
            "https://open.feishu.cn/open-apis/bitable/v1/apps/"
            f"{self.settings.feishu_bitable_app_token}/tables/{table_id}/records/{record_id}"
        )

    @staticmethod
    def _ensure_ok(data: dict[str, Any]) -> None:
        if data.get("code", 0) != 0:
            raise RuntimeError(f"Feishu API error: {data}")


def _template_label(report: ParsedReport) -> str | None:
    if not report.template_name:
        return None
    if report.template_version:
        return f"{report.template_name}@{report.template_version}"
    return report.template_name
