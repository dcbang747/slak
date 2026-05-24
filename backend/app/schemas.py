"""Pydantic schemas for the simulation payload (spec ch. 4)."""

from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Dynasty definitions (Jis_Revised_2 — user-defined dynasties with properties)
# ---------------------------------------------------------------------------

class CultureFaithPeriod(BaseModel):
    """A time-bounded culture/faith assignment for a dynasty."""
    start_year: int
    culture: str = ""
    faith: str = ""


class NameInheritance(BaseModel):
    """Per-dynasty name inheritance probabilities. Must sum to 1.0."""
    grandparent_chance: float = 0.05
    parent_chance: float = 0.05
    no_name_chance: float = 0.90

    @model_validator(mode="after")
    def _check_sum(self) -> "NameInheritance":
        total = self.grandparent_chance + self.parent_chance + self.no_name_chance
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"name_inheritance chances must sum to 1.0 (got {total:.6f})")
        return self


class DynastyDefinition(BaseModel):
    """User-defined dynasty with full properties."""
    id: str                  # Paradox ID, e.g. "dynasty_beor" — used in title_sequences
    name: str = ""           # Display name, e.g. "House of Beor"
    motto: str = ""
    start_year: int = 0      # Year the dynasty is founded
    end_year: int = 9999     # Year the dynasty dies out
    culture_faith_periods: list[CultureFaithPeriod] = Field(default_factory=list)
    gender_law: Literal[
        "AGNATIC", "AGNATIC_COGNATIC", "ABSOLUTE_COGNATIC", "ENATIC_COGNATIC", "ENATIC"
    ] = "AGNATIC_COGNATIC"
    succession: Literal["PRIMOGENITURE", "ULTIMOGENITURE", "SENIORITY"] = "PRIMOGENITURE"
    lowborn_spouses: bool = False
    guaranteed_survival: bool = False
    name_inheritance: NameInheritance = Field(default_factory=NameInheritance)
    languages: list[str] = Field(default_factory=list)
    # Each language entry: "language_id,start_year,end_year" — parsed at simulation time


# ---------------------------------------------------------------------------
# Personality traits (global config)
# ---------------------------------------------------------------------------

class PersonalityTrait(BaseModel):
    weight: float = 1.0
    excludes: list[str] = Field(default_factory=list)


def _default_personality_traits() -> dict[str, PersonalityTrait]:
    """All 28 CK3 personality traits with correct exclusion groups."""
    pairs = [
        ("brave", "craven"), ("calm", "wrathful"), ("chaste", "lustful"),
        ("content", "ambitious"), ("diligent", "lazy"), ("forgiving", "vengeful"),
        ("generous", "greedy"), ("gregarious", "shy"), ("honest", "deceitful"),
        ("humble", "arrogant"), ("just", "arbitrary"), ("patient", "impatient"),
        ("temperate", "gluttonous"), ("trusting", "paranoid"), ("zealous", "cynical"),
    ]
    traits: dict[str, PersonalityTrait] = {}
    for a, b in pairs:
        traits[a] = PersonalityTrait(weight=1.0, excludes=[b])
        traits[b] = PersonalityTrait(weight=1.0, excludes=[a])
    # Three-way exclusion group
    for t in ("compassionate", "callous", "sadistic"):
        others = [x for x in ("compassionate", "callous", "sadistic") if x != t]
        traits[t] = PersonalityTrait(weight=1.0, excludes=others)
    # Four-way exclusion group (fickle/stubborn/eccentric — effectively 3-way mutual)
    for t in ("fickle", "stubborn", "eccentric"):
        others = [x for x in ("fickle", "stubborn", "eccentric") if x != t]
        traits[t] = PersonalityTrait(weight=1.0, excludes=others)
    return traits


class PersonalityTraitsConfig(BaseModel):
    total_traits_per_character: int = 3
    traits: dict[str, PersonalityTrait] = Field(
        default_factory=_default_personality_traits
    )


# ---------------------------------------------------------------------------
# Frontend payload schemas
# ---------------------------------------------------------------------------

class GlobalSettings(BaseModel):
    start_year: int = 6800
    end_year: int = 7000
    maximum_generations: int = 30
    random_seed: int = 1337
    trait_frequency_multiplier: float = 1.0
    ignore_title_generation: bool = False
    enable_secrets: bool = False
    enable_relationships: bool = False
    enable_nicknames: bool = True  # slight chance to give characters a trait/role-appropriate nickname
    personality_traits: PersonalityTraitsConfig = Field(
        default_factory=PersonalityTraitsConfig
    )


class LifeCycleModifiers(BaseModel):
    max_age_difference_between_partners: int = 20
    max_children_per_couple: int = 3
    base_fertility_rate: float = 0.35
    male_bastard_chance: float = 0.05
    female_bastard_chance: float = 0.02
    dynasty_soft_cap: int = 50  # living-member count beyond which fertility damps toward zero
    average_lifespan: int = 70  # mean age at death; calibrates the mortality curve
    average_marriage_age: int = 22  # age dynasty members tend to marry (peak of the marriage hazard)
    gap_between_children: int = 2  # minimum years between a couple's successive births


class ConversionEvent(BaseModel):
    year: int
    new_culture: Optional[str] = None
    new_religion: Optional[str] = None


class DynastySequence(BaseModel):
    dynasty_id: str
    duration_type: Literal["years", "generations"] = "years"
    duration_value: int = 50
    transition_method: Literal["marriage", "usurpation", "extinction"] = "marriage"
    government_type: Optional[str] = None
    liege_title_id: Optional[str] = None
    lowborn_spouses_only: bool = False
    conversions: list[ConversionEvent] = Field(default_factory=list)


class TitleGapFill(BaseModel):
    """A user assignment of one or more dynasties to fill a >50yr gap in a title's
    existing (uploaded) history. The generator draws real members of each dynasty
    (alive within the window, clamped to the dynasty's own start/end years) as
    holders and injects them — chronologically ordered — into the original
    title-history text without touching the existing blocks. Gaps longer than 100
    years may list multiple dynasties; the gap is split evenly among them in order."""
    gap_start_year: int
    gap_end_year: int
    dynasty_ids: list[str] = Field(default_factory=list)


class ParsedFileData(BaseModel):
    """Backend receives raw .txt file contents and re-parses for safety."""
    titles_txt: Optional[str] = None
    traits_txt: Optional[str] = None
    deaths_txt: Optional[str] = None
    name_lists: dict[str, list[str]] = Field(default_factory=dict)
    dynasties_txt: Optional[str] = None
    religions_txt: Optional[str] = None
    secrets_txt: Optional[str] = None
    # Pre-extracted dynasty/house data (passed directly, not re-parsed)
    dynasties: dict = Field(default_factory=dict)


class SimulationPayload(BaseModel):
    """Full global state object serialized from the frontend."""
    global_settings: GlobalSettings
    life_cycle: LifeCycleModifiers
    parsed_files: ParsedFileData
    title_sequences: dict[str, list[DynastySequence]] = Field(default_factory=dict)
    dynasty_definitions: list[DynastyDefinition] = Field(default_factory=list)
    # Per-gap dynasty assignments for titles that have existing uploaded history.
    # Keyed by title id; each entry fills one >50yr vacant gap.
    title_gap_fills: dict[str, list[TitleGapFill]] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Internal entity schemas (spec 4.1)
# ---------------------------------------------------------------------------

class Character(BaseModel):
    id: str
    name: str
    # Exactly one of dynasty/dynasty_house should be set per character.
    # dynasty     → main-house member; outputs "dynasty = dynasty_X"
    # dynasty_house → cadet branch member; outputs "dynasty_house = house_Y"
    dynasty: str = ""
    dynasty_house: str = ""
    religion: str = "default_faith"
    culture: str = "default_culture"
    is_female: bool = False

    father_id: Optional[str] = None
    mother_id: Optional[str] = None
    spouse_ids: list[str] = Field(default_factory=list)
    child_ids: list[str] = Field(default_factory=list)

    # Genetic traits from inheritance/mutation (written as top-level trait = lines)
    traits: list[str] = Field(default_factory=list)

    # Education and personality (assigned during simulation)
    education_skill: str = ""          # random: diplomacy/intrigue/martial/stewardship/learning
    childhood_trait: Optional[str] = None  # derived from education_skill at age 3; top-level trait
    personality_traits: list[str] = Field(default_factory=list)  # drawn at age 16
    personality_trait_date: Optional[str] = None  # YYYY.M.D of 16th birthday

    # Marriage events (sorted chronologically for output)
    marriages: list[dict] = Field(default_factory=list)
    # Each entry: {"date": "YYYY.M.D", "spouse_id": "char_id", "type": "add_spouse"|"add_matrilineal_spouse"}

    # Relationships (set when enable_relationships) — written as dated effect blocks.
    # Each entry: {"date": "YYYY.M.D", "effect": "set_relation_friend", "target_id": "char_id"}
    relationships: list[dict] = Field(default_factory=list)

    # Secrets (set when enable_secrets) — written as dated add_secret effect blocks.
    # Each entry: {"date": "YYYY.M.D", "type": "secret_deviant",
    #              "target_id"?: "char_id", "with_lover"?: True}
    # target_id + block form for murder/murder_attempt/lover; with_lover also emits
    # set_relation_lover in the same effect block (lover / incest-lover secrets).
    secrets: list[dict] = Field(default_factory=list)

    # Languages acquired at birth (written into birth block effect)
    birth_languages: list[str] = Field(default_factory=list)

    # Nickname (set when enable_nicknames) — written as a dated give_nickname effect.
    nickname: Optional[str] = None       # e.g. "nick_the_righteous"
    nickname_date: Optional[str] = None  # YYYY.M.D the nickname is granted (adulthood)

    birth_date: str  # YYYY.M.D
    death_date: Optional[str] = None

    death_reason: Optional[str] = None
    killer_id: Optional[str] = None

    employer_id: Optional[str] = None
    employer_date: Optional[str] = None

    # Internal helpers (not in spec output but used during simulation)
    is_alive: bool = True
    fertility_multiplier: float = 1.0  # Set to 0.0 for extinction last gen
    force_child_house: Optional[str] = None  # Marriage transition override
    is_bastard: bool = False
    is_adopted: bool = False                 # fabricated guaranteed-survival heir → output as adoption
    childhood_trait_assigned: bool = False   # guard: only assign once at age 3
    personality_assigned: bool = False       # guard: only assign once at age 16
