"""In-process generation jobs.

Replaces the Celery + Redis task queue with a thread pool and an in-memory job
store. The simulation is a few-second CPU-bound job, so a worker pool inside the
API process is plenty for a small team (concurrent runs share the GIL and simply
take turns — correctness is unaffected, and `task_id`s never collide).

Trade-offs (acceptable for this scale): jobs live in one process, so results don't
survive a restart and the API can't be horizontally scaled to multiple replicas.
`run_simulation()` is untouched, so re-adding Celery later would be a contained
change if the tool ever outgrows this.
"""

import os
import time
import uuid
import threading
import tempfile
from concurrent.futures import ThreadPoolExecutor

from .schemas import SimulationPayload
from .parser import parse, transform_titles, extract_genetic_traits
from .simulation import run_simulation
from .output import package_zip


# Where result ZIPs are written (same instance reads them back for /download).
RESULTS_DIR = os.environ.get("RESULTS_DIR", tempfile.gettempdir())

# Concurrent generations. Low because runs are short and the team is small; the
# GIL serialises CPU work anyway, so a high count buys nothing.
_MAX_WORKERS = int(os.environ.get("GENERATION_WORKERS", "4"))

# Finished jobs are pruned (and their ZIPs deleted) after this many seconds.
_JOB_TTL_SECONDS = int(os.environ.get("JOB_TTL_SECONDS", "3600"))

_executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="gen")
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def _set(task_id: str, **patch) -> None:
    with _lock:
        job = _jobs.get(task_id)
        if job is not None:
            job.update(patch)


def _prune_expired() -> None:
    """Drop finished jobs older than the TTL and delete their result files."""
    now = time.time()
    with _lock:
        stale = [
            tid for tid, j in _jobs.items()
            if j["state"] in ("SUCCESS", "FAILURE") and now - j["finished_at"] > _JOB_TTL_SECONDS
        ]
        for tid in stale:
            job = _jobs.pop(tid, None)
            path = (job or {}).get("result", {}).get("zip_path") if (job or {}).get("result") else None
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


def _run(task_id: str, payload_json: dict) -> None:
    """Worker body: parse → simulate → render → ZIP, updating job state as it goes."""
    def log(msg: str) -> None:
        _set(task_id, state="PROGRESS", message=msg)

    try:
        payload = SimulationPayload(**payload_json)

        log("Parsing titles...")
        titles = transform_titles(parse(payload.parsed_files.titles_txt or ""))

        log("Parsing traits...")
        traits = extract_genetic_traits(parse(payload.parsed_files.traits_txt or ""))

        log(f"Starting simulation ({payload.global_settings.start_year} → {payload.global_settings.end_year})...")
        world = run_simulation(
            payload, traits, titles,
            seed=payload.global_settings.random_seed,
            logger=log,
        )

        ruler_ids = {
            cid
            for holders in world.title_holders.values()
            for _, cid in holders
            if cid != "0"
        }
        family_tree = {
            "characters": {
                cid: {
                    "name": c.name,
                    "dynasty": c.dynasty or c.dynasty_house or "",
                    "is_female": c.is_female,
                    "birth_date": c.birth_date,
                    "death_date": c.death_date or "",
                    "father_id": c.father_id or "",
                    "mother_id": c.mother_id or "",
                    "is_bastard": c.is_bastard,
                    "spouse_ids": list({m["spouse_id"] for m in c.marriages}),
                    "is_ruler": cid in ruler_ids,
                }
                for cid, c in world.characters.items()
            },
            "title_holders": {
                tid: holders
                for tid, holders in world.title_holders.items()
                if tid in world.explicit_title_ids
            },
        }

        log("Packaging ZIP...")
        zip_bytes = package_zip(world)
        out_path = os.path.join(RESULTS_DIR, f"history_{task_id}.zip")
        with open(out_path, "wb") as f:
            f.write(zip_bytes)

        _set(
            task_id,
            state="SUCCESS",
            message="Done.",
            finished_at=time.time(),
            result={
                "zip_path": out_path,
                "characters": len(world.characters),
                "titles_with_history": len(world.title_holders),
                "family_tree": family_tree,
            },
        )
    except Exception as exc:  # noqa: BLE001 — surface any failure to the client
        _set(task_id, state="FAILURE", error=str(exc), finished_at=time.time())


def submit_generation(payload_json: dict) -> str:
    """Queue a generation job and return its task ID immediately."""
    _prune_expired()
    task_id = uuid.uuid4().hex
    with _lock:
        _jobs[task_id] = {
            "state": "PENDING",
            "message": "Queued.",
            "result": None,
            "error": None,
            "finished_at": 0.0,
        }
    _executor.submit(_run, task_id, payload_json)
    return task_id


def get_job(task_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(task_id)
        return dict(job) if job is not None else None
