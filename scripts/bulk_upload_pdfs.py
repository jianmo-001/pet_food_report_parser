"""把本地文件夹里的 PDF 批量建成「轮询/宽表」里的待解析记录。

每个 PDF -> 上传为多维表格附件 -> 新建一行：PDF附件 + PDF文件名 + 解析状态=未解析。
之后由 `cli poll` 轮询逐行解析、回填字段。

用法:
    python scripts/bulk_upload_pdfs.py <pdf目录> [--limit N] [--dry-run]

幂等：已存在同名 PDF文件名 的记录会跳过，可安全重复运行。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pdf_report_ingestor.feishu import FeishuClient  # noqa: E402
from pdf_report_ingestor.settings import Settings  # noqa: E402


def upload_bitable_attachment(client: FeishuClient, app_token: str, path: Path, file_name: str) -> str:
    """上传一个文件作为多维表格附件，返回 file_token。"""
    url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
    data = {
        "file_name": file_name,
        "parent_type": "bitable_file",
        "parent_node": app_token,
        "size": str(path.stat().st_size),
        "extra": json.dumps({"drive_route_token": app_token}),
    }
    with path.open("rb") as fh:
        resp = requests.post(
            url,
            headers=client._auth_headers(),
            data=data,
            files={"file": (file_name, fh, "application/pdf")},
            timeout=120,
        )
    resp.raise_for_status()
    payload = resp.json()
    client._ensure_ok(payload)
    file_token = (payload.get("data") or {}).get("file_token")
    if not file_token:
        raise RuntimeError(f"upload media 响应缺少 file_token: {payload}")
    return str(file_token)


def create_pending_record(client: FeishuClient, app_token: str, table_id: str, file_name: str, file_token: str) -> str:
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    fields = {
        "PDF文件名": file_name,
        "PDF附件": [{"file_token": file_token}],
        "解析状态": "未解析",
    }
    resp = requests.post(url, headers=client._json_headers(), json={"fields": fields}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    client._ensure_ok(data)
    return ((data.get("data") or {}).get("record") or {}).get("record_id", "")


def existing_pdf_names(client: FeishuClient, table_id: str) -> set[str]:
    names: set[str] = set()
    for record in client._list_records(table_id):
        value = (record.get("fields") or {}).get("PDF文件名")
        if isinstance(value, list):
            value = "".join(str(v.get("text", v)) if isinstance(v, dict) else str(v) for v in value)
        if value:
            names.add(str(value).strip())
    return names


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 个（0=全部），用于测试")
    parser.add_argument("--dry-run", action="store_true", help="只列出将要上传的文件，不真正写飞书")
    args = parser.parse_args()

    load_dotenv(".env")
    settings = Settings()
    client = FeishuClient(settings)
    app_token = settings.feishu_bitable_app_token
    table_id = settings.feishu_upload_table_id

    pdfs = sorted(p for p in args.input_dir.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf")
    if not pdfs:
        raise SystemExit(f"未找到 PDF：{args.input_dir}")

    existing = existing_pdf_names(client, table_id)
    todo = [p for p in pdfs if p.name not in existing]
    skipped = len(pdfs) - len(todo)
    if args.limit:
        todo = todo[: args.limit]

    print(f"发现 PDF {len(pdfs)} 个；已存在跳过 {skipped} 个；本次将上传 {len(todo)} 个", flush=True)
    if args.dry_run:
        for p in todo:
            print("  [dry-run]", p.name)
        return

    ok = 0
    failures: list[tuple[str, str]] = []
    for i, pdf in enumerate(todo, 1):
        try:
            token = upload_bitable_attachment(client, app_token, pdf, pdf.name)
            rec = create_pending_record(client, app_token, table_id, pdf.name, token)
            ok += 1
            print(f"[{i}/{len(todo)}] OK {pdf.name} -> record={rec}", flush=True)
        except Exception as exc:  # noqa: BLE001
            failures.append((pdf.name, str(exc)))
            print(f"[{i}/{len(todo)}] FAIL {pdf.name}: {exc}", flush=True)
        time.sleep(0.05)

    print(f"\n完成：成功 {ok}，失败 {len(failures)}", flush=True)
    for name, err in failures:
        print("  FAIL", name, err)


if __name__ == "__main__":
    main()
