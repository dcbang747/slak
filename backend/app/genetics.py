"""Genetics inheritance algorithm (spec ch. 6.1)."""

import random
from typing import Optional


def _build_indices(traits: list[dict]) -> tuple[dict, dict, dict]:
    """Return (by_id, by_group_level, group_max_level) lookups."""
    by_id = {t["id"]: t for t in traits}

    by_group_level: dict[str, dict[int, str]] = {}
    group_max: dict[str, int] = {}
    for t in traits:
        g = t["group"]
        lvl = t["level"]
        by_group_level.setdefault(g, {})[lvl] = t["id"]
        group_max[g] = max(group_max.get(g, 0), lvl)
    return by_id, by_group_level, group_max


def _resolve_conflicts(traits: set[str], by_id: dict) -> list[str]:
    """Remove traits that are listed as opposites of already-accepted traits.

    Iterates in sorted order for determinism; first accepted trait wins and
    marks all its opposites as excluded.
    """
    kept: list[str] = []
    excluded: set[str] = set()
    for t_id in sorted(traits):
        if t_id in excluded:
            continue
        kept.append(t_id)
        for opp in by_id.get(t_id, {}).get("opposites", []):
            excluded.add(opp)
    return kept


def _trait_at(by_group_level: dict, group: str, level: int) -> Optional[str]:
    return by_group_level.get(group, {}).get(level)


def inherit_traits(
    mother_traits: list[str],
    father_traits: list[str],
    registry: list[dict],
    rng: random.Random,
    trait_multiplier: float = 1.0,
) -> list[str]:
    """Compute the genetic trait list for a child given the parents'.

    trait_multiplier scales birth_chance and random_creation before rolling.
    Values > 1.0 increase frequency; < 1.0 reduce it.
    """
    by_id, by_group_level, group_max = _build_indices(registry)

    # 1. Filter parental traits down to those present in the registry
    mom = [t for t in mother_traits if t in by_id]
    dad = [t for t in father_traits if t in by_id]

    # Cancel opposite pairs across parents
    cancelled: set[str] = set()
    for mt in mom:
        opps = set(by_id[mt]["opposites"])
        for dt in dad:
            if dt in opps:
                cancelled.add(mt)
                cancelled.add(dt)
    mom = [t for t in mom if t not in cancelled]
    dad = [t for t in dad if t not in cancelled]

    inherited: set[str] = set()

    mom_by_group: dict[str, str] = {by_id[t]["group"]: t for t in mom}
    dad_by_group: dict[str, str] = {by_id[t]["group"]: t for t in dad}
    all_groups = set(mom_by_group) | set(dad_by_group)

    for group in all_groups:
        m = mom_by_group.get(group)
        d = dad_by_group.get(group)
        if m and d:
            # Homogenous — both parents share the group
            highest_level = max(by_id[m]["level"], by_id[d]["level"])
            # Scale thresholds: higher multiplier = more inheritance
            inherit_threshold = min(0.80 * trait_multiplier, 1.0)
            roll = rng.random()
            if roll < inherit_threshold:
                chosen = _trait_at(by_group_level, group, highest_level)
            elif roll < min(1.00 * trait_multiplier, 1.0):
                target = min(highest_level + 1, group_max[group])
                chosen = _trait_at(by_group_level, group, target)
            else:
                chosen = None
            if chosen:
                inherited.add(chosen)
        else:
            # Heterogenous — only one parent has it
            parent_trait_id = m or d
            parent_level = by_id[parent_trait_id]["level"]
            inherit_threshold = min(0.50 * trait_multiplier, 1.0)
            parent_threshold = min(0.60 * trait_multiplier, 1.0)
            roll = rng.random()
            if roll < inherit_threshold:
                target = max(parent_level - 1, 1)
                chosen = _trait_at(by_group_level, group, target)
                if chosen:
                    inherited.add(chosen)
            elif roll < parent_threshold:
                inherited.add(parent_trait_id)

    # 4. Spontaneous mutation — for groups neither parent has.
    # Apply an extra 0.1 scale so novel mutations are very rare even at multiplier=1.
    inherited_groups = {by_id[t]["group"] for t in inherited}
    for trait in registry:
        if trait["group"] in inherited_groups:
            continue
        if trait["random_creation"] <= 0:
            continue
        scaled_rc = min(trait["random_creation"] * trait_multiplier * 0.1, 1.0)
        if rng.random() < scaled_rc:
            if by_id[trait["id"]]["level"] == 1:
                inherited.add(trait["id"])
                inherited_groups.add(trait["group"])

    return _resolve_conflicts(inherited, by_id)


def roll_birth_traits(
    registry: list[dict],
    rng: random.Random,
    trait_multiplier: float = 1.0,
) -> list[str]:
    """Roll traits for a founder character (no parents). Uses birth_chance."""
    by_id = {t["id"]: t for t in registry}
    chosen: dict[str, str] = {}  # group -> trait_id
    for trait in registry:
        if trait["birth_chance"] <= 0:
            continue
        if trait["level"] != 1:
            continue
        scaled_bc = min(trait["birth_chance"] * trait_multiplier, 1.0)
        if rng.random() < scaled_bc:
            chosen[trait["group"]] = trait["id"]
    return _resolve_conflicts(set(chosen.values()), by_id)
