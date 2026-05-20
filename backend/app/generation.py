"""Synchronous generation pipeline.

A generation run takes only a few seconds, so it runs inline within the request
rather than via a task queue or background thread. `/generate` calls this and
returns everything the frontend needs in one response — the stats, the family
tree, and the ZIP (base64-encoded) — so there's no polling, no shared state, and
no result files on disk. This keeps the backend fully stateless, which lets it
run as a serverless function (e.g. Vercel) as well as any normal web host.
"""

import base64

from .schemas import SimulationPayload
from .parser import parse, transform_titles, extract_genetic_traits
from .simulation import run_simulation
from .output import package_zip


def run_generation(payload_json: dict) -> dict:
    """Parse → simulate → render → ZIP. Returns stats + family tree + base64 ZIP."""
    payload = SimulationPayload(**payload_json)

    titles = transform_titles(parse(payload.parsed_files.titles_txt or ""))
    traits = extract_genetic_traits(parse(payload.parsed_files.traits_txt or ""))

    world = run_simulation(
        payload, traits, titles,
        seed=payload.global_settings.random_seed,
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

    zip_bytes = package_zip(world)

    return {
        "characters": len(world.characters),
        "titles_with_history": len(world.title_holders),
        "family_tree": family_tree,
        "zip_b64": base64.b64encode(zip_bytes).decode("ascii"),
    }
