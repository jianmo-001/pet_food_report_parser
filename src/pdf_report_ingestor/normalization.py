from __future__ import annotations

import re


def normalize_date(value: object) -> str | None:
    if value in (None, "", []):
        return None
    text = str(value).strip()

    range_match = re.search(r"(\d{4}[年./-]\s*\d{1,2}[月./-]\s*\d{1,2}日?)", text)
    if range_match:
        text = range_match.group(1)

    patterns = [
        r"(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})",
        r"(?P<year>\d{4})\s*年\s*(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})\s*日?",
        r"(?P<year>\d{4})[./-](?P<month>\d{1,2})[./-](?P<day>\d{1,2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        year = int(match.group("year"))
        month = int(match.group("month"))
        day = int(match.group("day"))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"
    return text or None


def normalize_date_range(value: object) -> str | None:
    if value in (None, "", []):
        return None
    text = str(value).strip()
    parts = re.split(r"\s*(?:~|～|到|至|-{2,})\s*", text, maxsplit=1)
    if len(parts) == 2:
        start = normalize_date(parts[0])
        end = normalize_date(parts[1])
        if start and end:
            return f"{start} ~ {end}"
    normalized = normalize_date(text)
    return normalized or text
