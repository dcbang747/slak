"""Celery tasks — long-running simulation work goes here (spec 1.2)."""

import base64
import os
import tempfile

from .celery_app import celery_app
from .schemas import SimulationPayload
from .parser import parse, transform_titles, extract_genetic_traits, extract_secrets
from .simulation import run_simulation
from .output import package_zip


# Where the worker writes the resulting ZIPs. In production this would be S3.
RESULTS_DIR = os.environ.get("RESULTS_DIR", tempfile.gettempdir())


@celery_app.task(bind=True, name="run_generation")
def run_generation(self, payload_json: dict) -> dict:
    """Parse → simulate → render → ZIP. Returns {zip_path, stats}."""
    payload = SimulationPayload(**payload_json)

    def log(msg: str) -> None:
        self.update_state(state="PROGRESS", meta={"message": msg})

    log("Parsing titles...")
    titles_ast = parse(payload.parsed_files.titles_txt or "")
    titles = transform_titles(titles_ast)

    log("Parsing traits...")
    traits_ast = parse(payload.parsed_files.traits_txt or "")
    traits = extract_genetic_traits(traits_ast)

    log("Parsing secrets...")
    secrets_txt = payload.parsed_files.secrets_txt or ""
    secret_types = extract_secrets(parse(secrets_txt)) if secrets_txt else []

    log(f"Starting simulation ({payload.global_settings.start_year} → {payload.global_settings.end_year})...")
    world = run_simulation(
        payload, traits, titles,
        secret_types=secret_types,
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
    out_path = os.path.join(RESULTS_DIR, f"history_{self.request.id}.zip")
    with open(out_path, "wb") as f:
        f.write(zip_bytes)

    log("Done.")
    return {
        "zip_path": out_path,
        "characters": len(world.characters),
        "titles_with_history": len(world.title_holders),
        "zip_b64": base64.b64encode(zip_bytes).decode("ascii"),
        "family_tree": family_tree,
    }
