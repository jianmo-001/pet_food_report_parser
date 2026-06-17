from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from .settings import Settings
from .storage import get_report, init_db


def create_app() -> FastAPI:
    settings = Settings()
    init_db(settings)
    app = FastAPI(title="PDF Report Viewer")
    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse("<html><body><h1>PDF Report Viewer</h1></body></html>")

    @app.get("/report/{record_id}", response_class=HTMLResponse)
    def report_page(record_id: str, request: Request) -> HTMLResponse:
        data = get_report(settings, record_id)
        if not data:
            raise HTTPException(status_code=404, detail="未找到该报告")
        payload = data.get("payload") or {}
        raw_main = payload.get("main_json") or "{}"
        try:
            main_fields = json.loads(raw_main)
        except json.JSONDecodeError:
            main_fields = {}
        return templates.TemplateResponse(
            request,
            "report.html",
            {
                "record_id": record_id,
                "report": data["report"],
                "items": data["items"],
                "main_fields": main_fields,
                "payload": payload,
            },
        )

    @app.get("/api/report/{record_id}")
    def report_api(record_id: str) -> dict[str, object]:
        data = get_report(settings, record_id)
        if not data:
            raise HTTPException(status_code=404, detail="未找到该报告")
        return data

    @app.get("/pdf/{record_id}")
    def report_pdf(record_id: str) -> FileResponse:
        data = get_report(settings, record_id)
        if not data:
            raise HTTPException(status_code=404, detail="未找到该报告")
        pdf_path = Path(str(data["report"].get("pdf_path") or ""))
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="PDF 文件不存在")
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline", "Cache-Control": "no-store"},
            content_disposition_type="inline",
        )

    return app


app = create_app()
