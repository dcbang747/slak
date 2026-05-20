"""
Paradox Interactive .txt AST parser.

Implements the tokenization + recursive parsing described in spec ch. 5.
Produces Python dicts where:
  - duplicate keys at the same scope collapse into a Python list
  - nested `name = { ... }` blocks become nested dicts
"""

import re
from typing import Any

TITLE_PREFIXES = ("h_", "e_", "k_", "d_", "c_", "b_")
MARITAL_DOCTRINES = {"doctrine_monogamy", "doctrine_polygamy", "doctrine_concubines"}


def tokenize(text: str) -> list[str]:
    """Strip comments, pad structural chars, split preserving quoted strings."""
    # 0. Strip UTF-8 BOM if present (common in Windows-saved Paradox files)
    text = text.lstrip("﻿")

    # 1. Remove comments (# ... end of line)
    text = re.sub(r"#[^\n]*", "", text)

    # 2. Pad braces and equals signs with spaces so they isolate as tokens
    text = re.sub(r"([{}=])", r" \1 ", text)

    # 3. Split, preserving double-quoted substrings as single tokens
    tokens: list[str] = []
    pattern = re.compile(r'"[^"]*"|\S+')
    for match in pattern.finditer(text):
        tok = match.group(0)
        # Strip surrounding quotes (but keep the literal content)
        if tok.startswith('"') and tok.endswith('"'):
            tok = tok[1:-1]
        tokens.append(tok)
    return tokens


class _Cursor:
    __slots__ = ("tokens", "i")

    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self.i = 0

    def peek(self) -> str | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def take(self) -> str:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def eof(self) -> bool:
        return self.i >= len(self.tokens)


def _assign(scope: dict, key: str, value: Any) -> None:
    """Assign respecting the duplicate-key edge case (collapse into list)."""
    if key in scope:
        existing = scope[key]
        if isinstance(existing, list):
            existing.append(value)
        else:
            scope[key] = [existing, value]
    else:
        scope[key] = value


def _parse_block(cur: _Cursor, until_brace: bool) -> dict | list:
    """
    Parse tokens until either EOF (if not until_brace) or a closing '}'.

    A block is normally a dict of key=value entries. If we encounter a bare
    value (no '=' after it), the block is treated as a list literal — this
    matches the Paradox `colors = { 1 2 3 }` style.
    """
    scope: dict = {}
    list_items: list = []
    is_list = False

    while not cur.eof():
        tok = cur.peek()
        if tok == "}":
            cur.take()
            return list_items if is_list else scope
        if tok == "{":
            # Anonymous nested block as a list item
            cur.take()
            inner = _parse_block(cur, until_brace=True)
            list_items.append(inner)
            is_list = True
            continue

        cur.take()  # consume the key/value token

        # Look ahead: is this `key = ...` or a bare list element?
        if cur.peek() == "=":
            cur.take()  # consume '='
            nxt = cur.peek()
            if nxt is None:
                break
            if nxt == "{":
                cur.take()
                value = _parse_block(cur, until_brace=True)
            else:
                value = cur.take()
            _assign(scope, tok, value)
        else:
            # Bare token = list element
            list_items.append(tok)
            is_list = True

        if not until_brace and cur.eof():
            break

    return list_items if is_list else scope


def parse(text: str) -> dict:
    """Parse a Paradox .txt document into a dict (or list) AST."""
    tokens = tokenize(text)
    cur = _Cursor(tokens)
    result = _parse_block(cur, until_brace=False)
    if isinstance(result, list):
        # Top-level was a list; wrap so callers always get a dict shape
        return {"_root": result}
    return result


# ---------------------------------------------------------------------------
# Title hierarchy transformation (spec 5.3)
# ---------------------------------------------------------------------------

def _is_title_key(key: str) -> bool:
    return any(key.startswith(p) for p in TITLE_PREFIXES)


def _tier_of(key: str) -> str:
    return {
        "h_": "hegemony",
        "e_": "empire",
        "k_": "kingdom",
        "d_": "duchy",
        "c_": "county",
        "b_": "barony",
    }[key[:2]]


def transform_titles(ast: dict) -> dict:
    """
    Walk a parsed landed_titles AST and produce a recursive Title tree.

    Each Title has: id, tier, is_landed, metadata, children (dict of id -> Title)
    `metadata` collects all non-title keys (color, capital, cultural_names...).
    """
    def walk(node: dict, key: str | None) -> dict:
        children: dict[str, dict] = {}
        metadata: dict = {}
        for k, v in node.items():
            if isinstance(k, str) and _is_title_key(k) and isinstance(v, dict):
                children[k] = walk(v, k)
            else:
                metadata[k] = v

        is_landed = True
        if key is not None and key.startswith("h_"):
            # Hegemony edge case — landed iff at least one child is a map title
            is_landed = any(_is_title_key(ck) for ck in children.keys())

        return {
            "id": key,
            "tier": _tier_of(key) if key else "root",
            "is_landed": is_landed,
            "metadata": metadata,
            "children": children,
        }

    root = walk(ast, None)
    # Return only the named top-level titles, not the synthetic root
    return root["children"]


# ---------------------------------------------------------------------------
# Title history ID extraction
# ---------------------------------------------------------------------------

def extract_title_ids_from_history(ast: dict) -> list[str]:
    """Return sorted title IDs from a title_history file.

    Title history files contain one root block per title (e.g. `k_arnor = { ... }`).
    Only keys matching TITLE_PREFIXES are returned; date blocks and other keys are ignored.
    Sorted by tier order (empire → kingdom → duchy → county → barony), then alphabetically.
    """
    _tier_order = {"h_": 0, "e_": 1, "k_": 2, "d_": 3, "c_": 4, "b_": 5}
    ids = [k for k in ast if isinstance(k, str) and k.startswith(TITLE_PREFIXES)]
    return sorted(ids, key=lambda t: (_tier_order.get(t[:2], 9), t))


# ---------------------------------------------------------------------------
# Trait + Death extraction (spec 5.4)
# ---------------------------------------------------------------------------

def extract_genetic_traits(ast: dict) -> list[dict]:
    """Return list of {id, group, level, birth_chance, random_creation, opposites}.

    Handles two field-name conventions:
    - Custom sample format: birth_chance = 0.06  (float 0-1, used in samples/)
    - Real Paradox format:  birth = 0.5           (treated as percentage → 0.5/100 = 0.005)

    Two-pass: first collects all genetic traits; second expands group-name references
    in opposites to actual trait IDs (e.g. "intellect_bad" → ["intellect_bad_1", ...]).
    """
    # ── Pass 1: collect raw data ────────────────────────────────────────────
    raw_list: list[dict] = []
    group_to_ids: dict[str, list[str]] = {}
    all_ids: set[str] = set()

    for trait_id, body in ast.items():
        if not isinstance(body, dict):
            continue
        if body.get("genetic") != "yes":
            continue

        def _f(key: str, default: float = 0.0) -> float:
            v = body.get(key, default)
            try:
                return float(v)
            except (TypeError, ValueError):
                return default

        def _i(key: str, default: int = 1) -> int:
            v = body.get(key, default)
            try:
                return int(float(v))
            except (TypeError, ValueError):
                return default

        opposites_raw = body.get("opposites", [])
        if isinstance(opposites_raw, str):
            raw_opps = [opposites_raw]
        elif isinstance(opposites_raw, list):
            raw_opps = [o for o in opposites_raw if isinstance(o, str)]
        else:
            raw_opps = []

        # birth_chance: prefer custom key (already 0-1); fall back to Paradox
        # "birth" which is a percentage value (divide by 100 unconditionally).
        if "birth_chance" in body:
            birth_chance = _f("birth_chance")
        else:
            birth_chance = _f("birth") / 100.0

        rc_raw = _f("random_creation")
        # Paradox random_creation is also a percentage value → always divide by 100.
        random_creation = rc_raw / 100.0

        group = body.get("group", trait_id)
        group_to_ids.setdefault(group, []).append(trait_id)
        all_ids.add(trait_id)

        raw_list.append({
            "id": trait_id,
            "group": group,
            "level": _i("level"),
            "birth_chance": birth_chance,
            "random_creation": random_creation,
            "_raw_opps": raw_opps,
        })

    # ── Pass 2: expand group-name references in opposites ───────────────────
    traits: list[dict] = []
    for t in raw_list:
        expanded: list[str] = []
        for opp in t["_raw_opps"]:
            if opp in all_ids:
                expanded.append(opp)
            elif opp in group_to_ids:
                expanded.extend(group_to_ids[opp])
            # else: unknown reference (e.g. personality trait name) — skip
        traits.append({
            "id": t["id"],
            "group": t["group"],
            "level": t["level"],
            "birth_chance": t["birth_chance"],
            "random_creation": t["random_creation"],
            "opposites": expanded,
        })
    return traits


def extract_death_reasons(ast: dict) -> list[dict]:
    """Return list of {id, is_natural, required_trait}."""
    reasons: list[dict] = []
    for death_id, body in ast.items():
        if not isinstance(body, dict):
            continue
        is_natural = body.get("natural") == "yes"
        required_trait = None
        trigger = body.get("natural_death_trigger")
        if isinstance(trigger, dict):
            ht = trigger.get("has_trait")
            if isinstance(ht, str):
                required_trait = ht
        reasons.append({
            "id": death_id,
            "is_natural": is_natural,
            "required_trait": required_trait,
        })
    return reasons


# ---------------------------------------------------------------------------
# Name list extraction (spec 5.5) — real Paradox name_list_* format
# ---------------------------------------------------------------------------

def _flatten_names(value: Any) -> list[str]:
    """Recursively flatten a parsed name block into a flat list of strings."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_flatten_names(item))
        return result
    return []


def extract_name_lists(ast: dict) -> dict[str, list[str]]:
    """Parse a Paradox name_list file AST into {culture_male: [...], culture_female: [...]}.

    Handles the weighted-group format: `male_names = { 10 = { name1 name2 } }`.
    Weight-0 groups are skipped (Paradox convention: weight 0 = never sample).
    Flat list format (`female_names = { name1 name2 }`) is also accepted.

    Adds `default_male` / `default_female` aliases from the first name list found
    because all characters start with culture = "default_culture" and _pick_name()
    falls back to those keys.
    """
    name_lists: dict[str, list[str]] = {}
    first_culture: str | None = None

    for key, body in ast.items():
        if not isinstance(key, str) or not key.startswith("name_list_"):
            continue
        if not isinstance(body, dict):
            continue

        culture = key[len("name_list_"):]
        if first_culture is None:
            first_culture = culture

        for gender in ("male", "female"):
            block = body.get(f"{gender}_names")
            names: list[str] = []

            if isinstance(block, list):
                # Flat list — no weighted groups
                names = [n for n in block if isinstance(n, str)]
            elif isinstance(block, dict):
                for weight_key, weight_val in block.items():
                    if weight_key == "0":
                        continue  # weight-0 = never sample in Paradox
                    names.extend(_flatten_names(weight_val))

            if names:
                name_lists[f"{culture}_{gender}"] = names

    # Provide default_male / default_female from the first name list so that
    # _pick_name() works for characters whose culture is "default_culture".
    if first_culture is not None:
        for gender in ("male", "female"):
            src = f"{first_culture}_{gender}"
            dst = f"default_{gender}"
            if src in name_lists and dst not in name_lists:
                name_lists[dst] = name_lists[src]

    return name_lists


# ---------------------------------------------------------------------------
# Dynasty extraction (spec 5.6) — real Paradox dynasties format
# ---------------------------------------------------------------------------

def extract_dynasties(ast: dict) -> dict:
    """Parse a Paradox dynasties file into {dynasties: [...], houses: [...]}.

    Base dynasties: `dynasty_X = { name = "dynn_X" culture = "X" motto = dynn_X_motto }`
    Cadet houses:   `house_Y  = { name = "dynn_Y" dynasty = dynasty_X motto = ... }`
    """
    dynasties: list[dict] = []
    houses: list[dict] = []

    for key, body in ast.items():
        if not isinstance(body, dict):
            continue
        if key.startswith("dynasty_"):
            dynasties.append({
                "id": key,
                "name": body.get("name", f"dynn_{key[8:]}"),
                "culture": body.get("culture", ""),
                "motto": body.get("motto", ""),
            })
        elif key.startswith("house_"):
            houses.append({
                "id": key,
                "name": body.get("name", f"dynn_{key[6:]}"),
                "dynasty": body.get("dynasty", ""),
                "motto": body.get("motto", ""),
            })

    return {"dynasties": dynasties, "houses": houses}


# ---------------------------------------------------------------------------
# Religion extraction (spec 5.7) — marital doctrines only
# ---------------------------------------------------------------------------

def extract_religions(ast: dict) -> dict[str, str]:
    """Parse a Paradox religion file, returning {faith_id: marital_doctrine}.

    Structure: `religion_id = { doctrine = X faiths = { faith_id = { ... } } }`
    Root religion sets the default doctrine; individual faiths may override.
    All non-marital content (cosmetics, holy orders, localization) is discarded.
    """
    result: dict[str, str] = {}

    for religion_id, body in ast.items():
        if not isinstance(body, dict):
            continue

        # Find the root marital doctrine for this religion (used as fallback for faiths)
        root_doctrine = _find_marital_doctrine(body)

        # Walk individual faiths
        faiths_block = body.get("faiths")
        if not isinstance(faiths_block, dict):
            continue

        for faith_id, faith_body in faiths_block.items():
            if not isinstance(faith_body, dict):
                continue
            faith_doctrine = _find_marital_doctrine(faith_body)
            result[faith_id] = faith_doctrine or root_doctrine or "doctrine_monogamy"

    return result


def _find_marital_doctrine(body: dict) -> str | None:
    """Return the first marital doctrine found in a block, or None."""
    # `doctrine` may be a single string or a list of strings
    doctrine_raw = body.get("doctrine")
    candidates: list[str] = []
    if isinstance(doctrine_raw, str):
        candidates = [doctrine_raw]
    elif isinstance(doctrine_raw, list):
        candidates = [d for d in doctrine_raw if isinstance(d, str)]

    for d in candidates:
        if d in MARITAL_DOCTRINES:
            return d
    return None


# ---------------------------------------------------------------------------
# Secret type extraction (spec 5.8) — root-level keys only
# ---------------------------------------------------------------------------

def extract_secrets(ast: dict) -> list[str]:
    """Return a list of secret type IDs from a Paradox secret types file.

    Only root-level keys are extracted; all internal block content is discarded.
    """
    return [key for key in ast.keys() if isinstance(key, str) and key.startswith("secret_")]


# ---------------------------------------------------------------------------
# Culture extraction — name_list mapping
# ---------------------------------------------------------------------------

def extract_cultures(ast: dict) -> dict[str, str]:
    """Return {culture_id: name_list_id} for all cultures that declare a name_list."""
    result: dict[str, str] = {}
    for key, body in ast.items():
        if not isinstance(body, dict):
            continue
        name_list = body.get("name_list")
        if isinstance(name_list, str):
            result[key] = name_list
    return result
