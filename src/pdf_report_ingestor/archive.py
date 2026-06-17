from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .models import ParsedReport
from .wide_table import split_brand_product


@dataclass(frozen=True)
class ArchiveFolderRule:
    brand: str
    product_keyword: str
    folder_token: str
    folder_name: str | None = None


def load_archive_rules(path: Path) -> list[ArchiveFolderRule]:
    if not path.exists():
        raise RuntimeError(f"归档配置文件不存在：{path}")

    rules: list[ArchiveFolderRule] = []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            brand = (row.get("brand") or "").strip()
            product_keyword = (row.get("product_keyword") or "").strip()
            folder_token = (row.get("folder_token") or "").strip()
            folder_name = (row.get("folder_name") or "").strip() or None
            if not brand or not product_keyword or not folder_token:
                continue
            rules.append(
                ArchiveFolderRule(
                    brand=brand,
                    product_keyword=product_keyword,
                    folder_token=folder_token,
                    folder_name=folder_name,
                )
            )
    if not rules:
        raise RuntimeError(f"归档配置为空或缺少有效规则：{path}")
    return rules


def select_archive_rule(report: ParsedReport, rules: list[ArchiveFolderRule]) -> ArchiveFolderRule:
    brand, product = split_brand_product(report.sample_name)
    product_text = product or report.sample_name or ""
    candidates = [
        rule
        for rule in rules
        if rule.brand == (brand or "") and rule.product_keyword in product_text
    ]
    if not candidates:
        raise RuntimeError(f"未找到归档目录映射：brand={brand or ''} product={product_text}")
    return max(candidates, key=lambda rule: len(rule.product_keyword))


def archived_file_url(domain: str, file_token: str) -> str:
    return f"{domain.rstrip('/')}/file/{file_token}"
