from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReportItem:
    name: str
    value: str | None = None
    unit: str | None = None
    standard: str | None = None
    method: str | None = None
    conclusion: str | None = None
    source_page: int | None = None
    source_text: str | None = None
    extra_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedReport:
    report_no: str | None = None
    sample_name: str | None = None
    lab: str | None = None
    client: str | None = None
    report_date: str | None = None
    conclusion: str | None = None
    category: str | None = None
    template_name: str | None = None
    template_version: str | None = None
    text_source: str = "pdf_text"
    raw_text: str = ""
    extra_fields: dict[str, Any] = field(default_factory=dict)
    items: list[ReportItem] = field(default_factory=list)


@dataclass(frozen=True)
class PendingReport:
    record_id: str
    attachment_token: str
    file_name: str
    extra: str | None = None
    archive_url: str | None = None


@dataclass(frozen=True)
class DownloadedFile:
    path: Path
    file_name: str
