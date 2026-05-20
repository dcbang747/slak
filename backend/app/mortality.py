"""Mortality / death-reason logic.

Death reasons are hardcoded (per spec amendment): a baseline natural death,
an old-age death past 60, and trait-triggered deaths for characters carrying a
specific genetic health trait. No death-reason file upload is required.
"""

import math
import random
from typing import Optional

from .schemas import Character


def base_mortality(age: int) -> float:
    """Exponential mortality curve.

    Roughly: ~0.2% at infancy, ~1% at 30, ~6% at 60, ~30% at 80, ~80%+ past 90.
    """
    if age < 1:
        return 0.05  # infant mortality bump
    # exp curve calibrated so exp(age/18) - 1 normalized
    p = (math.exp(age / 18.0) - 1.0) / 800.0
    return min(p, 0.99)


# Trait → death reason. A character is only eligible for a trait-death if they
# carry the trait.
_TRAIT_DEATH_REASONS: dict[str, str] = {
    "faltering_heart": "death_heart_attack",
    "fragile_bones": "death_broken_bones",
    "giant": "death_giant",
    "spindly": "death_spindly",
    "wheezing": "death_wheezing",
    "bleeder": "death_bleeder",
    "physique_bad_1": "death_physique_bad_1",
    "physique_bad_2": "death_physique_bad_2",
    "physique_bad_3": "death_physique_bad_3",
}

# Non-natural deaths used for hostile transitions (usurpation, murder).
_HOSTILE_DEATHS: list[str] = ["death_murder", "death_battle", "death_execution"]


def pick_death_reason(character: Character, age: int, rng: random.Random) -> str:
    """Pick a natural death reason, weighting trait- and age-triggered ones.

    Always includes death_natural_causes as the baseline. Adds death_old_age for
    characters past 60, and any trait-specific death the character qualifies for.
    """
    char_traits = set(character.traits)
    weighted: list[tuple[str, float]] = [("death_natural_causes", 1.0)]
    if age >= 60:
        weighted.append(("death_old_age", 3.0))
    for trait, reason in _TRAIT_DEATH_REASONS.items():
        if trait in char_traits:
            weighted.append((reason, 8.0))

    total = sum(w for _, w in weighted)
    pick = rng.random() * total
    acc = 0.0
    for reason, w in weighted:
        acc += w
        if pick <= acc:
            return reason
    return weighted[-1][0]


def pick_hostile_death(rng: random.Random) -> str:
    """Pick a non-natural death (murder, battle, execution)."""
    return rng.choice(_HOSTILE_DEATHS)


def annual_death_check(
    character: Character,
    year: int,
    rng: random.Random,
) -> Optional[str]:
    """If the character dies this year, return the death reason ID; else None."""
    age = year - int(character.birth_date.split(".")[0])
    if age < 0:
        return None
    p = base_mortality(age)
    if rng.random() < p:
        return pick_death_reason(character, age, rng)
    return None
