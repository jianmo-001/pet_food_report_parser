from __future__ import annotations

from pathlib import Path

import fitz


def extract_pdf_text(path: Path) -> str:
    doc = fitz.open(path)
    pages: list[str] = []
    try:
        for page_index, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if text:
                pages.append(f"\n--- page {page_index} ---\n{text}")
    finally:
        doc.close()
    return "\n".join(pages).strip()


def text_is_usable(text: str) -> bool:
    if len(text.strip()) < 80:
        return False
    useful_markers = ["报告", "检测", "检验", "样品", "编号"]
    return any(marker in text for marker in useful_markers)
