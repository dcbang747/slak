"""FastAPI app: receives uploads + simulation payload, dispatches to Celery,
exposes status polling and ZIP download endpoints (spec 1.2)."""

import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .celery_app import celery_app
from .schemas import SimulationPayload
from .tasks import run_generation
from .parser import (
    parse, extract_title_ids_from_history, extract_genetic_traits, extract_death_reasons,
    extract_name_lists, extract_dynasties, extract_religions, extract_secrets, extract_cultures,
)


app = FastAPI(title="CK3 Character History Generator", version="7.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Upload helpers — frontend sends raw .txt; backend parses + returns AST
# previewable by the UI before the heavy simulation runs.
# ---------------------------------------------------------------------------

@app.post("/upload/titles")
async def upload_titles(file: UploadFile = File(...)) -> dict:
    text = (await file.read()).decode("utf-8", errors="ignore")
    ast = parse(text)
    return {
        "filename": file.filename,
        "title_ids": extract_title_ids_from_history(ast),
        "raw": text,
    }


@app.post("/upload/traits")
async def upload_traits(file: UploadFile = File(...)) -> dict:
    text = (await file.read()).decode("utf-8", errors="ignore")
    ast = parse(text)
    return {
        "filename": file.filename,
        "traits": extract_genetic_traits(ast),
        "raw": text,
    }


@app.post("/upload/deaths")
async def upload_deaths(file: UploadFile = File(...)) -> dict:
    text = (await file.read()).decode("utf-8", errors="ignore")
    ast = parse(text)
    return {
        "filename": file.filename,
        "deaths": extract_death_reasons(ast),
        "raw": text,
    }


@app.post("/upload/names")
async def upload_names(file: UploadFile = File(...)) -> dict:
    text = (await file.read()).decode("utf-8", errors="ignore")
    ast = parse(text)
    name_lists = extract_name_lists(ast)
    return {"filename": file.filename, "name_lists": name_lists, "raw": text}


@app.post("/upload/dynasties")
async def upload_dynasties(file: UploadFile = File(...)) -> dict:
    text = (await file.read()).decode("utf-8", errors="ignore")
    ast = parse(text)
    dynasties = extract_dynasties(ast)
    return {"filename": file.filename, "dynasties": dynasties, "raw": text}


@app.post("/upload/religions")
async def upload_religions(file: UploadFile = File(...)) -> dict:
    text = (await file.read()).decode("utf-8", errors="ignore")
    ast = parse(text)
    religions = extract_religions(ast)
    return {"filename": file.filename, "religions": religions, "raw": text}


@app.post("/upload/secrets")
async def upload_secrets(file: UploadFile = File(...)) -> dict:
    text = (await file.read()).decode("utf-8", errors="ignore")
    ast = parse(text)
    secret_ids = extract_secrets(ast)
    return {"filename": file.filename, "secret_ids": secret_ids, "raw": text}


@app.post("/upload/cultures")
async def upload_cultures(file: UploadFile = File(...)) -> dict:
    text = (await file.read()).decode("utf-8", errors="ignore")
    ast = parse(text)
    cultures = extract_cultures(ast)
    return {"filename": file.filename, "cultures": cultures}


# ---------------------------------------------------------------------------
# Generation endpoints
# ---------------------------------------------------------------------------

@app.post("/generate")
def generate(payload: SimulationPayload) -> dict:
    """Dispatch the simulation to the Celery worker and return a task ID."""
    task = run_generation.delay(payload.model_dump())
    return {"task_id": task.id}


@app.get("/status/{task_id}")
def status(task_id: str) -> JSONResponse:
    task = celery_app.AsyncResult(task_id)
    body: dict = {"task_id": task_id, "state": task.state}
    if task.state == "PROGRESS" and isinstance(task.info, dict):
        body["message"] = task.info.get("message", "")
    elif task.state == "SUCCESS":
        body["result"] = {
            k: v for k, v in (task.result or {}).items()
            if k not in ("zip_b64", "family_tree")
        }
        body["message"] = "Done."
    elif task.state == "FAILURE":
        body["error"] = str(task.info)
    return JSONResponse(body)


@app.get("/result/{task_id}/tree")
def get_tree(task_id: str):
    task = celery_app.AsyncResult(task_id)
    if task.state != "SUCCESS":
        raise HTTPException(status_code=409, detail=f"Task is {task.state}")
    return (task.result or {}).get("family_tree", {})


@app.get("/download/{task_id}")
def download(task_id: str):
    task = celery_app.AsyncResult(task_id)
    if task.state != "SUCCESS":
        raise HTTPException(status_code=409, detail=f"Task is {task.state}")
    result = task.result or {}
    zip_path = result.get("zip_path")
    if not zip_path or not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Result file missing")
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename="CK3_HISTORY_GENERATOR_OUTPUT.zip",
    )
