from __future__ import annotations

import logging
import time

from .feishu import FeishuClient
from .parser import parse_pdf
from .settings import Settings

logger = logging.getLogger(__name__)


def process_once(settings: Settings) -> int:
    client = FeishuClient(settings)
    pending_reports = client.list_pending_reports()
    processed = 0
    for pending in pending_reports:
        logger.info("processing record=%s file=%s", pending.record_id, pending.file_name)
        try:
            client.mark_processing(pending.record_id)
            downloaded = client.download_attachment(pending)
            report = parse_pdf(downloaded.path, settings.template_config, tmp_dir=settings.tmp_dir)
            client.write_success(pending.record_id, report, pdf_file_name=pending.file_name)
            processed += 1
        except Exception as exc:
            logger.exception("failed to process record=%s", pending.record_id)
            client.write_failure(pending.record_id, str(exc))
    return processed


def poll_forever(settings: Settings) -> None:
    while True:
        processed = process_once(settings)
        logger.info("poll cycle finished, processed=%d", processed)
        time.sleep(settings.poll_interval_seconds)
