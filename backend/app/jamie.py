"""Jamie's Handy Character History Generator — a faithful Python port.

This is a second, *linear* generator distinct from the main simulation engine
(`simulation.py`). It reproduces the logic of the community Excel/VBA tool
"Jamie's Handy Character History Generator v1.2": a single dynasty grown from one
founder couple, recursing generation by generation, with per-category death
chances, weighted skills/traits/nicknames, and a single-line title-succession
chain.

Differences from the original Excel by design (owner decisions 2026-05):
  * The LotR-specific options are dropped — no Númenórean blood-tier traits and no
    per-generation lifespan decline (`oldDeathAgeReduction` and the "Lowest…"
    floors are gone).
  * Culture, faith and the male/female name pools come from the app's existing
    upload system instead of being typed/stored in the sheet.
  * `father`/`mother` are always assigned by the parents' actual sex (the Excel
    swapped them for matrilineal female lines); everything else is faithful.

All the weighting tables below are copied verbatim from the workbook's `Tables`
sheet. Generation is deterministic given `random_seed`.
"""

from __future__ import annotations

import io
import zipfile
import base64
from random import Random

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Built-in data tables (verbatim from the Excel "Tables" sheet)
# ---------------------------------------------------------------------------

_BATTLE_DEATHS = [
    ("death_battle", 45), ("death_wounds", 10), ("death_siege", 10),
    ("death_maimed", 5), ("death_raid", 5), ("death_beaten", 5),
    ("death_attacked", 5), ("death_duel", 4), ("death_fight", 1),
    ("death_head_ripped_off", 1), ("death_cloven_in_half", 1),
    ("death_viciously_dismembered", 1), ("death_ripped_apart_limb_by_limb", 1),
    ("death_chopped_to_pieces", 1), ("death_heart_ripped_out", 1),
    ("death_skull_cracked_open", 1), ("death_strangled_with_own_intestines", 1),
    ("death_decapitated", 1), ("death_piteously_cut_down", 1),
]

_ILLNESS_DEATHS = [
    ("death_smallpox", 20), ("death_typhus", 20), ("death_consumption", 15),
    ("death_cancer", 10), ("death_pneumonic", 10), ("death_leper", 10),
    ("death_ill", 5), ("death_gout_ridden", 2), ("death_great_pox", 2),
    ("death_treatment", 2), ("death_attempted_treatment", 2),
    ("death_bubonic_plague", 1), ("death_stress", 1),
]

_INTRIGUE_DEATHS = [
    ("death_accident", 10), ("death_plotting", 10), ("death_dungeon", 10),
    ("death_murder", 5), ("death_ended_on_feast_table", 5),
    ("death_script_cruelty", 5), ("death_disappearance", 5), ("death_poison", 5),
    ("death_horse_riding_accident", 5), ("death_training_accident", 5),
    ("death_hunting_accident", 5), ("death_mysterious", 5), ("death_torture", 5),
    ("death_vanished", 5), ("death_drowned", 5), ("death_whipping", 2),
    ("death_fall", 2), ("death_feast_accident", 2), ("death_dog_attack", 2),
    ("death_crushed", 2),
]

_SEXUALITY = [("heterosexual", 93), ("homosexual", 2), ("bisexual", 3), ("asexual", 2)]

# 16 adjacent opposite pairs (rows 0-31) followed by a mutually-exclusive trio.
_PERSONALITY = [
    "brave", "craven", "calm", "wrathful", "chaste", "lustful", "content",
    "ambitious", "diligent", "lazy", "fickle", "stubborn", "forgiving",
    "vengeful", "generous", "greedy", "gregarious", "shy", "honest", "deceitful",
    "humble", "arrogant", "just", "arbitrary", "patient", "impatient",
    "temperate", "gluttonous", "trusting", "paranoid", "zealous", "cynical",
    "compassionate", "callous", "sadistic",
]

# Exclusion sets by index: each of the 16 pairs excludes its partner; the final
# trio (32,33,34) is mutually exclusive.
def _build_personality_excludes() -> list[set[int]]:
    ex: list[set[int]] = [set() for _ in _PERSONALITY]
    for i in range(0, 32, 2):
        ex[i].add(i + 1)
        ex[i + 1].add(i)
    trio = (32, 33, 34)
    for a in trio:
        for b in trio:
            if a != b:
                ex[a].add(b)
    return ex

_PERSONALITY_EXCLUDES = _build_personality_excludes()

_EDUCATION_TIERS = [(1, 20), (2, 40), (3, 30), (4, 20)]

# Skill-level distribution: per level, a weight for each of the 6 skills
# (diplomacy, martial, stewardship, intrigue, learning, prowess).
_SKILL_LEVELS = [
    (1, [6, 3, 6, 3, 6, 3]), (2, [12, 6, 12, 6, 12, 6]), (3, [18, 12, 18, 12, 18, 12]),
    (4, [20, 18, 20, 18, 20, 18]), (5, [18, 20, 18, 20, 18, 20]),
    (6, [12, 18, 12, 18, 12, 18]), (7, [6, 12, 6, 12, 6, 12]), (8, [3, 6, 3, 6, 3, 6]),
    (9, [1, 3, 1, 3, 1, 3]), (10, [1, 1, 1, 1, 1, 1]), (11, [0, 1, 0, 1, 0, 1]),
]
_SKILL_NAMES = ["diplomacy", "martial", "stewardship", "intrigue", "learning", "prowess"]

_NO_NICKNAME_WEIGHT = 5000
_ACTIVE_NICKNAMES = [
    "nick_the_unready", "nick_the_quarreller", "nick_the_rash", "nick_the_foolish",
    "nick_the_hotspur", "nick_the_traitor", "nick_the_conqueror", "nick_the_great",
    "nick_the_hammer", "nick_the_victorious", "nick_the_lionheart", "nick_the_avenger",
    "nick_the_undefeated", "nick_the_triumphant", "nick_the_big_halberd",
    "nick_the_vanquisher", "nick_the_inevitable", "nick_the_courageous",
    "nick_the_brilliant", "nick_the_peacemaker", "nick_the_culture_wall",
    "nick_the_dragon", "nick_the_devourer", "nick_the_troubadour", "nick_the_glorious",
    "nick_the_ecumenist", "nick_the_sword_of_god", "nick_the_shepherd", "nick_the_judge",
    "nick_the_thunderbolt", "nick_the_whirlwind", "nick_the_unrestrained",
    "nick_the_greedy", "nick_the_timid", "nick_the_truthspeaker", "nick_the_worthy",
    "nick_the_unworthy", "nick_the_snorer", "nick_troll_slayer", "nick_the_unfaithful",
    "nick_the_quick", "nick_the_beguiling", "nick_the_lewd", "nick_the_whisperer",
    "nick_the_deceiver", "nick_the_crow", "nick_the_trickster", "nick_the_sly",
    "nick_the_mindbreaker", "nick_the_flayer", "nick_the_heartbreaker", "nick_the_fox",
    "nick_the_shrewd", "nick_the_gracious", "nick_the_magnanimous", "nick_the_affable",
    "nick_the_bard", "nick_the_diplomat", "nick_the_magnificent", "nick_the_silly",
    "nick_the_bully", "nick_the_architect", "nick_the_lawgiver", "nick_the_just",
    "nick_the_benevolent", "nick_the_generous", "nick_the_gardener", "nick_the_poet",
    "nick_the_selfish", "nick_the_meticulous", "nick_the_elegant", "nick_the_ironside",
    "nick_the_ruthless", "nick_the_brute", "nick_the_bear", "nick_the_lion",
    "nick_the_wolf", "nick_the_bold", "nick_the_brave", "nick_the_hunter",
    "nick_the_fearless", "nick_the_fowler", "nick_the_tactician", "nick_the_overseer",
    "nick_the_guardian", "nick_the_chivalrous", "nick_the_valiant", "nick_the_butcher",
    "nick_the_bloody", "nick_the_stalwart", "nick_the_merciless", "nick_the_imperious",
    "nick_the_fury", "nick_feareater", "nick_the_hawk", "nick_the_unrelenting",
    "nick_the_black_adder", "nick_the_eager", "nick_the_wise", "nick_the_scholar",
    "nick_the_sage", "nick_the_philosopher", "nick_the_truthseeker", "nick_the_chronicler",
    "nick_the_historian", "nick_the_silent", "nick_the_fishy", "nick_the_immortal",
    "nick_the_impaler", "nick_the_tormentor", "nick_the_depraved", "nick_the_monster",
    "nick_the_cruel", "nick_the_wicked", "nick_the_accursed", "nick_the_devil",
    "nick_the_black", "nick_the_oathbreaker", "nick_the_demon", "nick_the_theologian",
    "nick_the_enlightened", "nick_the_holy", "nick_the_confessor", "nick_the_divine",
    "nick_the_anointed", "nick_the_flash", "nick_the_passionate", "nick_the_able",
    "nick_the_compassionate", "nick_the_noble", "nick_the_gentle", "nick_the_good",
    "nick_the_kind", "nick_the_merry", "nick_the_honorable", "nick_the_loyal",
    "nick_the_trustworthy", "nick_the_honest", "nick_the_great_and_terrible",
    "nick_the_terrible", "nick_the_tyrant", "nick_the_betrayer", "nick_the_shy",
    "nick_the_bastard", "nick_the_proud", "nick_the_strong", "nick_the_handsome",
    "nick_the_fair", "nick_the_mad", "nick_the_weak", "nick_the_little",
    "nick_the_trembling", "nick_the_insane", "nick_the_defender_of_highgod",
    "nick_the_sea_king", "nick_the_defiant", "nick_the_stonefaced", "nick_the_dry",
    "nick_the_joyless", "nick_lacks_laughs", "nick_the_dull", "nick_tiny",
    "nick_little", "nick_the_savage",
]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class JamieSettings(BaseModel):
    """Mirrors the Excel `Inputs` sheet (minus the dropped LotR fields)."""
    dynasty_id: str = "dynasty_new"
    faith_id: str = "faith_fallback"
    culture_id: str = "culture_fallback"
    char_id_string: str = "myline"
    initial_char_id: int = 1
    start_birth_year: int = 6897
    title_id: str = ""  # optional: wrap the succession chain in `<title_id> = { … }`

    generations: int = Field(4, ge=1, le=12)
    generation_siblings: int = Field(3, ge=0)

    marriage_min_age: int = 16
    marriage_max_age: int = 35
    agediff_min: int = -3
    agediff_max: int = 3

    childbirth_min_age: int = 20
    childbirth_max_age: int = 40
    children_max: int = Field(5, ge=1)

    battle_death_chance: float = 0.10
    battle_death_min_age: int = 20
    battle_death_max_age: int = 65
    ill_death_chance: float = 0.10
    ill_death_min_age: int = 25
    ill_death_max_age: int = 65
    intrigue_death_chance: float = 0.05
    intrigue_death_min_age: int = 25
    intrigue_death_max_age: int = 65
    old_death_min_age: int = 60
    old_death_max_age: int = 85

    dominant_sex: str = "MALE"  # MALE | FEMALE | EQUAL

    option_male_line: bool = False
    option_sexuality: bool = True
    option_nicknames: bool = True
    option_personality_traits: bool = True
    option_skills: bool = True
    option_education: bool = True
    option_heroes: bool = True
    option_loc_keys: bool = False

    hero_chance: float = 0.01
    hero_buff_min: int = 5
    hero_buff_max: int = 10

    random_seed: int | None = None


class JamiePayload(BaseModel):
    settings: JamieSettings
    male_names: list[str] = Field(default_factory=list)
    female_names: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class _Char:
    __slots__ = (
        "id", "id_str", "sex", "birth_year", "death_year", "death_cause",
        "dynasty_member", "father_id", "mother_id", "marriage_year", "spouse_id",
        "name", "is_matrilineal", "sexuality", "traits", "skills", "education",
        "nickname", "nickname_year", "birth_md", "death_md",
    )

    def __init__(self):
        self.spouse_id = None
        self.father_id = None
        self.mother_id = None
        self.marriage_year = None
        self.is_matrilineal = False
        self.sexuality = None
        self.traits = []
        self.skills = {}
        self.education = None
        self.nickname = None
        self.nickname_year = None


class JamieGenerator:
    def __init__(self, payload: JamiePayload):
        self.s = payload.settings
        self.male_names = payload.male_names or ["Unnamed"]
        self.female_names = payload.female_names or ["Unnamed"]
        seed = self.s.random_seed if self.s.random_seed is not None else 0
        self.rng = Random(seed)

        self.char_id = self.s.initial_char_id
        self.titles_complete = False
        self.chars: dict[str, _Char] = {}
        self.order: list[str] = []          # creation order (for output)
        self.title_line: list[str] = []     # ordered ids forming the succession chain

    # --- small helpers -----------------------------------------------------
    def _id(self, n: int) -> str:
        return f"{self.s.char_id_string}{n}"

    def rb(self, a: int, b: int) -> int:
        """Inclusive RandBetween; tolerates a > b (Excel would error)."""
        a, b = int(a), int(b)
        if a > b:
            a, b = b, a
        return self.rng.randint(a, b)

    def _weighted(self, items: list[tuple[str, int]]) -> str:
        total = sum(w for _, w in items)
        r = self.rng.random() * total
        acc = 0.0
        for val, w in items:
            acc += w
            if acc >= r:
                return val
        return items[-1][0]

    def _md(self) -> tuple[int, int]:
        return self.rb(1, 12), self.rb(1, 28)

    # --- attribute rolls (faithful to the VBA Get* subs) -------------------
    def _death_age(self, r: float, sex: str) -> int:
        s = self.s
        battle = s.battle_death_chance if sex == "Male" else 0.0
        if r < battle:
            return self.rb(s.battle_death_min_age, s.battle_death_max_age)
        if r < battle + s.ill_death_chance:
            return self.rb(s.ill_death_min_age, s.ill_death_max_age)
        if r < battle + s.ill_death_chance + s.intrigue_death_chance:
            return self.rb(s.intrigue_death_min_age, s.intrigue_death_max_age)
        return self.rb(s.old_death_min_age, s.old_death_max_age)

    def _death_cause(self, r: float, sex: str) -> str:
        s = self.s
        battle = s.battle_death_chance if sex == "Male" else 0.0
        if r < battle:
            return self._weighted(_BATTLE_DEATHS)
        if r < battle + s.ill_death_chance:
            return self._weighted(_ILLNESS_DEATHS)
        if r < battle + s.ill_death_chance + s.intrigue_death_chance:
            return self._weighted(_INTRIGUE_DEATHS)
        return "death_natural_causes"

    def _personality(self) -> list[str]:
        picks: list[int] = []
        attempts = 0
        while len(picks) < 3 and attempts < 200:
            attempts += 1
            cand = self.rng.randrange(len(_PERSONALITY))
            if cand in picks:
                continue
            if any(cand in _PERSONALITY_EXCLUDES[p] for p in picks):
                continue
            picks.append(cand)
        return [_PERSONALITY[i] for i in picks]

    def _skills(self, sex: str) -> tuple[dict[str, int], str | None]:
        s = self.s
        hero = sex == "Male" and s.option_heroes and self.rng.random() <= s.hero_chance
        skills: dict[str, int] = {}
        best_val, best_type = -1, None
        for col, name in enumerate(_SKILL_NAMES):
            items = [(lvl, w[col]) for lvl, w in _SKILL_LEVELS]
            total = sum(w for _, w in items)
            r = self.rng.random() * total
            acc = 0.0
            level = items[-1][0]
            for lvl, w in items:
                acc += w
                if acc >= r:
                    level = lvl
                    break
            buff = self.rb(s.hero_buff_min, s.hero_buff_max) if hero else 0
            val = level + buff
            skills[name] = val
            # Prowess does not contribute to education choice (matches the VBA).
            if name != "prowess" and val > best_val:
                best_val, best_type = val, name
        education = None
        if s.option_education and best_type:
            if hero:
                education = f"education_{best_type}_4"
            else:
                tier = self._weighted([(str(t), w) for t, w in _EDUCATION_TIERS])
                education = f"education_{best_type}_{tier}"
        return skills, education

    def _nickname(self) -> str | None:
        total = _NO_NICKNAME_WEIGHT + len(_ACTIVE_NICKNAMES)
        r = self.rng.random() * total
        if r < _NO_NICKNAME_WEIGHT:
            return None
        return _ACTIVE_NICKNAMES[self.rng.randrange(len(_ACTIVE_NICKNAMES))]

    # --- character creation ------------------------------------------------
    def _add_character(self, cid: int, sex: str, birth_year: int, death_year: int,
                       death_cause: str, dynasty_member: bool, title_flag: bool,
                       marriage_year: int | None = None,
                       father_id: str | None = None, mother_id: str | None = None) -> _Char:
        s = self.s
        c = _Char()
        c.id = cid
        c.id_str = self._id(cid)
        c.sex = sex
        c.birth_year = birth_year
        c.death_year = death_year
        c.death_cause = death_cause
        c.dynasty_member = dynasty_member
        c.father_id = father_id
        c.mother_id = mother_id
        c.marriage_year = marriage_year
        c.name = self.rng.choice(self.male_names if sex == "Male" else self.female_names)

        if s.option_sexuality:
            c.sexuality = self._weighted(_SEXUALITY)
        if s.option_personality_traits:
            c.traits = self._personality()
        if s.option_skills:
            c.skills, c.education = self._skills(sex)

        c.birth_md = self._md()

        # Nickname (dynasty heirs of the dominant sex, per the VBA), placed a year after birth.
        is_heir = dynasty_member and (
            (sex == "Male" and s.dominant_sex == "MALE")
            or (sex == "Female" and s.dominant_sex == "FEMALE")
            or s.dominant_sex == "EQUAL"
        )
        if s.option_nicknames and is_heir:
            nick = self._nickname()
            if nick:
                c.nickname = nick
                c.nickname_year = birth_year + 1

        # Spouse pointer (the next id is created immediately after) + matrilineal flag.
        if is_heir and marriage_year is not None:
            c.spouse_id = self._id(cid + 1)
            c.is_matrilineal = (sex == "Female")

        c.death_md = self._md()

        self.chars[c.id_str] = c
        self.order.append(c.id_str)
        if title_flag:
            self.title_line.append(c.id_str)
        return c

    # --- recursive family build (mirrors AddChildren) ----------------------
    def _add_children(self, father_id: str, mother_id: str, marriage_year: int,
                      childbirth_min: int, childbirth_max: int, generation: int):
        s = self.s
        if generation > s.generations:
            return

        children = self.rb(1, s.children_max)
        if generation <= s.generations - s.generation_siblings:
            children = 1
        has_dominant = False

        for j in range(1, children + 1):
            # Sex assignment
            if self.rng.random() > 0.5:
                sex = "Male"
                if s.dominant_sex == "MALE":
                    has_dominant = True
            else:
                sex = "Female"
                if s.dominant_sex == "FEMALE":
                    has_dominant = True

            in_single_line = generation <= s.generations - s.generation_siblings
            if j == children and not has_dominant and s.option_male_line and s.dominant_sex == "MALE":
                sex = "Male"
            if j == children and not has_dominant and s.option_male_line and s.dominant_sex == "FEMALE":
                sex = "Female"
            if in_single_line and s.dominant_sex == "MALE":
                sex = "Male"
            if in_single_line and s.dominant_sex == "FEMALE":
                sex = "Female"
            if in_single_line and s.dominant_sex == "EQUAL":
                sex = "Male" if self.rng.random() < 0.5 else "Female"

            # Birth, spaced from the previous sibling
            hi = (childbirth_max - childbirth_min) // max(1, children) + childbirth_min
            birth_year = self.rb(childbirth_min, max(childbirth_min, hi))
            childbirth_min = birth_year + 1

            is_dominant = (
                (sex == "Male" and s.dominant_sex == "MALE")
                or (sex == "Female" and s.dominant_sex == "FEMALE")
                or s.dominant_sex == "EQUAL"
            )

            child_marriage = birth_year + self.rb(s.marriage_min_age, s.marriage_max_age)
            r = self.rng.random()
            if sex == "Male":
                death_year = max(child_marriage + 10, birth_year + self._death_age(r, sex))
            else:
                death_year = birth_year + self._death_age(r, sex)
            death_cause = self._death_cause(r, sex)

            heir_death = death_year if is_dominant else None

            # Title flag: the dominant-sex main line, until the chain is complete.
            title_flag = is_dominant and not self.titles_complete

            child = self._add_character(
                self.char_id, sex, birth_year, death_year, death_cause,
                dynasty_member=is_dominant, title_flag=title_flag,
                marriage_year=child_marriage,
                father_id=father_id, mother_id=mother_id,
            )
            child_id = self.char_id
            if generation == s.generations:
                self.titles_complete = True
            self.char_id += 1

            # Dominant-sex children take a lowborn spouse and continue the line.
            spawn_spouse = (sex == "Male" and s.dominant_sex != "FEMALE") or \
                           (sex == "Female" and s.dominant_sex != "MALE")
            if spawn_spouse:
                spouse_sex = "Female" if sex == "Male" else "Male"
                # Spouse age at marriage ≈ heir's marriage age ± agediff, floored at 17.
                spouse_age = max(17, (child_marriage - birth_year) + self.rb(s.agediff_min, s.agediff_max))
                spouse_birth = child_marriage - spouse_age
                rs = self.rng.random()
                spouse_death = max(child_marriage + 10, spouse_birth + self._death_age(rs, spouse_sex))
                spouse_cause = self._death_cause(rs, spouse_sex)
                self._add_character(
                    self.char_id, spouse_sex, spouse_birth, spouse_death, spouse_cause,
                    dynasty_member=False, title_flag=False,
                )
                spouse_id = self.char_id
                self.char_id += 1

                # Resolve father/mother by actual sex (output stays valid for matrilineal lines).
                if sex == "Male":
                    nxt_father, nxt_mother = self._id(child_id), self._id(spouse_id)
                else:
                    nxt_father, nxt_mother = self._id(spouse_id), self._id(child_id)

                cb_min = max(child_marriage, spouse_birth + s.childbirth_min_age)
                cb_max = min(spouse_death, heir_death or death_year, spouse_birth + s.childbirth_max_age)
                self._add_children(nxt_father, nxt_mother, child_marriage, cb_min, cb_max, generation + 1)

    # --- entry point (mirrors GenerateFamily) ------------------------------
    def run(self):
        s = self.s
        birth_year = s.start_birth_year
        marriage_year = birth_year + self.rb(s.marriage_min_age, s.marriage_max_age)

        if s.dominant_sex == "FEMALE":
            founder_sex, spouse_sex = "Female", "Male"
        elif s.dominant_sex == "MALE":
            founder_sex, spouse_sex = "Male", "Female"
        else:
            if self.rng.random() < 0.5:
                founder_sex, spouse_sex = "Male", "Female"
            else:
                founder_sex, spouse_sex = "Female", "Male"

        r = self.rng.random()
        founder_death = max(marriage_year + 10, birth_year + self._death_age(r, founder_sex))
        founder_cause = self._death_cause(r, founder_sex)

        self._add_character(
            self.char_id, founder_sex, birth_year, founder_death, founder_cause,
            dynasty_member=True, title_flag=True, marriage_year=marriage_year,
        )
        founder_id = self.char_id
        self.char_id += 1

        # Founder's spouse
        sp_birth = marriage_year - max(17, self.rb(s.agediff_min, s.agediff_max))
        rs = self.rng.random()
        sp_death = max(marriage_year + 10, sp_birth + self._death_age(rs, spouse_sex))
        sp_cause = self._death_cause(rs, spouse_sex)
        self._add_character(
            self.char_id, spouse_sex, sp_birth, sp_death, sp_cause,
            dynasty_member=False, title_flag=False,
        )
        spouse_id = self.char_id
        self.char_id += 1

        if founder_sex == "Male":
            father_id, mother_id = self._id(founder_id), self._id(spouse_id)
        else:
            father_id, mother_id = self._id(spouse_id), self._id(founder_id)

        cb_min = max(marriage_year, sp_birth + s.childbirth_min_age)
        cb_max = min(sp_death, founder_death, sp_birth + s.childbirth_max_age)
        self._add_children(father_id, mother_id, marriage_year, cb_min, cb_max, 2)
        return self


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _name_token(name: str, loc_keys: bool) -> str:
    return name if loc_keys else f'"{name}"'


def render_character_history(gen: JamieGenerator) -> str:
    s = gen.s
    out: list[str] = []
    for cid in gen.order:
        c = gen.chars[cid]
        out.append(f"{c.id_str} = {{")
        out.append(f"    name = {_name_token(c.name, s.option_loc_keys)}")
        out.append("")
        if c.dynasty_member:
            out.append(f"    dynasty = {s.dynasty_id}")
        out.append(f"    religion = {s.faith_id}")
        out.append(f"    culture = {s.culture_id}")
        if c.sex == "Female":
            out.append("    female = yes")
        out.append("")
        if c.father_id:
            out.append(f"    father = {c.father_id}")
            out.append(f"    mother = {c.mother_id}")
            out.append("")
        if c.sexuality:
            out.append(f"    sexuality = {c.sexuality}")
        for t in c.traits:
            out.append(f"    trait = {t}")
        if c.skills:
            for name in _SKILL_NAMES:
                if name in c.skills:
                    out.append(f"    {name} = {c.skills[name]}")
        if c.education:
            out.append(f"    trait = {c.education}")
        out.append("")

        bm, bd = c.birth_md
        out.append(f"    {c.birth_year}.{bm}.{bd} = {{")
        out.append("        birth = yes")
        out.append("    }")

        if c.nickname:
            nm, nd = gen._md()
            out.append(f"    {c.nickname_year}.{nm}.{nd} = {{")
            out.append(f"        give_nickname = {c.nickname}")
            out.append("        effect = {")
            out.append("            add_character_flag = had_nickname_event")
            out.append("        }")
            out.append("    }")

        if c.spouse_id and c.marriage_year is not None:
            mm, md = gen._md()
            verb = "add_matrilineal_spouse" if c.is_matrilineal else "add_spouse"
            out.append(f"    {c.marriage_year}.{mm}.{md} = {{")
            out.append(f"        {verb} = {c.spouse_id}")
            out.append("    }")

        dm, dd = c.death_md
        out.append(f"    {c.death_year}.{dm}.{dd} = {{")
        out.append(f"        death = {{ death_reason = {c.death_cause} }}")
        out.append("    }")
        out.append("}")
        out.append("")
    return "\n".join(out)


def _succession_events(gen: JamieGenerator) -> list[tuple[str, str, str]]:
    """[(date, holder_id, name)] — founder at birth, each successor at predecessor's death."""
    events: list[tuple[str, str, str]] = []
    line = gen.title_line
    if not line:
        return events
    founder = gen.chars[line[0]]
    bm, bd = founder.birth_md
    events.append((f"{founder.birth_year}.{bm}.{bd}", founder.id_str, founder.name))
    for i in range(1, len(line)):
        pred = gen.chars[line[i - 1]]
        succ = gen.chars[line[i]]
        dm, dd = pred.death_md
        events.append((f"{pred.death_year}.{dm}.{dd}", succ.id_str, succ.name))
    return events


def render_title_history(gen: JamieGenerator) -> str:
    events = _succession_events(gen)
    if not events:
        return ""
    title_id = gen.s.title_id.strip()
    indent = "    " if title_id else ""
    lines: list[str] = []
    if title_id:
        lines.append(f"{title_id} = {{")
    for date, holder, name in events:
        lines.append(f"{indent}{date} = {{")
        lines.append(f"{indent}    holder = {holder} #{name}")
        lines.append(f"{indent}}}")
    if title_id:
        lines.append("}")
    return "\n".join(lines)


def build_family_tree(gen: JamieGenerator) -> dict:
    s = gen.s
    ruler_ids = {h for _, h, _ in _succession_events(gen)}
    # Mutual spouse links for clean tree layout.
    spouse_of: dict[str, set[str]] = {}
    for cid, c in gen.chars.items():
        if c.spouse_id:
            spouse_of.setdefault(cid, set()).add(c.spouse_id)
            spouse_of.setdefault(c.spouse_id, set()).add(cid)

    characters = {}
    for cid, c in gen.chars.items():
        characters[cid] = {
            "name": c.name,
            "dynasty": s.dynasty_id if c.dynasty_member else "",
            "is_female": c.sex == "Female",
            "birth_date": f"{c.birth_year}.{c.birth_md[0]}.{c.birth_md[1]}",
            "death_date": f"{c.death_year}.{c.death_md[0]}.{c.death_md[1]}",
            "father_id": c.father_id or "",
            "mother_id": c.mother_id or "",
            "is_bastard": False,
            "spouse_ids": sorted(spouse_of.get(cid, set())),
            "is_ruler": cid in ruler_ids,
        }
    title_key = s.title_id.strip() or s.dynasty_id
    title_holders = {title_key: [[date, holder] for date, holder, _ in _succession_events(gen)]}
    return {"characters": characters, "title_holders": title_holders}


def package_zip(gen: JamieGenerator) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("generated_character_history.txt", render_character_history(gen))
        zf.writestr("generated_title_history.txt", render_title_history(gen))
    return buf.getvalue()


def run_jamie_generation(payload_json: dict) -> dict:
    """Parse → build family → render → ZIP. Mirrors generation.run_generation's contract."""
    payload = JamiePayload(**payload_json)
    gen = JamieGenerator(payload).run()
    return {
        "characters": len(gen.chars),
        "titles_with_history": 1 if gen.title_line else 0,
        "family_tree": build_family_tree(gen),
        "zip_b64": base64.b64encode(package_zip(gen)).decode("ascii"),
    }
