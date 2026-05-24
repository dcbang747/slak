"""Paradox-script output formatter (spec ch. 9 — IMMUTABLE format)."""

import io
import re
import zipfile

from .simulation import WorldState
from .schemas import Character
from .parser import TITLE_PREFIXES

# Secrets emitted with the block form `add_secret = { type = X target = ... }`;
# every other secret uses the bare form `add_secret = secret_X`.
_SECRET_TARGET_FORM = {"secret_murder", "secret_murder_attempt", "secret_lover"}


def _date_key(date_str: str) -> tuple:
    """Parse 'YYYY.M.D' into a comparable tuple for chronological sorting.
    A plain string sort mis-orders months/days, so dates are compared as ints."""
    try:
        return tuple(int(p) for p in date_str.split("."))
    except (AttributeError, ValueError):
        return (9999,)


def _format_character(c: Character, adopted_children: list | None = None) -> str:
    """Format a single character per spec 9.1.

    `adopted_children` is the list of characters this character adopted; each
    produces an `adopt` effect block dated at the adopted child's birth.

    Dated blocks are emitted in strict chronological order: the birth block is
    always first and the death block always last, with every other dated event
    (marriages, adoptions, relationships, secrets, personality traits,
    employment) sorted by date in between.
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

    # Father/mother are ALWAYS written, including for adopted heirs. The blood
    # link must persist in CK3 start dates where the adopting parent is not alive
    # (otherwise the heir appears unconnected). The adopter still records an
    # `adopt` effect at the heir's birth (see adopted_children below).
    if c.father_id:
        lines.append(f"    father = {c.father_id}")
    if c.mother_id:
        lines.append(f"    mother = {c.mother_id}")
    if c.father_id or c.mother_id:
        lines.append("")

    # Genetic traits (top-level, no date block)
    if c.is_bastard:
        lines.append("    trait = bastard")
    for trait in c.traits:
        lines.append(f"    trait = {trait}")
    # Childhood trait (also top-level, per CK3 spec)
    if c.childhood_trait:
        lines.append(f"    trait = {c.childhood_trait}")
    if c.is_bastard or c.traits or c.childhood_trait:
        lines.append("")

    # ------------------------------------------------------------------
    # Collect every dated block as (date_key, block_lines), then sort.
    # Birth is pinned first and death last regardless of any malformed dates.
    # ------------------------------------------------------------------
    middle: list[tuple[tuple, list[str]]] = []

    # Marriage events
    for marriage in c.marriages:
        middle.append((_date_key(marriage["date"]), [
            f"    {marriage['date']} = {{",
            f"        {marriage['type']} = {marriage['spouse_id']}",
            "    }",
        ]))

    # Adoption effects — this character adopts each heir at the heir's birth date.
    for child in adopted_children:
        middle.append((_date_key(child.birth_date), [
            f"    {child.birth_date} = {{",
            "        effect = {",
            f"            adopt = character:{child.id}",
            "",
            "            create_character_memory = {",
            "                type = adopted_a_child",
            "                participants = {",
            f"                    child = character:{child.id}",
            "                }",
            "            }",
            "        }",
            "    }",
        ]))

    # Relationship effects (dated) — set_relation_friend/rival/lover/etc.
    # Guarded by an is_alive check so the relation only fires when the target is
    # still alive at that date (a target may have died before this event).
    for rel in c.relationships:
        middle.append((_date_key(rel["date"]), [
            f"    {rel['date']} = {{",
            "        effect = {",
            "            if = {",
            f"                limit = {{ character:{rel['target_id']} = {{ is_alive = yes }} }}",
            f"                {rel['effect']} = character:{rel['target_id']}",
            "            }",
            "        }",
            "    }",
        ]))

    # Secret effects (dated). Three shapes:
    #   bare:   add_secret = secret_X
    #   block:  add_secret = { type = secret_X target = character:Y }   (murder/lover)
    #   lover:  set_relation_lover = character:Y precedes the add_secret in the block
    for sec in c.secrets:
        stype = sec["type"]
        tgt = sec.get("target_id")
        block = [f"    {sec['date']} = {{", "        effect = {"]
        if sec.get("with_lover") and tgt:
            # Guard the relationship on the target still being alive (same as the
            # relationship blocks above). The add_secret below is left unguarded —
            # a secret about a now-dead character is still valid in CK3.
            block.append("            if = {")
            block.append(f"                limit = {{ character:{tgt} = {{ is_alive = yes }} }}")
            block.append(f"                set_relation_lover = character:{tgt}")
            block.append("            }")
        if tgt and stype in _SECRET_TARGET_FORM:
            block.append("            add_secret = {")
            block.append(f"                type = {stype}")
            block.append(f"                target = character:{tgt}")
            block.append("            }")
        else:
            block.append(f"            add_secret = {{ type = {stype} }}")
        block.append("        }")
        block.append("    }")
        middle.append((_date_key(sec["date"]), block))

    # Personality traits block (assigned at age 16, in a date block)
    if c.personality_traits and c.personality_trait_date:
        block = [f"    {c.personality_trait_date} = {{"]
        for trait in c.personality_traits:
            block.append(f"        trait = {trait}")
        block.append("    }")
        middle.append((_date_key(c.personality_trait_date), block))

    # Nickname (granted in adulthood). give_nickname sits directly under the date
    # block; a separate effect stamps a flag marking the nickname event.
    if c.nickname and c.nickname_date:
        middle.append((_date_key(c.nickname_date), [
            f"    {c.nickname_date} = {{",
            f"        give_nickname = {c.nickname}",
            "        effect = {",
            "            add_character_flag = had_nickname_event",
            "        }",
            "    }",
        ]))

    # Optional employment block (claimant displacement)
    if c.employer_id and c.employer_date:
        middle.append((_date_key(c.employer_date), [
            f"    {c.employer_date} = {{",
            f"        employer = {c.employer_id}",
            "    }",
        ]))

    # Birth block (pinned first) — with optional learn_language effect
    birth_block = [f"    {c.birth_date} = {{", "        birth = yes"]
    if c.birth_languages:
        birth_block.append("        effect = {")
        for lang in c.birth_languages:
            birth_block.append(f"            learn_language = {lang}")
        birth_block.append("        }")
    birth_block.append("    }")

    # Emit: birth first, then chronologically-sorted middle blocks.
    lines.append("")
    lines.extend(birth_block)
    middle.sort(key=lambda t: t[0])
    for _, block in middle:
        lines.append("")
        lines.extend(block)

    # Death block (pinned last)
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

    # Build dynasty → [characters] mapping preserving insertion order within each group.
    # No-dynasty characters split two ways: actual bastards vs lowborn spouses/in-laws
    # (married in from outside, no dynasty) — the latter must NOT be labelled bastards.
    dynasty_groups: dict[str, list] = {}
    bastards: list = []
    lowborn: list = []
    for c in world.characters.values():
        did = c.dynasty_house or c.dynasty
        if did:
            dynasty_groups.setdefault(did, []).append(c)
        elif c.is_bastard:
            bastards.append(c)
        else:
            lowborn.append(c)

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

    if lowborn:
        sections.append(_dynasty_header("LOWBORN", "Lowborn (spouses & in-laws)"))
        sections.append("\n\n".join(fmt(c) for c in lowborn))

    return "\n\n".join(sections) + "\n"


def _date_sort_key(entry: tuple) -> tuple:
    date, _ = entry
    parts = date.split(".")
    return tuple(int(p) for p in parts)


def render_title_history(world: WorldState, only_ids: set | None = None) -> str:
    """One block per explicitly-configured title, date-sorted holders (spec 9.2).

    Only titles the user directly configured (not cascade-inherited children)
    appear in the output. This prevents hundreds of unwanted title entries.
    Titles that came from an uploaded history file are skipped here — their
    output is produced by `merge_title_history` (which preserves the original
    blocks verbatim and injects generated gap-fill holders).

    If `only_ids` is given, restrict output to those title IDs (used in
    Skip-Title-History mode to emit just the placeholder titles).
    """
    out: list[str] = []
    for title_id, holders in world.title_holders.items():
        # Skip cascade-inherited titles — only emit user-configured ones
        if world.explicit_title_ids and title_id not in world.explicit_title_ids:
            continue
        # Skip uploaded titles unless explicitly requested (handled by merge)
        if only_ids is None and title_id in world.uploaded_title_ids:
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


def _title_block_spans(text: str) -> dict[str, tuple[int, int]]:
    """Map each top-level title id to ``(open_brace_index, close_brace_index)``.
    Comments (`# … EOL`) and quoted strings are skipped, so braces inside
    commented-out blocks (common in real mod files) don't miscount depth."""
    result: dict[str, tuple[int, int]] = {}
    i, n = 0, len(text)
    depth = 0
    pending_name: str | None = None
    block_stack: list[tuple[str | None, int]] = []
    while i < n:
        ch = text[i]
        if ch == "#":
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        if ch == '"':
            j = text.find('"', i + 1)
            i = n if j == -1 else j + 1
            continue
        if ch == "{":
            block_stack.append((pending_name if depth == 0 else None, i))
            depth += 1
            pending_name = None
            i += 1
            continue
        if ch == "}":
            depth -= 1
            opened, open_idx = block_stack.pop() if block_stack else (None, 0)
            if depth == 0 and opened:
                result[opened] = (open_idx, i)
            i += 1
            continue
        if ch.isspace() or ch == "=":
            i += 1
            continue
        j = i
        while j < n and not text[j].isspace() and text[j] not in '{}="#':
            j += 1
        token = text[i:j]
        if depth == 0 and token.startswith(TITLE_PREFIXES):
            pending_name = token
        i = j
    return result


_DATE_OPEN_RE = re.compile(r"(?m)^[ \t]*(\d+)\.(\d+)\.(\d+)[ \t]*=[ \t]*\{")


def merge_title_history(original_text: str, injected: dict[str, list[tuple[str, str]]]) -> str:
    """Return the original uploaded title-history text with generated gap-fill
    holder blocks inserted into each affected title block — **at the correct
    chronological position** (before the first existing date block dated later,
    else before the closing brace). Existing blocks (holders, government, liege,
    names, comments) are left byte-for-byte intact."""
    if not injected:
        return original_text
    spans = _title_block_spans(original_text)
    # (absolute_insert_index, date_tuple, block_text) collected across all titles.
    items: list[tuple[int, tuple, str]] = []
    for tid, holders in injected.items():
        span = spans.get(tid)
        if span is None or not holders:
            continue
        open_idx, close_idx = span
        # Existing date-block openings within this title, as (date_tuple, abs_index).
        openings: list[tuple[tuple, int]] = []
        for m in _DATE_OPEN_RE.finditer(original_text, open_idx, close_idx):
            dt = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
            openings.append((dt, m.start()))
        for date, hid in holders:
            dt = _date_key(date)
            later = [idx for (odt, idx) in openings if odt > dt]
            ins_idx = min(later) if later else close_idx
            items.append((ins_idx, dt, f"\t{date} = {{\n\t\tholder = {hid}\n\t}}\n"))

    # Group by insertion index; emit each group's blocks in date order. Apply
    # from highest index to lowest so earlier indices stay valid.
    groups: dict[int, list[tuple[tuple, str]]] = {}
    for idx, dt, txt in items:
        groups.setdefault(idx, []).append((dt, txt))
    out = original_text
    for idx in sorted(groups, reverse=True):
        chunk = "".join(t for _, t in sorted(groups[idx], key=lambda x: x[0]))
        prefix = "" if (idx > 0 and out[idx - 1] == "\n") else "\n"
        out = out[:idx] + prefix + chunk + out[idx:]
    return out


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
            # Generated blocks for non-uploaded (user-added/placeholder) titles.
            generated = render_title_history(world)
            original = world.payload.parsed_files.titles_txt
            if original:
                # Preserve the uploaded file verbatim, injecting gap-fill holders,
                # then append any generated non-uploaded title blocks.
                merged = merge_title_history(original, world.injected_holders)
                if generated.strip():
                    merged = merged.rstrip() + "\n\n" + generated
                title_history = merged
            else:
                title_history = generated
            zf.writestr("title_history.txt", title_history)
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
