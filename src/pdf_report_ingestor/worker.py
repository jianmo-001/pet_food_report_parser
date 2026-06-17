from __future__ import annotations

import csv
import logging
import time
from pathlib import Path

from .archive import archived_file_url
from .feishu import FeishuClient
from .models import ParsedReport
from .parser import parse_pdf
from .router import load_archive_rules
from .settings import Settings
from .storage import save_report_pdf, upsert_report

logger = logging.getLogger(__name__)


def process_once(settings: Settings) -> int:
    client = FeishuClient(settings)
    upload_table_id = settings.feishu_upload_table_id
    pending_reports = client.list_pending_reports(upload_table_id)
    processed = 0
    for pending in pending_reports:
        logger.info("processing record=%s file=%s", pending.record_id, pending.file_name)
        try:
            client.mark_processing(pending.record_id, upload_table_id)
            downloaded = client.download_attachment(pending)
            report = parse_pdf(downloaded.path, settings.template_config, tmp_dir=settings.tmp_dir)
            saved_pdf = save_report_pdf(downloaded.path, settings, pending.record_id, pending.file_name)
            detail_url = settings.detail_url(pending.record_id)
            upsert_report(settings, pending.record_id, report, saved_pdf, pending.file_name, detail_url)
            if settings.is_wide_upload_mode:
                client.write_wide_success(pending.record_id, report, pdf_file_name=pending.file_name, detail_url=detail_url)
                archive_pdf(client, settings, pending.record_id, report, downloaded.path, pending.file_name, pending.archive_url)
            else:
                client.write_success(pending.record_id, report, pdf_file_name=pending.file_name, detail_url=detail_url)
            processed += 1
        except Exception as exc:
            logger.exception("failed to process record=%s", pending.record_id)
            client.write_failure(pending.record_id, str(exc), upload_table_id)
    return processed


def archive_pdf(
    client: FeishuClient,
    settings: Settings,
    record_id: str,
    report: ParsedReport,
    pdf_path: Path,
    file_name: str,
    existing_archive_url: str | None = None,
) -> None:
    if not settings.feishu_archive_enabled:
        return
    if existing_archive_url:
        logger.info("record=%s already archived: %s", record_id, existing_archive_url)
        return
    if not settings.feishu_archive_root_token:
        logger.warning("record=%s skip archive: FEISHU_ARCHIVE_ROOT_TOKEN 未配置", record_id)
        return

    try:
        router = load_archive_rules(settings.feishu_archive_rules)
        top_folders = client.list_subfolders(settings.feishu_archive_root_token)
        router = router.with_live_folders(list(top_folders))
        result = router.classify(file_name, report.sample_name)

        if result is None or result.ambiguous:
            reason = "未匹配到归档文件夹，请人工归档或补充规则" if result is None else "归档匹配并列冲突，请人工确认"
            logger.warning("record=%s 归档未匹配: %s", record_id, file_name)
            _report_unmatched(settings, record_id, file_name, report.sample_name, reason)
            client.update_record(
                settings.feishu_wide_table_id,
                record_id,
                {settings.field_archive_error: reason},
            )
            return

        # 解析目标文件夹 token：顶层一定存在；二级子目录不存在时回落到顶层根目录。
        folder_token = top_folders[result.top_folder]
        archived_parts = [result.top_folder]
        for sub_name in result.path_parts[1:]:
            children = client.list_subfolders(folder_token)
            if sub_name in children:
                folder_token = children[sub_name]
                archived_parts.append(sub_name)
            else:
                logger.info("record=%s 二级子目录缺失，回落根目录: %s", record_id, sub_name)
                break

        actual_result = result if archived_parts == list(result.path_parts) else None
        path_text = router.archive_path(actual_result) if actual_result else "/".join(
            [router.root_name, *archived_parts] if router.root_name else archived_parts
        )

        file_token = client.find_file_in_folder(folder_token, file_name, pdf_path.stat().st_size)
        if file_token:
            logger.info("record=%s 归档已存在: %s -> %s", record_id, file_name, path_text)
        else:
            file_token = client.upload_file_to_folder(pdf_path, file_name, folder_token)
            logger.info("record=%s 已归档: %s -> %s", record_id, file_name, path_text)

        client.update_record(
            settings.feishu_wide_table_id,
            record_id,
            {
                settings.field_archive_path: path_text,
                settings.field_archive_url: archived_file_url(settings.feishu_archive_domain, file_token),
                settings.field_archive_error: "",
            },
        )
    except Exception as exc:
        logger.exception("failed to archive record=%s", record_id)
        client.update_record(
            settings.feishu_wide_table_id,
            record_id,
            {settings.field_archive_error: str(exc)},
        )


def _report_unmatched(
    settings: Settings,
    record_id: str,
    file_name: str,
    sample_name: str | None,
    reason: str,
) -> None:
    """把未匹配的文件追加到本地清单，方便人工复核。"""
    report_path = Path("output/archive_unmatched.csv")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not report_path.exists()
    with report_path.open("a", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        if new_file:
            writer.writerow(["record_id", "file_name", "sample_name", "reason"])
        writer.writerow([record_id, file_name, sample_name or "", reason])


def poll_forever(settings: Settings) -> None:
    while True:
        processed = process_once(settings)
        logger.info("poll cycle finished, processed=%d", processed)
        time.sleep(settings.poll_interval_seconds)
