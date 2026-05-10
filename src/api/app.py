"""FastAPI app: upload CSV, status, snapshot — local development only."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from src.api.pipeline import PipelineError, repo_root, run_health_pipeline

app = FastAPI(title="healthOS local API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _snapshot_path() -> Path:
    return repo_root() / "web" / "src" / "data" / "snapshot.json"


@app.get("/status")
def status() -> dict[str, bool]:
    path = _snapshot_path()
    if not path.is_file():
        return {"has_data": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"has_data": False}
    return {"has_data": data.get("state") != "no_data"}


@app.get("/snapshot")
def snapshot():
    path = _snapshot_path()
    if not path.is_file():
        raise HTTPException(status_code=404, detail="snapshot.json not found")
    return FileResponse(path, media_type="application/json")


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        return JSONResponse(
            status_code=400,
            content={"error": "Please upload a .csv file"},
        )
    repo = repo_root()
    rawdata = repo / "rawdata"
    rawdata.mkdir(parents=True, exist_ok=True)
    dest = rawdata / "universal.csv"
    body = await file.read()
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return JSONResponse(
            status_code=400,
            content={"error": "File must be UTF-8 encoded text"},
        )
    dest.write_text(text, encoding="utf-8")
    try:
        run_health_pipeline(repo)
    except PipelineError as e:
        return JSONResponse(
            status_code=400,
            content={"error": str(e)},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Pipeline failed: {e}"},
        )
    return {"status": "ok"}
