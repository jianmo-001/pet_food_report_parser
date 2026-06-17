from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .exporter import to_main_fields
from .models import ParsedReport, ReportItem
from .settings import Settings
from .wide_table import build_wide_row


def init_db(settings: Settings) -> None:
    db_path = settings.database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS reports (
                feishu_record_id TEXT PRIMARY KEY,
                report_no TEXT,
                pdf_filename TEXT,
                pdf_path TEXT,
                sample_name TEXT,
                customer_name TEXT,
                test_org TEXT,
                report_date TEXT,
                sample_receive_date TEXT,
                test_start_date TEXT,
                test_end_date TEXT,
                conclusion TEXT,
                detail_url TEXT,
                main_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS report_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feishu_record_id TEXT NOT NULL,
                report_no TEXT,
                item_index INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                value TEXT,
                unit TEXT,
                standard TEXT,
                method TEXT,
                conclusion TEXT,
                raw_text TEXT,
                extra_json TEXT NOT NULL,
                FOREIGN KEY (feishu_record_id) REFERENCES reports(feishu_record_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_report_items_record
            ON report_items(feishu_record_id, item_index);

            CREATE TABLE IF NOT EXISTS report_payloads (
                feishu_record_id TEXT PRIMARY KEY,
                main_json TEXT NOT NULL,
                items_json TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (feishu_record_id) REFERENCES reports(feishu_record_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS product_wide_reports (
                feishu_record_id TEXT PRIMARY KEY,
                report_no TEXT,
                brand_name TEXT,
                product_name TEXT,
                wide_json TEXT NOT NULL,
                unmapped_items_json TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (feishu_record_id) REFERENCES reports(feishu_record_id) ON DELETE CASCADE
            );
            """
        )


def save_report_pdf(source: Path, settings: Settings, record_id: str, file_name: str) -> Path:
    settings.report_pdf_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file_name).suffix or ".pdf"
    output = settings.report_pdf_dir / f"{_safe_file_stem(record_id)}{suffix}"
    if source.resolve() != output.resolve():
        shutil.copy2(source, output)
    return output


def upsert_report(
    settings: Settings,
    record_id: str,
    report: ParsedReport,
    pdf_path: Path,
    pdf_file_name: str,
    detail_url: str,
) -> None:
    init_db(settings)
    main_fields = to_main_fields(report, pdf_file_name)
    now = _utc_now()
    with _connect(settings.database_path) as conn:
        existing = conn.execute(
            "SELECT created_at FROM reports WHERE feishu_record_id = ?",
            (record_id,),
        ).fetchone()
        created_at = existing["created_at"] if existing else now
        conn.execute(
            """
            INSERT INTO reports (
                feishu_record_id, report_no, pdf_filename, pdf_path, sample_name,
                customer_name, test_org, report_date, sample_receive_date,
                test_start_date, test_end_date, conclusion, detail_url,
                main_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(feishu_record_id) DO UPDATE SET
                report_no = excluded.report_no,
                pdf_filename = excluded.pdf_filename,
                pdf_path = excluded.pdf_path,
                sample_name = excluded.sample_name,
                customer_name = excluded.customer_name,
                test_org = excluded.test_org,
                report_date = excluded.report_date,
                sample_receive_date = excluded.sample_receive_date,
                test_start_date = excluded.test_start_date,
                test_end_date = excluded.test_end_date,
                conclusion = excluded.conclusion,
                detail_url = excluded.detail_url,
                main_json = excluded.main_json,
                updated_at = excluded.updated_at
            """,
            (
                record_id,
                report.report_no,
                pdf_file_name,
                str(pdf_path),
                report.sample_name,
                report.client,
                report.lab,
                main_fields.get("报告日期"),
                main_fields.get("样品接收日期"),
                main_fields.get("检测开始日期"),
                main_fields.get("检测结束日期"),
                report.conclusion,
                detail_url,
                json.dumps(main_fields, ensure_ascii=False),
                created_at,
                now,
            ),
        )
        conn.execute("DELETE FROM report_items WHERE feishu_record_id = ?", (record_id,))
        conn.executemany(
            """
            INSERT INTO report_items (
                feishu_record_id, report_no, item_index, item_name, value, unit,
                standard, method, conclusion, raw_text, extra_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [_item_values(record_id, report.report_no, index, item) for index, item in enumerate(report.items, 1)],
        )
        conn.execute(
            """
            INSERT INTO report_payloads (feishu_record_id, main_json, items_json, raw_text, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(feishu_record_id) DO UPDATE SET
                main_json = excluded.main_json,
                items_json = excluded.items_json,
                raw_text = excluded.raw_text,
                updated_at = excluded.updated_at
            """,
            (
                record_id,
                json.dumps(main_fields, ensure_ascii=False),
                json.dumps([asdict(item) for item in report.items], ensure_ascii=False),
                report.raw_text,
                now,
            ),
        )
        wide_row = build_wide_row(report, pdf_file_name, detail_url)
        conn.execute(
            """
            INSERT INTO product_wide_reports (
                feishu_record_id, report_no, brand_name, product_name,
                wide_json, unmapped_items_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(feishu_record_id) DO UPDATE SET
                report_no = excluded.report_no,
                brand_name = excluded.brand_name,
                product_name = excluded.product_name,
                wide_json = excluded.wide_json,
                unmapped_items_json = excluded.unmapped_items_json,
                updated_at = excluded.updated_at
            """,
            (
                record_id,
                report.report_no,
                wide_row.get("品牌名称"),
                wide_row.get("产品名称"),
                json.dumps(wide_row, ensure_ascii=False),
                wide_row.get("未映射检测项目JSON"),
                now,
            ),
        )


def get_report(settings: Settings, record_id: str) -> dict[str, Any] | None:
    init_db(settings)
    with _connect(settings.database_path) as conn:
        report = conn.execute(
            "SELECT * FROM reports WHERE feishu_record_id = ?",
            (record_id,),
        ).fetchone()
        if not report:
            return None
        items = conn.execute(
            "SELECT * FROM report_items WHERE feishu_record_id = ? ORDER BY item_index",
            (record_id,),
        ).fetchall()
        payload = conn.execute(
            "SELECT * FROM report_payloads WHERE feishu_record_id = ?",
            (record_id,),
        ).fetchone()
        wide = conn.execute(
            "SELECT * FROM product_wide_reports WHERE feishu_record_id = ?",
            (record_id,),
        ).fetchone()
    return {
        "report": dict(report),
        "items": [dict(item) for item in items],
        "payload": dict(payload) if payload else None,
        "wide": dict(wide) if wide else None,
    }


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _item_values(record_id: str, report_no: str | None, index: int, item: ReportItem) -> tuple[Any, ...]:
    return (
        record_id,
        report_no,
        index,
        item.name,
        item.value,
        item.unit,
        item.standard,
        item.method,
        item.conclusion,
        item.source_text,
        json.dumps(item.extra_fields, ensure_ascii=False),
    )


def _safe_file_stem(value: str) -> str:
    return "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in value).strip("_") or "report"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
