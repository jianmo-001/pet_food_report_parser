from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

from .parser import parse_pdf
from .exporter import export_report
from .settings import Settings
from .worker import poll_forever, process_once


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    parser = argparse.ArgumentParser(description="Parse inspection report PDFs into Feishu Bitable.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_local = subparsers.add_parser("parse-local", help="Parse one local PDF and print JSON.")
    parse_local.add_argument("pdf", type=Path)

    export = subparsers.add_parser("export-local", help="Parse one local PDF and export JSON/Markdown/CSV files.")
    export.add_argument("pdf", type=Path)
    export.add_argument("--output", type=Path, default=Path("output"))

    poll = subparsers.add_parser("poll", help="Poll Feishu Bitable pending records.")
    poll.add_argument("--once", action="store_true", help="Run one poll cycle and exit.")

    args = parser.parse_args()
    settings = Settings()

    if args.command == "parse-local":
        report = parse_pdf(args.pdf, settings.template_config, tmp_dir=settings.tmp_dir)
        payload = asdict(report)
        payload["raw_text"] = report.raw_text[:2000]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if args.command == "export-local":
        report = parse_pdf(args.pdf, settings.template_config, tmp_dir=settings.tmp_dir)
        paths = export_report(report, args.pdf, args.output)
        for path in paths:
            print(path)
        return

    if args.command == "poll":
        if args.once:
            count = process_once(settings)
            print(f"processed={count}")
        else:
            poll_forever(settings)


if __name__ == "__main__":
    main()
