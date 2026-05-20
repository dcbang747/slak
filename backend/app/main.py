"""FastAPI app: receives uploads + simulation payload, runs generation in an
in-process thread pool, and exposes status polling and ZIP download endpoints."""

import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .schemas import SimulationPayload
from .jobs import submit_generation, get_job
from .parser import (
    parse, extract_title_ids_from_history, extract_genetic_traits, extract_death_reasons,
    extract_name_lists, extract_dynasties, extract_religions, extract_secrets, extract_cultures,
)


app = FastAPI(title="CK3 Character History Generator", version="7.0")

# Comma-separated allowed origins; defaults to "*" for local dev. In production
# set CORS_ORIGINS to your frontend domain (e.g. https://yourdomain.com).
_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
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
    """Queue the simulation in the in-process thread pool and return a task ID."""
    task_id = submit_generation(payload.model_dump())
    return {"task_id": task_id}


@app.get("/status/{task_id}")
def status(task_id: str) -> JSONResponse:
    job = get_job(task_id)
    if job is None:
        return JSONResponse({"task_id": task_id, "state": "PENDING"})
    body: dict = {"task_id": task_id, "state": job["state"]}
    if job["state"] == "SUCCESS":
        result = job["result"] or {}
        body["result"] = {
            k: v for k, v in result.items() if k != "family_tree"
        }
        body["message"] = "Done."
    elif job["state"] == "FAILURE":
        body["error"] = job.get("error", "")
    elif job.get("message"):
        body["message"] = job["message"]
    return JSONResponse(body)


@app.get("/result/{task_id}/tree")
def get_tree(task_id: str):
    job = get_job(task_id)
    if job is None or job["state"] != "SUCCESS":
        state = job["state"] if job else "UNKNOWN"
        raise HTTPException(status_code=409, detail=f"Task is {state}")
    return (job["result"] or {}).get("family_tree", {})


@app.get("/download/{task_id}")
def download(task_id: str):
    job = get_job(task_id)
    if job is None or job["state"] != "SUCCESS":
        state = job["state"] if job else "UNKNOWN"
        raise HTTPException(status_code=409, detail=f"Task is {state}")
    zip_path = (job["result"] or {}).get("zip_path")
    if not zip_path or not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Result file missing")
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename="CK3_HISTORY_GENERATOR_OUTPUT.zip",
    )
