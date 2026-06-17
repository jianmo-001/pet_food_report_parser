"""用本地镜像文件夹全量验证归档路由准确率（不联网、不碰共享文件夹）。

用法：
    python scripts/validate_archive_router.py "/Users/yangrunxin/Downloads/2026诚实一口大货报告"

把每个 PDF 当成待归档文件，用规则判定目标路径，再和它真实所在的文件夹比对。
“与原文件夹不一致”里，多数是文件名指向别处（历史放错/类目重叠）——按“文件名说了算”是预期行为。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdf_report_ingestor.router import load_archive_rules  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate archive router against a local mirror folder.")
    parser.add_argument("mirror_dir", type=Path, help="本地镜像目录（结构与共享文件夹一致）。")
    parser.add_argument("--rules", type=Path, default=Path("config/archive_rules.yaml"))
    parser.add_argument("--show", choices=["mismatch", "all", "none"], default="mismatch")
    args = parser.parse_args()

    router = load_archive_rules(args.rules)
    top_names = [p.name for p in args.mirror_dir.iterdir() if p.is_dir()]
    router = router.with_live_folders(top_names)

    total = matched = unmatched = ambiguous = 0
    mismatches: list[tuple[str, str, str]] = []

    for pdf in args.mirror_dir.rglob("*.pdf"):
        rel = pdf.relative_to(args.mirror_dir).parts
        actual = "/".join(rel[:-1])  # 真实所在路径（顶层或顶层/二级）
        result = router.classify(pdf.name)
        total += 1
        if result is None or result.ambiguous:
            unmatched += 1
            if result is not None:
                ambiguous += 1
            mismatches.append((actual, "（未匹配）", pdf.name))
            continue
        pred = "/".join(result.path_parts)
        # 顶层一致即算对；二级仅在双方都到二级时比对
        actual_top = actual.split("/")[0]
        if pred.split("/")[0] != actual_top:
            mismatches.append((actual, pred, pdf.name))
        elif "/" in actual and "/" in pred and pred != actual:
            mismatches.append((actual, pred, pdf.name))
        else:
            matched += 1

    print(f"总文件 {total}  一致 {matched}  不一致 {len(mismatches)}  未匹配 {unmatched}（其中并列冲突 {ambiguous}）")
    print(f"一致率 {matched / total * 100:.1f}%\n" if total else "无文件\n")

    if args.show != "none" and mismatches:
        print("=== 不一致明细（文件名→判定）===")
        for actual, pred, name in mismatches:
            print(f"  原[{actual}] → 判[{pred}]  {name}")


if __name__ == "__main__":
    main()
