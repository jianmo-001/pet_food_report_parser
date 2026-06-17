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

    init_db_parser = subparsers.add_parser("init-db", help="Initialize the local report SQLite database.")
    deploy_check = subparsers.add_parser("deploy-check", help="Check server deployment configuration.")
    deploy_check.add_argument("--check-feishu", action="store_true", help="Also call Feishu API to verify the configured Bitable table.")

    web = subparsers.add_parser("web", help="Run the report detail web server.")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8000)

    subparsers.add_parser("ensure-wide-fields", help="Create missing fields in the Feishu product wide table.")

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

    if args.command == "init-db":
        from .storage import init_db

        init_db(settings)
        print(settings.database_path)
        return

    if args.command == "deploy-check":
        result = _deploy_check(settings, check_feishu=args.check_feishu)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["errors"]:
            raise SystemExit(1)
        return

    if args.command == "web":
        import uvicorn

        uvicorn.run("pdf_report_ingestor.web:app", host=args.host, port=args.port, reload=False)
        return

    if args.command == "ensure-wide-fields":
        from .feishu import FeishuClient
        from .wide_table import wide_field_names

        if not settings.feishu_bitable_app_token:
            raise RuntimeError("缺少 FEISHU_BITABLE_APP_TOKEN")
        if not settings.feishu_wide_table_id:
            raise RuntimeError("缺少 FEISHU_WIDE_TABLE_ID")
        result = FeishuClient(settings).ensure_table_fields(
            settings.feishu_bitable_app_token,
            settings.feishu_wide_table_id,
            wide_field_names(),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
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


def _deploy_check(settings: Settings, check_feishu: bool = False) -> dict[str, object]:
    from .storage import init_db

    errors: list[str] = []
    warnings: list[str] = []
    required = {
        "FEISHU_APP_ID": settings.feishu_app_id,
        "FEISHU_APP_SECRET": settings.feishu_app_secret,
        "FEISHU_BITABLE_APP_TOKEN": settings.feishu_bitable_app_token,
        "FEISHU_WIDE_TABLE_ID": settings.feishu_wide_table_id,
    }
    for key, value in required.items():
        if not value:
            errors.append(f"{key} 为空")
    if settings.dry_run:
        warnings.append("DRY_RUN=true，服务器正式轮询应设置为 false")
    if not settings.public_base_url:
        warnings.append("PUBLIC_BASE_URL 为空，详情页链接会使用 DETAIL_BASE_URL，本地地址外部无法访问")
    if not settings.template_config.exists():
        errors.append(f"TEMPLATE_CONFIG 不存在：{settings.template_config}")
    if settings.feishu_archive_enabled and not settings.feishu_archive_config.exists():
        errors.append(f"FEISHU_ARCHIVE_ENABLED=true 但归档配置不存在：{settings.feishu_archive_config}")

    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    settings.report_pdf_dir.mkdir(parents=True, exist_ok=True)
    init_db(settings)

    feishu: dict[str, object] = {"checked": False}
    if check_feishu and not errors:
        from .feishu import FeishuClient

        try:
            fields = FeishuClient(settings).list_table_fields(settings.feishu_bitable_app_token, settings.feishu_wide_table_id)
            names = {field.get("field_name") for field in fields}
            missing = [name for name in [settings.field_pdf, settings.field_status, settings.field_error] if name not in names]
            feishu = {"checked": True, "field_count": len(fields), "missing_required_fields": missing}
            if missing:
                errors.append(f"飞书宽表缺少字段：{', '.join(missing)}")
        except Exception as exc:
            errors.append(f"飞书 API 检查失败：{exc}")
            feishu = {"checked": True, "error": str(exc)}

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "database": str(settings.database_path),
        "report_pdf_dir": str(settings.report_pdf_dir),
        "detail_url_example": settings.detail_url("rec_example"),
        "feishu": feishu,
    }


if __name__ == "__main__":
    main()
