from __future__ import annotations

from pathlib import Path

import fitz


def extract_ocr_text(path: Path, tmp_dir: Path | None = None) -> str:
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise RuntimeError("未安装 OCR 依赖，请安装项目的 ocr extras，或先只处理文本型 PDF") from exc

    ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    image_dir = tmp_dir or path.parent
    image_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(path)
    pages: list[str] = []
    try:
        for page_index, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image_path = image_dir / f"{path.stem}_page_{page_index}.png"
            pix.save(image_path)
            result = ocr.ocr(str(image_path), cls=True)
            lines: list[str] = []
            for page_result in result or []:
                for item in page_result or []:
                    if len(item) >= 2 and item[1]:
                        lines.append(str(item[1][0]))
            if lines:
                pages.append(f"\n--- page {page_index} ---\n" + "\n".join(lines))
    finally:
        doc.close()
    return "\n".join(pages).strip()
