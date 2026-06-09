from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

from .parser import parse_pdf
from .batch import process_pdf_folder
from .exporter import export_report
from .output_importer import append_output_to_existing_feishu, import_output_to_feishu
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

    import_output = subparsers.add_parser("import-output-to-feishu", help="Create a Feishu Bitable from exported output CSV files.")
    import_output.add_argument("--output", type=Path, default=Path("output"))

    append_output = subparsers.add_parser("append-output-to-feishu", help="Append exported output CSV files to an existing Feishu Bitable.")
    append_output.add_argument("--output", type=Path, default=Path("output"))

    process_folder = subparsers.add_parser("process-folder", help="Parse all PDFs in a folder, export results, and optionally import to Feishu.")
    process_folder.add_argument("input_dir", type=Path)
    process_folder.add_argument("--output", type=Path, default=Path("output/batch"))
    process_folder.add_argument("--import-to-feishu", action="store_true")
    process_folder.add_argument("--allow-partial", action="store_true", help="Import successful PDFs even if some PDFs fail.")

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
        return

    if args.command == "import-output-to-feishu":
        result = import_output_to_feishu(args.output, settings)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "append-output-to-feishu":
        result = append_output_to_existing_feishu(args.output, settings)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "process-folder":
        result = process_pdf_folder(
            input_dir=args.input_dir,
            output_dir=args.output,
            settings=settings,
            import_to_feishu=args.import_to_feishu,
            allow_partial=args.allow_partial,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return


if __name__ == "__main__":
    main()
