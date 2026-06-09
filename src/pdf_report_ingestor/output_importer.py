from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .feishu import FeishuClient
from .settings import Settings


MAIN_TABLE_NAME = "检测报告主表"
ITEM_TABLE_NAME = "检测项目明细表"


def import_output_to_feishu(output_dir: Path, settings: Settings) -> dict[str, Any]:
    main_rows = _read_csv_files(output_dir, "*/*_main.csv")
    item_rows = _read_csv_files(output_dir, "*/*_items.csv")
    if not main_rows:
        raise RuntimeError(f"未找到主表 CSV：{output_dir}/*/*_main.csv")
    if not item_rows:
        raise RuntimeError(f"未找到明细表 CSV：{output_dir}/*/*_items.csv")

    client = FeishuClient(settings)
    app_token = client.create_bitable_app(
        name=settings.feishu_output_bitable_name,
        folder_token=settings.feishu_folder_token or None,
    )
    main_table_id = client.create_table(app_token, MAIN_TABLE_NAME, _field_names(main_rows))
    item_table_id = client.create_table(app_token, ITEM_TABLE_NAME, _field_names(item_rows))
    main_count = client.batch_create_records(app_token, main_table_id, main_rows)
    item_count = client.batch_create_records(app_token, item_table_id, item_rows)
    permission = client.set_bitable_link_permission(app_token, settings.feishu_link_share_entity)

    return {
        "app_token": app_token,
        "url": f"https://feishu.cn/base/{app_token}",
        "permission": permission,
        "tables": {
            MAIN_TABLE_NAME: {"table_id": main_table_id, "records": main_count},
            ITEM_TABLE_NAME: {"table_id": item_table_id, "records": item_count},
        },
    }


def append_output_to_existing_feishu(output_dir: Path, settings: Settings) -> dict[str, Any]:
    main_rows = _read_csv_files(output_dir, "*/*_main.csv")
    item_rows = _read_csv_files(output_dir, "*/*_items.csv")
    if not main_rows:
        raise RuntimeError(f"未找到主表 CSV：{output_dir}/*/*_main.csv")
    if not item_rows:
        raise RuntimeError(f"未找到明细表 CSV：{output_dir}/*/*_items.csv")
    if not settings.feishu_bitable_app_token:
        raise RuntimeError("缺少 FEISHU_BITABLE_APP_TOKEN，请从多维表格链接中填写 app_token")
    if not settings.feishu_report_table_id:
        raise RuntimeError("缺少 FEISHU_REPORT_TABLE_ID，请填写检测报告主表 table_id")
    if not settings.feishu_item_table_id:
        raise RuntimeError("缺少 FEISHU_ITEM_TABLE_ID，请填写检测项目明细表 table_id")

    client = FeishuClient(settings)
    main_count = client.batch_create_records(settings.feishu_bitable_app_token, settings.feishu_report_table_id, main_rows)
    item_count = client.batch_create_records(settings.feishu_bitable_app_token, settings.feishu_item_table_id, item_rows)
    return {
        "app_token": settings.feishu_bitable_app_token,
        "url": f"https://feishu.cn/base/{settings.feishu_bitable_app_token}",
        "tables": {
            MAIN_TABLE_NAME: {"table_id": settings.feishu_report_table_id, "records": main_count},
            ITEM_TABLE_NAME: {"table_id": settings.feishu_item_table_id, "records": item_count},
        },
    }


def _read_csv_files(output_dir: Path, pattern: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    paths = sorted(output_dir.glob(pattern))
    if pattern.startswith("*/*_"):
        paths.extend(sorted(output_dir.glob(pattern.removeprefix("*/"))))
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            rows.extend(dict(row) for row in csv.DictReader(file))
    return rows


def _field_names(rows: list[dict[str, str]]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for name in row.keys():
            if name and name not in seen:
                names.append(name)
                seen.add(name)
    return names
