from __future__ import annotations

import logging
import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests

from .exporter import to_main_fields
from .models import DownloadedFile, ParsedReport, PendingReport, ReportItem
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

        records = self._list_records()
        pending: list[PendingReport] = []
        for record in records:
            fields = record.get("fields") or {}
            status = _field_text(fields.get(self.settings.field_status))
            attachments = _attachment_list(fields.get(self.settings.field_pdf))
            if status not in {"未解析", "待解析", ""}:
                continue
            if not attachments:
                continue
            attachment = attachments[0]
            attachment_token = (
                attachment.get("file_token")
                or attachment.get("token")
                or attachment.get("attachmentToken")
                or attachment.get("attachment_token")
            )
            if not attachment_token:
                logger.warning("skip record=%s: attachment token missing", record.get("record_id"))
                continue
            pending.append(
                PendingReport(
                    record_id=record["record_id"],
                    attachment_token=str(attachment_token),
                    file_name=attachment.get("name") or attachment.get("file_name") or f'{record["record_id"]}.pdf',
                    extra=attachment.get("extra"),
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
        params = {"extra": pending.extra} if pending.extra else None
        response = requests.get(url, headers=self._auth_headers(), params=params, timeout=60)
        response.raise_for_status()
        output.write_bytes(response.content)
        return DownloadedFile(path=output, file_name=pending.file_name)

    def mark_processing(self, record_id: str) -> None:
        self.update_report_record(record_id, {self.settings.field_status: "解析中", self.settings.field_error: ""})

    def write_success(self, record_id: str, report: ParsedReport, pdf_file_name: str | None = None) -> None:
        report_fields = {
            **to_main_fields(report, pdf_file_name),
            self.settings.field_status: "解析成功",
            self.settings.field_error: "",
            self.settings.field_raw_text: report.raw_text[:20000],
            self.settings.field_extra_info: json.dumps(report.extra_fields, ensure_ascii=False),
        }
        report_fields.pop(self.settings.field_pdf, None)
        self.update_report_record(record_id, _map_field_names(_convert_numbers(_convert_dates(_clean_record_fields(report_fields)))))

        item_records = [_item_row(report.report_no, index, item) for index, item in enumerate(report.items, 1)]
        if item_records:
            self.batch_create_records(self.settings.feishu_bitable_app_token, self.settings.feishu_item_table_id, item_records)

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

    def create_bitable_app(self, name: str, folder_token: str | None = None) -> str:
        if self.settings.dry_run:
            logger.info("dry-run: create bitable app name=%s folder_token=%s", name, folder_token)
            return "dry_run_app_token"
        url = "https://open.feishu.cn/open-apis/bitable/v1/apps"
        payload: dict[str, Any] = {"name": name}
        if folder_token:
            payload["folder_token"] = folder_token
        response = requests.post(url, headers=self._json_headers(), json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        self._ensure_ok(data)
        app_token = _find_key(data, "app_token") or _find_key(data, "token")
        if not app_token:
            raise RuntimeError(f"Feishu API response missing app_token: {data}")
        return str(app_token)

    def create_table(self, app_token: str, table_name: str, field_names: list[str]) -> str:
        fields = [{"field_name": field_name, "type": 1} for field_name in field_names]
        if self.settings.dry_run:
            logger.info("dry-run: create table app_token=%s table=%s fields=%d", app_token, table_name, len(fields))
            return f"dry_run_{table_name}"
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables"
        response = requests.post(
            url,
            headers=self._json_headers(),
            json={"table": {"name": table_name, "default_view_name": "默认视图", "fields": fields}},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        self._ensure_ok(data)
        table_id = _find_key(data, "table_id")
        if not table_id:
            raise RuntimeError(f"Feishu API response missing table_id: {data}")
        return str(table_id)

    def batch_create_records(self, app_token: str, table_id: str, rows: list[dict[str, Any]], batch_size: int = 500) -> int:
        total = 0
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            records = [{"fields": _map_field_names(_convert_numbers(_convert_dates(_clean_record_fields(row))))} for row in batch]
            if self.settings.dry_run:
                logger.info("dry-run: create %d records app_token=%s table_id=%s", len(records), app_token, table_id)
                total += len(records)
                continue
            url = (
                "https://open.feishu.cn/open-apis/bitable/v1/apps/"
                f"{app_token}/tables/{table_id}/records/batch_create"
            )
            response = requests.post(url, headers=self._json_headers(), json={"records": records}, timeout=60)
            response.raise_for_status()
            self._ensure_ok(response.json())
            total += len(records)
        return total

    def set_bitable_link_permission(self, app_token: str, link_share_entity: str) -> dict[str, Any]:
        if not link_share_entity:
            return {}
        payload = _permission_payload(link_share_entity)
        if self.settings.dry_run:
            logger.info("dry-run: set bitable permission app_token=%s payload=%s", app_token, payload)
            return {"permission_public": payload}
        url = f"https://open.feishu.cn/open-apis/drive/v1/permissions/{app_token}/public?type=bitable"
        response = requests.patch(url, headers=self._json_headers(), json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        self._ensure_ok(data)
        return data.get("data", {})

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

    def _list_records(self) -> list[dict[str, Any]]:
        url = (
            "https://open.feishu.cn/open-apis/bitable/v1/apps/"
            f"{self.settings.feishu_bitable_app_token}/tables/{self.settings.feishu_report_table_id}/records/search"
        )
        records: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            payload: dict[str, Any] = {
                "filter": {"conjunction": "and", "conditions": []},
                "automatic_fields": False,
                "page_size": 500,
            }
            if page_token:
                payload["page_token"] = page_token
            response = requests.post(url, headers=self._json_headers(), json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            self._ensure_ok(data)
            page = data.get("data", {})
            records.extend(page.get("items", []))
            if not page.get("has_more"):
                return records
            page_token = page.get("page_token")

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


def _clean_record_fields(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if value not in (None, "")}


def _field_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value).strip()
    if isinstance(value, list):
        return "".join(_field_text(item) for item in value).strip()
    if isinstance(value, dict):
        for key in ("text", "name", "value"):
            if key in value:
                return _field_text(value[key])
    return str(value).strip()


def _attachment_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _item_row(report_no: str | None, index: int, item: ReportItem) -> dict[str, Any]:
    loq = item.extra_fields.get("定量限") or item.extra_fields.get("定量限/检出限") or item.extra_fields.get("报告检出限")
    return {
        "关联报告": report_no,
        "序号": index,
        "检测项目": item.name,
        "单位": item.unit,
        "检测方法": item.method,
        "检测结果": item.value,
        "定量限/检出限": loq,
        "限值": item.standard,
        "单项结论": item.conclusion,
        "明细额外信息JSON": json.dumps(item.extra_fields, ensure_ascii=False),
        "来源文本片段": item.source_text,
    }


FEISHU_DATE_FIELDS = {"报告日期", "样品接收日期", "检测开始日期", "检测结束日期", "生产日期"}


def _convert_dates(row: dict[str, Any]) -> dict[str, Any]:
    """Convert YYYY-MM-DD date strings to Unix timestamps in milliseconds for Feishu date fields."""
    result = dict(row)
    for field in FEISHU_DATE_FIELDS:
        value = result.get(field)
        if value and isinstance(value, str) and len(value) >= 10:
            try:
                date_value = datetime.strptime(value[:10], "%Y-%m-%d").date()
                dt = datetime.combine(date_value, datetime.min.time(), ZoneInfo("Asia/Shanghai"))
                result[field] = int(dt.timestamp() * 1000)
            except (ValueError, OSError):
                pass
    return result


NUMBER_FIELDS = {"检测项目数量", "序号"}


def _convert_numbers(row: dict[str, Any]) -> dict[str, Any]:
    """Convert numeric string fields to actual numbers."""
    result = dict(row)
    for field in NUMBER_FIELDS:
        value = result.get(field)
        if value is not None:
            try:
                result[field] = int(value)
            except (ValueError, TypeError):
                pass
    return result


# CSV字段名 -> 飞书字段名 映射
FIELD_NAME_MAP = {
    "定量限/检出限": "定量限|检出限",
}


def _map_field_names(row: dict[str, Any]) -> dict[str, Any]:
    """Rename fields to match Feishu field names."""
    result = {}
    for key, value in row.items():
        new_key = FIELD_NAME_MAP.get(key, key)
        result[new_key] = value
    return result


def _find_key(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for child in value.values():
            found = _find_key(child, key)
            if found is not None:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_key(child, key)
            if found is not None:
                return found
    return None


def _permission_payload(link_share_entity: str) -> dict[str, Any]:
    payload: dict[str, Any] = {"link_share_entity": link_share_entity}
    if link_share_entity.startswith("anyone_"):
        payload["external_access"] = True
        payload["invite_external"] = True
        payload["share_entity"] = "anyone"
    return payload
