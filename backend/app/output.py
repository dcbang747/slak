"""Paradox-script output formatter (spec ch. 9 — IMMUTABLE format)."""

import io
import re
import zipfile

from .simulation import WorldState
from .schemas import Character

# Secrets emitted with the block form `add_secret = { type = X target = ... }`;
# every other secret uses the bare form `add_secret = secret_X`.
_SECRET_TARGET_FORM = {"secret_murder", "secret_murder_attempt", "secret_lover"}


def _format_character(c: Character, adopted_children: list | None = None) -> str:
    """Format a single character per spec 9.1.

    `adopted_children` is the list of characters this character adopted; each
    produces an `adopt` effect block dated at the adopted child's birth.
    """
    adopted_children = adopted_children or []
    lines: list[str] = [f"{c.id} = {{"]
    lines.append(f"    name = {c.name}")

    # Emit dynasty= (main house) XOR dynasty_house= (cadet branch), never both.
    if c.dynasty_house:
        lines.append(f"    dynasty_house = {c.dynasty_house}")
    elif c.dynasty:
        lines.append(f"    dynasty = {c.dynasty}")

    lines.append(f"    religion = {c.religion}")
    lines.append(f"    culture = {c.culture}")
    lines.append("")

    # `female = yes` ONLY if female (omit entirely otherwise)
    if c.is_female:
        lines.append("    female = yes")
        lines.append("")

    # Adopted heirs are foundlings in CK3 — no biological parent lines; the
    # adopting parent records an `adopt` effect instead (see below).
    if not c.is_adopted:
        if c.father_id:
            lines.append(f"    father = {c.father_id}")
        if c.mother_id:
            lines.append(f"    mother = {c.mother_id}")
        if c.father_id or c.mother_id:
            lines.append("")

    # Genetic traits (top-level, no date block)
    for trait in c.traits:
        lines.append(f"    trait = {trait}")
    # Childhood trait (also top-level, per CK3 spec)
    if c.childhood_trait:
        lines.append(f"    trait = {c.childhood_trait}")
    if c.traits or c.childhood_trait:
        lines.append("")

    # Marriage events (sorted chronologically; before birth block)
    for marriage in sorted(c.marriages, key=lambda m: m["date"]):
        lines.append(f"    {marriage['date']} = {{")
        lines.append(f"        {marriage['type']} = {marriage['spouse_id']}")
        lines.append("    }")
        lines.append("")

    # Birth block — with optional learn_language effect
    lines.append(f"    {c.birth_date} = {{")
    lines.append("        birth = yes")
    if c.birth_languages:
        lines.append("        effect = {")
        for lang in c.birth_languages:
            lines.append(f"            learn_language = {lang}")
        lines.append("        }")
    lines.append("    }")

    # Adoption effects — this character adopts each heir at the heir's birth date.
    for child in sorted(adopted_children, key=lambda ch: ch.birth_date):
        lines.append("")
        lines.append(f"    {child.birth_date} = {{")
        lines.append("        effect = {")
        lines.append(f"            adopt = character:{child.id}")
        lines.append("")
        lines.append("            create_character_memory = {")
        lines.append("                type = adopted_a_child")
        lines.append("                participants = {")
        lines.append(f"                    child = character:{child.id}")
        lines.append("                }")
        lines.append("            }")
        lines.append("        }")
        lines.append("    }")

    # Relationship effects (dated) — set_relation_friend/rival/lover/etc.
    for rel in sorted(c.relationships, key=lambda r: r["date"]):
        lines.append("")
        lines.append(f"    {rel['date']} = {{")
        lines.append("        effect = {")
        lines.append(f"            {rel['effect']} = character:{rel['target_id']}")
        lines.append("        }")
        lines.append("    }")

    # Secret effects (dated). Three shapes:
    #   bare:   add_secret = secret_X
    #   block:  add_secret = { type = secret_X target = character:Y }   (murder/lover)
    #   lover:  set_relation_lover = character:Y precedes the add_secret in the block
    for sec in sorted(c.secrets, key=lambda s: s["date"]):
        stype = sec["type"]
        tgt = sec.get("target_id")
        lines.append("")
        lines.append(f"    {sec['date']} = {{")
        lines.append("        effect = {")
        if sec.get("with_lover") and tgt:
            lines.append(f"            set_relation_lover = character:{tgt}")
        if tgt and stype in _SECRET_TARGET_FORM:
            lines.append("            add_secret = {")
            lines.append(f"                type = {stype}")
            lines.append(f"                target = character:{tgt}")
            lines.append("            }")
        else:
            lines.append(f"            add_secret = {stype}")
        lines.append("        }")
        lines.append("    }")

    # Personality traits block (assigned at age 16, in a date block)
    if c.personality_traits and c.personality_trait_date:
        lines.append("")
        lines.append(f"    {c.personality_trait_date} = {{")
        for trait in c.personality_traits:
            lines.append(f"        trait = {trait}")
        lines.append("    }")

    # Optional employment block (claimant displacement)
    if c.employer_id and c.employer_date:
        lines.append("")
        lines.append(f"    {c.employer_date} = {{")
        lines.append(f"        employer = {c.employer_id}")
        lines.append("    }")

    # Death block
    if c.death_date:
        lines.append("")
        lines.append(f"    {c.death_date} = {{")
        lines.append("        death = {")
        lines.append(f"            death_reason = {c.death_reason or 'death_natural_causes'}")
        if c.killer_id:
            lines.append(f"            killer = {c.killer_id}")
        lines.append("        }")
        lines.append("    }")

    lines.append("}")
    return "\n".join(lines)


def _dynasty_header(dynasty_id: str, dynasty_name: str) -> str:
    label = f"### {dynasty_id} | {dynasty_name} ###"
    bar = "#" * len(label)
    return f"{bar}\n{label}\n{bar}"


def render_character_history(world: WorldState) -> str:
    """Characters grouped by dynasty with comment headers, then bastards."""
    # adopter_id → [adopted child, ...] so each adopter emits adopt effects.
    adoptions: dict[str, list] = {}
    for c in world.characters.values():
        if c.is_adopted:
            adopter_id = c.father_id or c.mother_id
            if adopter_id:
                adoptions.setdefault(adopter_id, []).append(c)

    # Build dynasty → [characters] mapping preserving insertion order within each group
    dynasty_groups: dict[str, list] = {}
    bastards: list = []
    for c in world.characters.values():
        did = c.dynasty_house or c.dynasty
        if did:
            dynasty_groups.setdefault(did, []).append(c)
        else:
            bastards.append(c)

    def fmt(c):
        return _format_character(c, adoptions.get(c.id))

    sections: list[str] = []
    for did in sorted(dynasty_groups.keys()):
        chars = dynasty_groups[did]
        ddef = world.dynasty_defs.get(did)
        dname = (ddef.name if ddef and ddef.name else did)
        sections.append(_dynasty_header(did, dname))
        sections.append("\n\n".join(fmt(c) for c in chars))

    if bastards:
        sections.append(_dynasty_header("BASTARDS", "Bastards"))
        sections.append("\n\n".join(fmt(c) for c in bastards))

    return "\n\n".join(sections) + "\n"


def _date_sort_key(entry: tuple) -> tuple:
    date, _ = entry
    parts = date.split(".")
    return tuple(int(p) for p in parts)


def render_title_history(world: WorldState, only_ids: set | None = None) -> str:
    """One block per explicitly-configured title, date-sorted holders (spec 9.2).

    Only titles the user directly configured (not cascade-inherited children)
    appear in the output. This prevents hundreds of unwanted title entries.

    If `only_ids` is given, restrict output to those title IDs (used in
    Skip-Title-History mode to emit just the placeholder titles).
    """
    out: list[str] = []
    for title_id, holders in world.title_holders.items():
        # Skip cascade-inherited titles — only emit user-configured ones
        if world.explicit_title_ids and title_id not in world.explicit_title_ids:
            continue
        if only_ids is not None and title_id not in only_ids:
            continue
        if not holders:
            continue
        sorted_holders = sorted(holders, key=_date_sort_key)
        out.append(f"{title_id} = {{")
        for date, holder_id in sorted_holders:
            out.append(f"    {date} = {{")
            out.append(f"        holder = {holder_id}")
            out.append("    }")
        out.append("}")
    return "\n".join(out) + "\n"


def _pretty_name(dynasty_id: str) -> str:
    """Convert dynasty_elendil → 'Elendil', house_isildur → 'Isildur'."""
    name = dynasty_id
    for prefix in ("dynasty_", "house_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    return name.replace("_", " ").title()


def render_dynasties_txt(world: WorldState) -> str:
    """Generate a Paradox dynasties.txt from all dynasty/house IDs used."""
    lines: list[str] = []
    # Sort for deterministic output: base dynasties first, then houses
    dynasty_ids = sorted(world.dynasty_ids_used)
    base = [d for d in dynasty_ids if not d.startswith("house_")]
    houses = [d for d in dynasty_ids if d.startswith("house_")]

    for did in base:
        ddef = world.dynasty_defs.get(did)
        culture = (
            next((p.culture for p in sorted(ddef.culture_faith_periods, key=lambda p: p.start_year) if p.culture), None)
            if ddef and ddef.culture_faith_periods else None
        ) or "default_culture"
        slug = _slug_key(did)
        lines.append(f"{did} = {{")
        lines.append(f'    name = "dynn_{slug}"')
        lines.append(f'    culture = "{culture}"')
        lines.append(f"    motto = dynn_{slug}_motto")
        lines.append("}")
        lines.append("")

    for did in houses:
        lines.append(f"{did} = {{")
        lines.append(f'    name = "dynn_{_slug_key(did)}"')
        # dynasty link is unknown without user-provided data; left as placeholder
        lines.append("    # dynasty = dynasty_PARENT  # fill in parent dynasty")
        lines.append("}")
        lines.append("")

    return "\n".join(lines)


def _slug_key(dynasty_id: str) -> str:
    """Strip dynasty_/house_ prefix for use as localization key stem."""
    for prefix in ("dynasty_", "house_"):
        if dynasty_id.startswith(prefix):
            return dynasty_id[len(prefix):]
    return dynasty_id


def render_dynasty_names_yml(world: WorldState) -> str:
    """Generate a UTF-8 BOM localization .yml for dynasty display names only."""
    # CK3 requires UTF-8 with BOM; the BOM is prepended in package_zip.
    lines: list[str] = ["l_english:", ""]
    for did in sorted(world.dynasty_ids_used):
        key = _slug_key(did)
        ddef = world.dynasty_defs.get(did)
        display_name = (ddef.name if ddef and ddef.name else "#DEBUG TEMP#!")
        lines.append(f' dynn_{key}: "{display_name}"')
    lines.append("")
    return "\n".join(lines)


def render_dynasty_mottos_yml(world: WorldState) -> str:
    """Generate a UTF-8 BOM localization .yml for dynasty mottos only."""
    lines: list[str] = ["l_english:", ""]
    for did in sorted(world.dynasty_ids_used):
        key = _slug_key(did)
        ddef = world.dynasty_defs.get(did)
        motto_text = (ddef.motto if ddef and ddef.motto else "#DEBUG TEMP#!")
        lines.append(f' dynn_{key}_motto: "{motto_text}"')
    lines.append("")
    return "\n".join(lines)


def package_zip(world: WorldState) -> bytes:
    """Bundle all output files into a ZIP."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("character_history.txt", render_character_history(world))
        if world.payload.global_settings.ignore_title_generation:
            # Skip mode: still emit placeholder title blocks (one per dynasty with no
            # user-assigned title) so the user has copyable title-history scaffolding.
            placeholder_history = render_title_history(world, only_ids=world.placeholder_title_ids)
            zf.writestr("title_history.txt", placeholder_history)
        else:
            zf.writestr("title_history.txt", render_title_history(world))
        if world.dynasty_ids_used:
            zf.writestr("00_dynasties.txt", render_dynasties_txt(world))
            # UTF-8 BOM required by CK3 for .yml localization files. Names and
            # mottos go to separate files; the _l_english suffix is mandatory for
            # CK3 to load the localization, so it is preserved on both.
            names_yml = "﻿" + render_dynasty_names_yml(world)
            zf.writestr("dynasty_names_l_english.yml", names_yml.encode("utf-8"))
            mottos_yml = "﻿" + render_dynasty_mottos_yml(world)
            zf.writestr("dynasty_mottos_l_english.yml", mottos_yml.encode("utf-8"))
    return buf.getvalue()
