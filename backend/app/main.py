"""FastAPI app: receives uploads + simulation payload, runs the (fast) generation
synchronously, and returns stats + family tree + ZIP in a single response.
Stateless — no task queue, polling, or result files."""

import os
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from .schemas import SimulationPayload
from .generation import run_generation
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
# Generation endpoint — runs synchronously, returns the full result.
# Defined as a sync `def` so FastAPI runs the CPU-bound work in its threadpool
# (keeps the event loop free and lets concurrent requests proceed).
# ---------------------------------------------------------------------------

@app.post("/generate")
def generate(payload: SimulationPayload) -> dict:
    """Run the simulation and return {characters, titles_with_history, family_tree, zip_b64}."""
    return run_generation(payload.model_dump())
