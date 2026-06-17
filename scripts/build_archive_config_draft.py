from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a draft archive folder mapping CSV from local report folders.")
    parser.add_argument("source_dir", type=Path, help="Local directory containing product report folders.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("config/archive_folders.draft.csv"),
        help="Output CSV path.",
    )
    args = parser.parse_args()

    folders = sorted(path for path in args.source_dir.iterdir() if path.is_dir())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["brand", "product_keyword", "folder_token", "folder_name"])
        writer.writeheader()
        for folder in folders:
            writer.writerow(
                {
                    "brand": "诚实一口",
                    "product_keyword": folder.name,
                    "folder_token": "",
                    "folder_name": folder.name,
                }
            )
    print(f"wrote {len(folders)} rows: {args.output}")


if __name__ == "__main__":
    main()
