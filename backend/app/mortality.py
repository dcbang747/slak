"""Mortality / death-reason logic.

Death reasons are hardcoded (per spec amendment): a baseline natural death,
an old-age death past 60, and trait-triggered deaths for characters carrying a
specific genetic health trait. No death-reason file upload is required.
"""

import math
import random
from typing import Optional

from .schemas import Character


_GOMPERTZ_STEEPNESS = 0.10   # hazard growth rate; death-age spread ≈ 1.28 / G ≈ 13 yrs
_EULER_MASCHERONI = 0.5772156649


def base_mortality(age: int, avg_lifespan: float = 70.0) -> float:
    """Annual death probability via a Gompertz hazard.

    The scale is solved so the *mean* age at death equals `avg_lifespan`:
    for hazard h(t) = A·e^(G·t), the Gompertz mean is (1/G)·ln(G/A) − γ/G, so
    A = G·e^(−(G·avg_lifespan + γ)). Deaths cluster around `avg_lifespan` with a
    spread of ~13 years, and the probability rises steeply past it (capped at
    0.99), so characters rarely reach extreme ages.
    """
    if age < 0:
        return 0.0
    g = _GOMPERTZ_STEEPNESS
    a = g * math.exp(-(g * max(avg_lifespan, 1.0) + _EULER_MASCHERONI))
    return min(a * math.exp(g * age), 0.99)


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
    avg_lifespan: float = 70.0,
) -> Optional[str]:
    """If the character dies this year, return the death reason ID; else None."""
    age = year - int(character.birth_date.split(".")[0])
    if age < 0:
        return None
    p = base_mortality(age, avg_lifespan)
    if rng.random() < p:
        return pick_death_reason(character, age, rng)
    return None
