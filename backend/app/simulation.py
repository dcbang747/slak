"""Main chronological simulation loop and title-transition orchestration.

Implements:
  * Annual tick: aging, mortality, fertility (children), succession
  * Title transitions per chapter 7 (marriage, usurpation, extinction)
  * Cascade rule for high-tier dynasty sequences
  * Personality trait and childhood trait assignment
  * Per-dynasty name inheritance, language assignment
"""

from __future__ import annotations
import re
import random
from typing import Callable, Optional

from .schemas import (
    Character,
    DynastyDefinition,
    PersonalityTraitsConfig,
    SimulationPayload,
    DynastySequence,
    LifeCycleModifiers,
)
from .genetics import inherit_traits, roll_birth_traits
from .mortality import annual_death_check, pick_hostile_death


# Built-in relationship types (no upload required). Each maps to the CK3 history
# effect that establishes it. All are reciprocal in-game, so we record one side.
#   soulmate / best_friend  — capped at one per character
#   bully / crush           — childhood (age < 16) precursors of rival/nemesis
#                             and lover/soulmate respectively
RELATIONSHIP_EFFECTS: dict[str, str] = {
    "lover": "set_relation_lover",
    "soulmate": "set_relation_soulmate",
    "rival": "set_relation_rival",
    "nemesis": "set_relation_nemesis",
    "friend": "set_relation_friend",
    "best_friend": "set_relation_best_friend",
    "bully": "set_relation_bully",
    "crush": "set_relation_crush",
}

# Hardcoded secret catalogue (no upload). Each entry declares how it is emitted:
#   target=True  → block form `add_secret = { type = X target = character:Y }`
#   lover=True   → also emits `set_relation_lover = character:Y` in the same block
#   incest=True  → partner is a close blood relative (≤3rd degree); bare add_secret,
#                  optionally accompanied by a lover relation
# Anything with no flags uses the simple bare form `add_secret = secret_X`.
_SECRET_CATALOGUE: dict[str, dict] = {
    "secret_deviant": {},
    "secret_homosexual": {},
    "secret_cannibal": {},
    "secret_non_believer": {},
    "secret_murder_attempt": {"target": True},
    "secret_murder": {"target": True},
    "secret_lover": {"target": True, "lover": True},
    "secret_incest": {"incest": True},
}

_SIMPLE_SECRETS: list[str] = [
    "secret_deviant", "secret_homosexual", "secret_cannibal", "secret_non_believer",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GAP_DYNASTY_ID = "__gap__"


def _is_non_county(title_id: str) -> bool:
    """True for titles that must have an explicit holder=0 when vacant."""
    return title_id[:2] in ("d_", "k_", "e_", "h_")


def _slug(text: str) -> str:
    """Convert a dynasty/house ID to a safe slug for use in character IDs."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "char"


def _lineof_prefix(dynasty: str) -> str:
    """Derive the 'lineof' ID prefix from a dynasty/house ID."""
    if not dynasty:
        return ""
    s = dynasty
    for prefix in ("dynasty_", "house_"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    return s.split("_")[-1]


def _dynasty_culture_faith(dynasty_def: DynastyDefinition, year: int) -> tuple[str, str]:
    """Return (culture, faith) for a dynasty at the given year."""
    if not dynasty_def.culture_faith_periods:
        return "default_culture", "default_faith"
    active = [p for p in dynasty_def.culture_faith_periods if p.start_year <= year]
    if not active:
        return "default_culture", "default_faith"
    period = max(active, key=lambda p: p.start_year)
    return period.culture or "default_culture", period.faith or "default_faith"


def _date(year: int, month: int = 1, day: int = 1) -> str:
    return f"{year}.{month}.{day}"


def _age(character: Character, year: int) -> int:
    return year - int(character.birth_date.split(".")[0])


def _relatives_within_degree(char_id: str, characters: dict, max_degree: int) -> set[str]:
    """BFS on the undirected parent↔child graph; returns all relatives within max_degree steps."""
    visited: set[str] = {char_id}
    frontier: set[str] = {char_id}
    for _ in range(max_degree):
        next_frontier: set[str] = set()
        for cid in frontier:
            c = characters.get(cid)
            if c is None:
                continue
            for pid in (c.father_id, c.mother_id):
                if pid and pid not in visited:
                    next_frontier.add(pid)
            for kid in c.child_ids:
                if kid not in visited:
                    next_frontier.add(kid)
        visited.update(next_frontier)
        frontier = next_frontier
    visited.discard(char_id)
    return visited


def _char_dynasty_id(c: Character) -> str:
    """The effective dynasty/house identifier used to match characters."""
    return c.dynasty_house or c.dynasty


def _pick_name(culture: str, is_female: bool, name_lists: dict, rng: random.Random) -> str:
    key_options = [
        f"{culture}_{'female' if is_female else 'male'}",
        culture,
        "default_female" if is_female else "default_male",
        "default",
    ]
    for k in key_options:
        if k in name_lists and name_lists[k]:
            return rng.choice(name_lists[k])
    return "Unnamed"


_EDUCATION_SKILLS = ["diplomacy", "intrigue", "martial", "stewardship", "learning"]

_EDUCATION_CHILDHOOD_TRAITS: dict[str, list[str]] = {
    "diplomacy":   ["charming", "curious"],
    "intrigue":    ["charming", "rowdy"],
    "martial":     ["rowdy", "bossy"],
    "stewardship": ["pensive", "bossy"],
    "learning":    ["pensive", "curious"],
}


def _get_birth_languages(dynasty_def: Optional[DynastyDefinition], birth_year: int) -> list[str]:
    """Return language IDs whose year range covers birth_year for this dynasty."""
    if not dynasty_def or not dynasty_def.languages:
        return []
    result = []
    for entry in dynasty_def.languages:
        parts = entry.split(",")
        if len(parts) != 3:
            continue
        lang_id = parts[0].strip()
        try:
            start = int(parts[1].strip())
            end = int(parts[2].strip())
        except ValueError:
            continue
        if start <= birth_year <= end:
            result.append(lang_id)
    return result


def _assign_childhood_trait(char: Character, rng: random.Random) -> None:
    """Assign a childhood trait at age 3 from the character's education skill."""
    if not char.education_skill:
        return
    options = _EDUCATION_CHILDHOOD_TRAITS.get(char.education_skill, [])
    if options:
        char.childhood_trait = rng.choice(options)
    char.childhood_trait_assigned = True


def _assign_personality_traits(char: Character, config: PersonalityTraitsConfig, rng: random.Random) -> None:
    """Weighted draw without replacement at age 16, respecting exclusion groups."""
    pool = {name: trait for name, trait in config.traits.items()}
    drawn: list[str] = []

    for _ in range(config.total_traits_per_character):
        if not pool:
            break
        names = list(pool.keys())
        weights = [pool[n].weight for n in names]
        chosen = rng.choices(names, weights=weights)[0]
        drawn.append(chosen)

        # Remove chosen + everything that excludes it or is excluded by it (bidirectional)
        to_remove: set[str] = {chosen}
        to_remove.update(pool[chosen].excludes)
        for name, t in pool.items():
            if chosen in t.excludes:
                to_remove.add(name)
        for r in to_remove:
            pool.pop(r, None)

    char.personality_traits = drawn
    char.personality_assigned = True


# ---------------------------------------------------------------------------
# WorldState
# ---------------------------------------------------------------------------

class WorldState:
    """Holds every character ever created plus the holder timelines for titles."""

    def __init__(self, payload: SimulationPayload, rng: random.Random,
                 logger: Callable[[str], None] = lambda _: None):
        self.payload = payload
        self.rng = rng
        self.log = logger
        self.characters: dict[str, Character] = {}
        # title_id -> list of (date_str, holder_char_id)
        self.title_holders: dict[str, list[tuple[str, str]]] = {}
        # title_id -> currently-active dynasty ID
        self.current_dynasty: dict[str, str] = {}
        # Set of title IDs the user explicitly configured (not cascade-inherited)
        self.explicit_title_ids: set[str] = set()
        # Synthetic placeholder titles created for dynasties with no user-assigned title
        self.placeholder_title_ids: set[str] = set()
        # All unique dynasty/house IDs used in the simulation
        self.dynasty_ids_used: set[str] = set()

        # Parsed registries
        self.traits_registry: list[dict] = []
        self.titles: dict[str, dict] = {}

        # Per-dynasty ID counter for descriptive character IDs
        self._id_counters: dict[str, int] = {}

        self.trait_frequency_multiplier: float = getattr(
            payload.global_settings, "trait_frequency_multiplier", 1.0
        )
        self.personality_traits_config: PersonalityTraitsConfig = (
            payload.global_settings.personality_traits
        )

        # Dynasty definitions lookup keyed by dynasty ID
        self.dynasty_defs: dict[str, DynastyDefinition] = {
            d.id: d for d in (payload.dynasty_definitions or [])
        }

    def _make_char_id(self, dynasty: str) -> str:
        if dynasty:
            prefix = _lineof_prefix(dynasty)
            n = self._id_counters.get(prefix, 0) + 1
            self._id_counters[prefix] = n
            return f"lineof{prefix}{n}"
        else:
            n = self._id_counters.get("bastard", 0) + 1
            self._id_counters["bastard"] = n
            return f"bastard{n}"

    # ------------------------------------------------------------------
    # Name picking (with optional inheritance)
    # ------------------------------------------------------------------

    def _pick_name_with_inheritance(
        self,
        is_female: bool,
        father_id: Optional[str],
        mother_id: Optional[str],
        dynasty_def: Optional[DynastyDefinition],
        culture: str,
    ) -> str:
        """Pick a name using per-dynasty inheritance chances for non-founders."""
        name_lists = self.payload.parsed_files.name_lists
        rng = self.rng

        father = self.characters.get(father_id) if father_id else None
        mother = self.characters.get(mother_id) if mother_id else None

        # Founders and parentless characters → culture pool
        if father is None and mother is None:
            return _pick_name(culture, is_female, name_lists, rng)

        ni = dynasty_def.name_inheritance if dynasty_def else None
        if ni is None:
            return _pick_name(culture, is_female, name_lists, rng)

        outcome = rng.choices(
            ["grandparent", "parent", "none"],
            weights=[ni.grandparent_chance, ni.parent_chance, ni.no_name_chance],
        )[0]

        if outcome == "grandparent":
            if not is_female and father and father.father_id:
                gf = self.characters.get(father.father_id)
                if gf:
                    return gf.name
            elif is_female and mother and mother.mother_id:
                gm = self.characters.get(mother.mother_id)
                if gm:
                    return gm.name
            outcome = "none"  # fallback

        if outcome == "parent":
            if not is_female and father:
                return father.name
            elif is_female and mother:
                return mother.name
            outcome = "none"  # fallback

        # "none" — fresh name from culture pool
        return _pick_name(culture, is_female, name_lists, rng)

    # ------------------------------------------------------------------
    # Elder-of tiebreak for ABSOLUTE_COGNATIC
    # ------------------------------------------------------------------

    def _elder_of(self, a: Character, b: Character) -> Character:
        """Return the 'senior' parent for ABSOLUTE_COGNATIC child-dynasty assignment.

        Simple approximation: the older parent (earlier birth date) is senior.
        """
        return a if a.birth_date <= b.birth_date else b

    # ------------------------------------------------------------------
    # Character creation
    # ------------------------------------------------------------------

    def make_character(
        self,
        *,
        dynasty: str,
        culture: str,
        religion: str,
        is_female: bool,
        birth_year: int,
        father_id: Optional[str] = None,
        mother_id: Optional[str] = None,
        is_bastard: bool = False,
    ) -> Character:
        mult = self.trait_frequency_multiplier
        father = self.characters.get(father_id) if father_id else None
        mother = self.characters.get(mother_id) if mother_id else None

        if father and mother:
            # Each parent contributes at most ONE randomly chosen genetic trait
            # to each child, preventing all traits from spreading simultaneously.
            genetic_ids = {t["id"] for t in self.traits_registry}

            def _one_genetic(char_traits: list[str]) -> list[str]:
                g = [t for t in char_traits if t in genetic_ids]
                return [self.rng.choice(g)] if len(g) > 1 else g

            traits = inherit_traits(
                _one_genetic(mother.traits),
                _one_genetic(father.traits),
                self.traits_registry,
                self.rng,
                mult,
            )
        else:
            traits = roll_birth_traits(self.traits_registry, self.rng, mult)

        # Bastards use their parent's dynasty prefix for the character ID so
        # they follow the same lineof{X}N naming convention as legitimate children.
        id_dynasty = dynasty
        if is_bastard and not dynasty:
            if father:
                id_dynasty = _char_dynasty_id(father)
            elif mother:
                id_dynasty = _char_dynasty_id(mother)

        cid = self._make_char_id(id_dynasty)

        # Dynasty definition lookup for name, languages, etc.
        ddef = self.dynasty_defs.get(dynasty) if dynasty else None

        name = self._pick_name_with_inheritance(
            is_female, father_id, mother_id, ddef, culture
        )

        # Birth languages from dynasty configuration
        birth_languages = _get_birth_languages(ddef, birth_year)

        # Assign education skill randomly
        education_skill = self.rng.choice(_EDUCATION_SKILLS)

        # Determine correct field: house_ prefix → dynasty_house, else → dynasty
        char_dynasty = ""
        char_dynasty_house = ""
        if not dynasty:
            pass  # bastard — both empty
        elif dynasty.startswith("house_"):
            char_dynasty_house = dynasty
        else:
            char_dynasty = dynasty

        char = Character(
            id=cid,
            name=name,
            dynasty=char_dynasty,
            dynasty_house=char_dynasty_house,
            culture=culture,
            religion=religion,
            is_female=is_female,
            father_id=father_id,
            mother_id=mother_id,
            traits=traits,
            birth_date=_date(birth_year, self.rng.randint(1, 12), self.rng.randint(1, 28)),
            is_bastard=is_bastard,
            education_skill=education_skill,
            birth_languages=birth_languages,
        )
        self.characters[cid] = char

        if dynasty:
            self.dynasty_ids_used.add(dynasty)

        if father_id:
            self.characters[father_id].child_ids.append(cid)
        if mother_id:
            self.characters[mother_id].child_ids.append(cid)
        return char

    def kill(self, character: Character, year: int, reason: str, killer_id: Optional[str] = None) -> None:
        if not character.is_alive:
            return
        character.is_alive = False
        character.death_date = _date(year, self.rng.randint(1, 12), self.rng.randint(1, 28))
        character.death_reason = reason
        character.killer_id = killer_id

    # ------------------------------------------------------------------
    # Marriage / fertility helpers
    # ------------------------------------------------------------------

    def marry(self, dynasty_member: Character, spouse: Character, year: int) -> None:
        """Marry two characters, recording the event on the dynasty member."""
        if spouse.id not in dynasty_member.spouse_ids:
            dynasty_member.spouse_ids.append(spouse.id)
        if dynasty_member.id not in spouse.spouse_ids:
            spouse.spouse_ids.append(dynasty_member.id)

        marriage_type = "add_matrilineal_spouse" if dynasty_member.is_female else "add_spouse"
        marriage_date = _date(year, self.rng.randint(1, 12), self.rng.randint(1, 28))
        dynasty_member.marriages.append({
            "date": marriage_date,
            "spouse_id": spouse.id,
            "type": marriage_type,
        })

    def ensure_spouse(
        self,
        ruler: Character,
        year: int,
        modifiers: LifeCycleModifiers,
        spouse_dynasty: Optional[str] = None,
    ) -> Character:
        """Find or create a spouse for ruler, then marry them."""
        if ruler.spouse_ids:
            sp = self.characters.get(ruler.spouse_ids[-1])
            if sp and sp.is_alive:
                return sp

        # Try to find an existing eligible character first
        spouse = self.find_eligible_spouse(ruler, spouse_dynasty, year, modifiers)
        if spouse is None:
            # Create a fresh spouse of appropriate age
            ruler_age = _age(ruler, year)
            spouse_age = max(16, min(ruler_age + self.rng.randint(-5, 5), 40))
            spouse = self.make_character(
                dynasty=spouse_dynasty or ruler.dynasty or ruler.dynasty_house,
                culture=ruler.culture,
                religion=ruler.religion,
                is_female=not ruler.is_female,
                birth_year=year - spouse_age,
            )
        self.marry(ruler, spouse, year)
        return spouse

    def make_lowborn_spouse_and_marry(
        self,
        ruler: Character,
        year: int,
    ) -> Character:
        """Create a fresh lowborn spouse (no dynasty) and marry them to ruler.

        Used for founder/heir/non-heir marriages where the spouse should marry IN
        from outside the dynasty rather than appearing as another dynasty root.
        """
        if ruler.spouse_ids:
            sp = self.characters.get(ruler.spouse_ids[-1])
            if sp and sp.is_alive:
                return sp
        ruler_age = _age(ruler, year)
        spouse_age = max(16, min(ruler_age + self.rng.randint(-5, 5), 40))
        spouse = self.make_character(
            dynasty="",  # lowborn — appears as external ghost via parent-child link, not as dynasty root
            culture=ruler.culture,
            religion=ruler.religion,
            is_female=not ruler.is_female,
            birth_year=year - spouse_age,
        )
        self.marry(ruler, spouse, year)
        return spouse

    def find_eligible_spouse(
        self,
        for_character: Character,
        from_dynasty: Optional[str],
        year: int,
        modifiers: LifeCycleModifiers,
    ) -> Optional[Character]:
        relatives = _relatives_within_degree(for_character.id, self.characters, 3)
        candidates: list[Character] = []
        for c in self.characters.values():
            if not c.is_alive:
                continue
            if c.id == for_character.id:
                continue
            if c.is_female == for_character.is_female:
                continue
            if c.spouse_ids:
                continue
            if c.id in relatives:
                continue
            age = _age(c, year)
            if age < 16 or age > 50:
                continue
            target_age = _age(for_character, year)
            if abs(age - target_age) > modifiers.max_age_difference_between_partners:
                continue
            if from_dynasty and _char_dynasty_id(c) != from_dynasty:
                continue
            candidates.append(c)
        if not candidates:
            return None
        return self.rng.choice(candidates)


# ---------------------------------------------------------------------------
# Title sequence cascade (spec ch. 7)
# ---------------------------------------------------------------------------

def cascade_sequences(
    titles: dict[str, dict],
    user_sequences: dict[str, list[DynastySequence]],
) -> dict[str, list[DynastySequence]]:
    """Propagate parent-tier sequences to children unless overridden."""
    resolved: dict[str, list[DynastySequence]] = {}

    def walk(node: dict, inherited: list[DynastySequence] | None) -> None:
        tid = node.get("id")
        if tid is None:
            for c in node.get("children", {}).values():
                walk(c, inherited)
            return

        if tid in user_sequences:
            current = user_sequences[tid]
        else:
            current = inherited

        if current:
            resolved[tid] = current

        for c in node.get("children", {}).values():
            walk(c, current)

    walk({"id": None, "children": titles}, None)

    # Always include user-explicitly-configured titles, even if they aren't
    # present in the uploaded title hierarchy (e.g., no titles file uploaded).
    for tid, seq_list in user_sequences.items():
        if tid not in resolved and seq_list:
            resolved[tid] = seq_list

    return resolved


# ---------------------------------------------------------------------------
# Main simulation loop
# ---------------------------------------------------------------------------

def run_simulation(
    payload: SimulationPayload,
    traits_registry: list[dict],
    titles: dict[str, dict],
    seed: int = 1337,
    logger: Callable[[str], None] = lambda _: None,
) -> WorldState:
    rng = random.Random(seed)
    world = WorldState(payload, rng, logger)
    world.traits_registry = traits_registry
    world.titles = titles
    world.explicit_title_ids = set(payload.title_sequences.keys())
    world.placeholder_title_ids = set()

    settings = payload.global_settings
    modifiers = payload.life_cycle

    sequences = cascade_sequences(titles, payload.title_sequences)

    title_state: dict[str, dict] = {}
    for tid, seq_list in sequences.items():
        if not seq_list:
            continue
        title_state[tid] = {
            "sequences": list(seq_list),
            "index": 0,
            "started_year": settings.start_year,
            "generations": 0,
            "ruler_id": None,
        }

    # Synthesize placeholder titles for any dynasty defined in the payload but
    # never assigned to a real title. Without this, those dynasties generate no
    # characters at all. The user can copy the placeholder title's history block
    # out of the output and onto a real title manually.
    used_dynasty_ids = {
        seq.dynasty_id
        for seq_list in sequences.values()
        for seq in seq_list
        if seq.dynasty_id and seq.dynasty_id != GAP_DYNASTY_ID
    }
    placeholder_duration = max(1, settings.end_year - settings.start_year + 1)
    for dyn_id in world.dynasty_defs.keys():
        if dyn_id in used_dynasty_ids:
            continue
        placeholder_tid = f"e_placeholder_{dyn_id}"
        title_state[placeholder_tid] = {
            "sequences": [
                DynastySequence(
                    dynasty_id=dyn_id,
                    duration_type="years",
                    duration_value=placeholder_duration,
                    transition_method="extinction",
                )
            ],
            "index": 0,
            "started_year": settings.start_year,
            "generations": 0,
            "ruler_id": None,
        }
        world.explicit_title_ids.add(placeholder_tid)
        world.placeholder_title_ids.add(placeholder_tid)

    if not title_state:
        logger("No title sequences configured and no dynasties defined — nothing to simulate.")
        return world

    # Bootstrap titles. Reuse one founder per dynasty so multiple titles sharing
    # a dynasty don't each create their own unrelated founding character.
    dynasty_founders: dict[str, str] = {}  # dynasty_id -> founder character id
    for tid, st in title_state.items():
        seq = st["sequences"][0]

        # Gap as first sequence: title starts vacant — no founder created.
        if seq.dynasty_id == GAP_DYNASTY_ID:
            st["ruler_id"] = None
            world.current_dynasty[tid] = GAP_DYNASTY_ID
            if _is_non_county(tid):
                world.title_holders.setdefault(tid, []).append(
                    (_date(settings.start_year, 1, 1), "0")
                )
            continue

        existing_founder_id = dynasty_founders.get(seq.dynasty_id)
        if existing_founder_id:
            founder = world.characters[existing_founder_id]
        else:
            ddef = world.dynasty_defs.get(seq.dynasty_id)
            founder_birth = settings.start_year - 35
            if ddef and ddef.start_year:
                founder_birth = ddef.start_year - 35
            culture, religion = ("default_culture", "default_faith")
            if ddef:
                culture, religion = _dynasty_culture_faith(ddef, settings.start_year)
            founder = world.make_character(
                dynasty=seq.dynasty_id,
                culture=culture,
                religion=religion,
                is_female=_ruler_sex_is_female(ddef.gender_law if ddef else None, rng),
                birth_year=founder_birth,
            )
            # Spouse is lowborn so they don't appear as a second dynasty root
            world.make_lowborn_spouse_and_marry(founder, settings.start_year)
            dynasty_founders[seq.dynasty_id] = founder.id

        st["ruler_id"] = founder.id
        world.title_holders.setdefault(tid, []).append(
            (_date(settings.start_year, 1, 1), founder.id)
        )
        world.current_dynasty[tid] = seq.dynasty_id

    # ------------------------------------------------------------------
    # Year-by-year tick
    # ------------------------------------------------------------------
    global_generations = 0
    for year in range(settings.start_year, settings.end_year + 1):
        if global_generations >= settings.maximum_generations:
            logger(f"Reached maximum_generations limit ({settings.maximum_generations}) at year {year}, stopping.")
            break
        if year % 50 == 0:
            logger(f"Simulating year {year}...")

        # 1. Mortality
        for char in list(world.characters.values()):
            if not char.is_alive:
                continue
            reason = annual_death_check(char, year, rng, modifiers.average_lifespan)
            if reason:
                world.kill(char, year, reason)

        # Per-year cache: living member count per house (key = dynasty_house or dynasty).
        # Used to damp fertility + marriage as a dynasty approaches its soft cap.
        dynasty_sizes: dict[str, int] = {}
        for c in world.characters.values():
            if c.is_alive:
                d = _char_dynasty_id(c)
                if d:
                    dynasty_sizes[d] = dynasty_sizes.get(d, 0) + 1
        soft_cap = max(1, modifiers.dynasty_soft_cap)

        def _size_factor(dynasty_id: str) -> float:
            size = dynasty_sizes.get(dynasty_id, 0)
            if size <= 0:
                return 1.0
            return max(0.05, 1.0 - (size / soft_cap) ** 2)

        # Multi-source BFS from current rulers → kinship distance per character.
        # Used to suppress fertility for distant relatives of the active ruling line.
        # Distance counts steps along parent↔child edges:
        #   0=ruler, 1=parent/child, 2=grandparent/grandchild/sibling,
        #   3=aunt/uncle/nephew/niece, 4=first cousin, 6=second cousin, 8=third cousin
        ruler_distances: dict[str, int] = {}
        for st in title_state.values():
            rid = st.get("ruler_id")
            if rid and rid in world.characters and world.characters[rid].is_alive:
                ruler_distances[rid] = 0
        bfs_frontier = list(ruler_distances.keys())
        while bfs_frontier:
            next_frontier: list[str] = []
            for cid in bfs_frontier:
                d = ruler_distances[cid]
                c = world.characters.get(cid)
                if c is None:
                    continue
                neighbors = list(c.child_ids)
                if c.father_id:
                    neighbors.append(c.father_id)
                if c.mother_id:
                    neighbors.append(c.mother_id)
                for nid in neighbors:
                    if nid and nid not in ruler_distances:
                        ruler_distances[nid] = d + 1
                        next_frontier.append(nid)
            bfs_frontier = next_frontier

        def _kinship_factor(*char_ids: str) -> float:
            """Falloff by minimum kinship distance to any current ruler.
            Tightened so dynasties grow tall (more generations) rather than wide."""
            d = min((ruler_distances.get(cid, 99) for cid in char_ids), default=99)
            if d <= 1:
                return 1.0   # ruler, parent, child of ruler — heir line
            if d == 2:
                return 0.45  # siblings, grandchildren — secondary branches
            if d == 3:
                return 0.15  # aunts/uncles, nephews/nieces
            if d == 4:
                return 0.03  # first cousins — rare children
            return 0.0       # cousins once removed and beyond — no children

        # 2. Age-milestone events (childhood traits at 3, personality traits at 16)
        for char in list(world.characters.values()):
            if not char.is_alive:
                continue
            age = _age(char, year)
            if age >= 3 and not char.childhood_trait_assigned:
                _assign_childhood_trait(char, rng)
            if age >= 16 and not char.personality_assigned:
                birth_parts = char.birth_date.split(".")
                char.personality_trait_date = _date(
                    int(birth_parts[0]) + 16, int(birth_parts[1]), int(birth_parts[2])
                )
                _assign_personality_traits(char, world.personality_traits_config, rng)

        # 3. Fertility — generate children for living married couples
        for char in list(world.characters.values()):
            if not char.is_alive or char.is_female:
                continue
            if not char.spouse_ids:
                continue
            spouse = world.characters.get(char.spouse_ids[-1])
            if not spouse or not spouse.is_alive:
                continue

            dad_age = _age(char, year)
            if 16 <= dad_age <= 70 and rng.random() < modifiers.male_bastard_chance:
                world.make_character(
                    dynasty="",
                    culture=char.culture,
                    religion=char.religion,
                    is_female=rng.random() < 0.5,
                    birth_year=year,
                    father_id=char.id,
                    is_bastard=True,
                )
            spouse_age = _age(spouse, year)
            if 16 <= spouse_age <= 45 and rng.random() < modifiers.female_bastard_chance:
                world.make_character(
                    dynasty="",
                    culture=char.culture,
                    religion=char.religion,
                    is_female=rng.random() < 0.5,
                    birth_year=year,
                    mother_id=spouse.id,
                    is_bastard=True,
                )

            if spouse_age < 16 or spouse_age > 45:
                continue
            legitimate_children = sum(
                1 for cid in char.child_ids
                if cid in world.characters and not world.characters[cid].is_bastard
            )
            if legitimate_children >= modifiers.max_children_per_couple:
                continue

            fertility = modifiers.base_fertility_rate * char.fertility_multiplier * spouse.fertility_multiplier
            child_house_hint = _char_dynasty_id(char) or _char_dynasty_id(spouse)
            if child_house_hint:
                fertility *= _size_factor(child_house_hint)
            fertility *= _kinship_factor(char.id, spouse.id)
            if rng.random() < fertility:
                # Determine child's dynasty
                ddef_char = world.dynasty_defs.get(_char_dynasty_id(char))
                house = _char_dynasty_id(char)
                if spouse.force_child_house:
                    house = spouse.force_child_house
                elif char.force_child_house:
                    house = char.force_child_house
                elif ddef_char and ddef_char.gender_law == "ABSOLUTE_COGNATIC":
                    # Senior parent's dynasty for the child
                    senior = world._elder_of(char, spouse)
                    house = _char_dynasty_id(senior)

                # Matrilineal fallback: father is lowborn but mother is in a dynasty
                if not house:
                    house = _char_dynasty_id(spouse)

                # Apply birth sex bias based on gender law
                child_is_female = _biased_sex(world, char, ddef_char, year, rng)

                world.make_character(
                    dynasty=house,
                    culture=char.culture,
                    religion=char.religion,
                    is_female=child_is_female,
                    birth_year=year,
                    father_id=char.id,
                    mother_id=spouse.id,
                )

        # 3.5. Marriage — pair up unmarried adult dynasty members with lowborn spouses
        for char in list(world.characters.values()):
            if not char.is_alive:
                continue
            if char.spouse_ids:
                continue
            if char.is_bastard:
                continue
            if not _char_dynasty_id(char):
                continue  # skip lowborn — they don't actively seek marriage
            age = _age(char, year)
            if age < 16 or age > 40:
                continue
            marriage_chance = 0.10 * _size_factor(_char_dynasty_id(char)) * _kinship_factor(char.id)
            if rng.random() < marriage_chance:
                world.make_lowborn_spouse_and_marry(char, year)

        # 4. Succession + transition events for each title
        for tid, st in title_state.items():
            seq = st["sequences"][st["index"]]
            ruler = world.characters.get(st["ruler_id"]) if st["ruler_id"] else None

            expired = False
            if seq.duration_type == "years":
                expired = (year - st["started_year"]) >= seq.duration_value
            else:
                expired = st["generations"] >= seq.duration_value

            # --- Gap sequence: title is vacant; just check for expiry ---
            if seq.dynasty_id == GAP_DYNASTY_ID:
                if expired and st["index"] + 1 < len(st["sequences"]):
                    next_seq = st["sequences"][st["index"] + 1]
                    if next_seq.dynasty_id != GAP_DYNASTY_ID:
                        # Gap → real dynasty: fabricate a new founder
                        ddef = world.dynasty_defs.get(next_seq.dynasty_id)
                        nc, nr = _dynasty_culture_faith(ddef, year) if ddef else ("default_culture", "default_faith")
                        new_ruler = world.make_character(
                            dynasty=next_seq.dynasty_id,
                            culture=nc,
                            religion=nr,
                            is_female=_ruler_sex_is_female(ddef.gender_law if ddef else None, rng),
                            birth_year=year - 30,
                        )
                        world.make_lowborn_spouse_and_marry(new_ruler, year)
                        world.title_holders.setdefault(tid, []).append(
                            (_date(year, 1, 1), new_ruler.id)
                        )
                        st["ruler_id"] = new_ruler.id
                    else:
                        # Gap → gap: remain vacant
                        if _is_non_county(tid):
                            world.title_holders.setdefault(tid, []).append(
                                (_date(year, 1, 1), "0")
                            )
                        st["ruler_id"] = None
                    st["index"] += 1
                    st["started_year"] = year
                    st["generations"] = 0
                    world.current_dynasty[tid] = next_seq.dynasty_id
                continue  # no succession logic during a gap

            # --- Normal sequence ---
            if ruler is None:
                continue

            if not ruler.is_alive:
                ddef = world.dynasty_defs.get(seq.dynasty_id)
                heir = _find_heir(world, ruler, ddef)
                if heir is None:
                    guaranteed = ddef is None or ddef.guaranteed_survival
                    if not guaranteed:
                        expired = True
                    else:
                        heir = _fabricate_continuation_heir(world, ruler, ddef, year)

                if heir is not None:
                    world.make_lowborn_spouse_and_marry(heir, year)
                    st["ruler_id"] = heir.id
                    st["generations"] += 1
                    global_generations += 1
                    world.title_holders[tid].append(
                        (ruler.death_date, heir.id)
                    )
                    ruler = heir

            if expired and st["index"] + 1 < len(st["sequences"]):
                next_seq = st["sequences"][st["index"] + 1]
                if next_seq.dynasty_id == GAP_DYNASTY_ID:
                    # Transition into a gap: write holder=0 for non-county titles
                    if _is_non_county(tid):
                        gap_date = _date(year, 1, 1)
                        if not ruler.is_alive and ruler.death_date:
                            gap_date = ruler.death_date
                        world.title_holders.setdefault(tid, []).append(
                            (gap_date, "0")
                        )
                    st["ruler_id"] = None
                else:
                    _execute_transition(
                        world, tid, ruler, seq, next_seq, year, modifiers,
                    )
                    st["ruler_id"] = world.title_holders[tid][-1][1]
                st["index"] += 1
                st["started_year"] = year
                st["generations"] = 0
                world.current_dynasty[tid] = next_seq.dynasty_id

    # All characters who survived to end_year must receive a death date.
    # Without this they would appear immortal when the game loads — hundreds
    # of years old at the CK3 start date.
    _kill_survivors(world, settings.end_year, modifiers.average_lifespan)

    # Optional post-passes. Both pick dates inside a character's lifespan, so they
    # run after _kill_survivors has stamped every character with a death date.
    if settings.enable_relationships:
        _generate_relationships(world)
    if settings.enable_secrets:
        _generate_secrets(world)

    return world


# ---------------------------------------------------------------------------
# Post-simulation survivor cleanup
# ---------------------------------------------------------------------------

def _kill_survivors(world: WorldState, end_year: int, avg_lifespan: float = 70.0) -> None:
    """Simulate natural deaths for every character still alive at end_year.

    Continues the annual mortality tick until all characters have died or the
    hard cap (end_year + 200) is reached. Remaining immortals are force-killed
    at the cap with death_natural_causes.
    """
    hard_cap = end_year + 200
    for year in range(end_year + 1, hard_cap + 1):
        alive = [c for c in world.characters.values() if c.is_alive]
        if not alive:
            break
        for char in alive:
            reason = annual_death_check(char, year, world.rng, avg_lifespan)
            if reason:
                world.kill(char, year, reason)
    # Hard cap: force-kill anyone who survived 200 extra years
    for char in world.characters.values():
        if char.is_alive:
            world.kill(char, hard_cap, "death_natural_causes")


# ---------------------------------------------------------------------------
# Relationship + secret generation (optional post-passes)
# ---------------------------------------------------------------------------

def _life_years(c: Character) -> tuple[int, int]:
    """Return (birth_year, death_year) for a character; defaults if unparseable."""
    try:
        b = int(c.birth_date.split(".")[0])
    except (AttributeError, ValueError):
        b = 0
    try:
        d = int(c.death_date.split(".")[0]) if c.death_date else b + 80
    except (AttributeError, ValueError):
        d = b + 80
    return b, d


def _lifespans_overlap(c: Character, o: Character) -> bool:
    cb, cd = _life_years(c)
    ob, od = _life_years(o)
    return max(cb, ob) <= min(cd, od)


def _pick_contemporary(c: Character, pool: list, rng: random.Random) -> Optional[Character]:
    """Return a random character from pool whose lifespan overlaps c's (not c)."""
    cands = [o for o in pool if o.id != c.id and _lifespans_overlap(c, o)]
    return rng.choice(cands) if cands else None


def _generate_relationships(world: WorldState) -> None:
    """Assign built-in relationships between contemporaries.

    Each unordered pair is considered once (from the smaller character ID). A pair
    that shared childhood (both < 16) may form a bully/crush, which then biases the
    adult relationship toward rival/nemesis (bully) or lover/soulmate (crush). The
    soulmate and best_friend upgrades are capped at one per character.
    """
    rng = world.rng
    chars = list(world.characters.values())
    soulmate_used: set[str] = set()
    best_friend_used: set[str] = set()

    def _rand_date(lo: int, hi: int) -> str:
        return _date(rng.randint(lo, hi), rng.randint(1, 12), rng.randint(1, 28))

    for c in chars:
        if rng.random() > 0.25:  # ~25% of characters initiate a relationship arc
            continue
        cb, cd = _life_years(c)
        candidates = [o for o in chars if o.id > c.id and _lifespans_overlap(c, o)]
        if not candidates:
            continue
        o = rng.choice(candidates)
        ob, od = _life_years(o)

        # Childhood window: both alive and under 16.
        ch_lo, ch_hi = max(cb, ob), min(cb + 15, ob + 15, cd, od)
        had_bully = had_crush = False
        if ch_lo <= ch_hi and rng.random() < 0.5:
            kind = rng.choice(["bully", "crush"])
            had_bully, had_crush = kind == "bully", kind == "crush"
            c.relationships.append({
                "date": _rand_date(ch_lo, ch_hi),
                "effect": RELATIONSHIP_EFFECTS[kind],
                "target_id": o.id,
            })

        # Adult window: both alive and 16+.
        ad_lo, ad_hi = max(cb + 16, ob + 16), min(cd, od)
        if ad_lo <= ad_hi:
            if had_bully:
                base = "rival"
            elif had_crush:
                base = "lover"
            else:
                base = rng.choice(["friend", "rival", "lover"])
            key = base
            if base == "rival" and rng.random() < 0.30:
                key = "nemesis"
            elif (base == "friend" and rng.random() < 0.30
                  and c.id not in best_friend_used and o.id not in best_friend_used):
                key = "best_friend"
                best_friend_used.update({c.id, o.id})
            elif (base == "lover" and rng.random() < 0.30
                  and c.id not in soulmate_used and o.id not in soulmate_used):
                key = "soulmate"
                soulmate_used.update({c.id, o.id})
            c.relationships.append({
                "date": _rand_date(ad_lo, ad_hi),
                "effect": RELATIONSHIP_EFFECTS[key],
                "target_id": o.id,
            })


def _generate_secrets(world: WorldState) -> None:
    """Assign hardcoded secrets to a fraction of characters (no upload needed).

    Target/lover secrets resolve a contemporary; incest secrets resolve a close
    blood relative (≤3rd degree). A partner-requiring secret with no eligible
    partner downgrades to a simple secret. The output formatter decides between
    the bare `add_secret = X` form and the block `add_secret = { type target }`
    form (see output.py).
    """
    rng = world.rng
    chars = list(world.characters.values())
    catalogue = list(_SECRET_CATALOGUE.keys())
    for c in chars:
        if rng.random() > 0.15:  # ~15% of characters hold a secret
            continue
        stype = rng.choice(catalogue)
        meta = _SECRET_CATALOGUE[stype]
        cb, cd = _life_years(c)

        partner: Optional[Character] = None
        if meta.get("incest"):
            pool = [world.characters[r] for r in _relatives_within_degree(c.id, world.characters, 3)
                    if r in world.characters]
            partner = _pick_contemporary(c, pool, rng)
        elif meta.get("target") or meta.get("lover"):
            partner = _pick_contemporary(c, chars, rng)

        # Partner-requiring secret with no eligible partner → downgrade to simple.
        if partner is None and meta:
            stype, meta = rng.choice(_SIMPLE_SECRETS), {}

        # Date window: overlap with partner if any, else c's own adulthood.
        if partner is not None:
            pb, pd = _life_years(partner)
            lo, hi = max(cb, pb), min(cd, pd)
        else:
            lo, hi = (cb + 16, cd) if cb + 16 <= cd else (cb, cd)
        if lo > hi:
            continue

        entry = {
            "date": _date(rng.randint(lo, hi), rng.randint(1, 12), rng.randint(1, 28)),
            "type": stype,
        }
        if partner is not None:
            entry["target_id"] = partner.id
            if meta.get("lover") or (meta.get("incest") and rng.random() < 0.5):
                entry["with_lover"] = True
        c.secrets.append(entry)


# ---------------------------------------------------------------------------
# Birth sex bias helper
# ---------------------------------------------------------------------------

def _biased_sex(
    world: WorldState,
    father: Character,
    ddef: Optional[DynastyDefinition],
    year: int,
    rng: random.Random,
) -> bool:
    """Return True (female) or False (male) with gender-law-appropriate bias."""
    gl = ddef.gender_law if ddef else "AGNATIC_COGNATIC"

    if gl in ("AGNATIC", "AGNATIC_COGNATIC"):
        # 90% male if no living male child heir exists yet
        has_male_heir = any(
            world.characters[cid].is_alive
            and not world.characters[cid].is_female
            and not world.characters[cid].is_bastard
            for cid in father.child_ids
            if cid in world.characters
        )
        if not has_male_heir:
            return rng.random() < 0.10  # 10% female = 90% male
    elif gl in ("ENATIC", "ENATIC_COGNATIC"):
        # 90% female if no living female child heir exists yet
        has_female_heir = any(
            world.characters[cid].is_alive
            and world.characters[cid].is_female
            and not world.characters[cid].is_bastard
            for cid in father.child_ids
            if cid in world.characters
        )
        if not has_female_heir:
            return rng.random() < 0.90  # 90% female

    # ABSOLUTE_COGNATIC or bias doesn't apply: 50/50
    return rng.random() < 0.5


# ---------------------------------------------------------------------------
# Heir / transition helpers
# ---------------------------------------------------------------------------

def _fabricate_continuation_heir(
    world: WorldState,
    ruler: Character,
    dynasty_def: Optional[DynastyDefinition],
    year: int,
) -> Character:
    """Create a continuation heir for a guaranteed-survival dynasty whose ruling
    line has no eligible successor.

    The heir is grafted onto the existing lineage (as a previously-unmentioned
    child of the late ruler, or of the ruler's parent if the ruler was too young)
    rather than spawned parentless — so the dynasty keeps a single founding root
    in the family tree instead of sprouting multiple unrelated starting characters.
    """
    culture, religion = (ruler.culture, ruler.religion)
    if dynasty_def:
        culture, religion = _dynasty_culture_faith(dynasty_def, year)
    heir_is_female = _ruler_sex_is_female(dynasty_def.gender_law if dynasty_def else None, world.rng)

    def _yr(date_str: Optional[str], fallback: int) -> int:
        try:
            return int(date_str.split(".")[0])
        except (AttributeError, ValueError, IndexError):
            return fallback

    # Anchor candidates: the late ruler first, then their parent.
    candidates = [ruler]
    pid = ruler.father_id or ruler.mother_id
    if pid and pid in world.characters:
        candidates.append(world.characters[pid])

    for anchor in candidates:
        a_birth = _yr(anchor.birth_date, year - 60)
        a_death = _yr(anchor.death_date, year) if anchor.death_date else year
        earliest = a_birth + 18           # parent must have been an adult at the birth
        latest = min(year - 18, a_death)  # heir must be an adult now, born before parent died
        if earliest <= latest:
            heir_birth = max(min(year - 25, latest), earliest)
            parent_kwargs = {"mother_id": anchor.id} if anchor.is_female else {"father_id": anchor.id}
            heir = world.make_character(
                dynasty=_char_dynasty_id(ruler),
                culture=culture,
                religion=religion,
                is_female=heir_is_female,
                birth_year=heir_birth,
                **parent_kwargs,
            )
            # Modelled as an adoption: the anchor has no recorded partner producing
            # this heir, so output emits an `adopt` effect rather than a biological birth.
            heir.is_adopted = True
            return heir

    # Last resort (rare): no viable anchor — accept a parentless heir.
    return world.make_character(
        dynasty=_char_dynasty_id(ruler),
        culture=culture,
        religion=religion,
        is_female=heir_is_female,
        birth_year=year - 30,
    )


def _birth_key(c: Character) -> tuple:
    """Parse 'YYYY.M.D' into a comparable tuple so birth dates sort by real
    chronology (a plain string sort mis-orders months/days within a year)."""
    try:
        return tuple(int(p) for p in c.birth_date.split("."))
    except (AttributeError, ValueError):
        return (9999,)


def _find_heir(
    world: WorldState,
    ruler: Character,
    dynasty_def: Optional[DynastyDefinition] = None,
) -> Optional[Character]:
    """Return the eligible heir per gender_law and succession type of the dynasty."""
    ruler_dynasty = _char_dynasty_id(ruler)
    death_year = int(ruler.death_date.split(".")[0]) if ruler.death_date else 9999
    gl = dynasty_def.gender_law if dynasty_def else "AGNATIC_COGNATIC"
    succ = dynasty_def.succession if dynasty_def else "PRIMOGENITURE"

    def _eligible(c: Character, allow_bastard: bool = False) -> bool:
        return (
            c.is_alive
            and (allow_bastard or not c.is_bastard)
            and _char_dynasty_id(c) == ruler_dynasty
            and _age(c, death_year) >= 16
        )

    # --- SENIORITY: oldest living dynasty member ---
    if succ == "SENIORITY":
        for allow_bastard in (False, True):
            pool = [c for c in world.characters.values() if _eligible(c, allow_bastard)]
            pool = _filter_by_gender(pool, gl)
            if pool:
                pool.sort(key=_birth_key)
                return pool[0]
        return None

    # --- PRIMOGENITURE / ULTIMOGENITURE: depth-first child search ---
    reverse = (succ == "ULTIMOGENITURE")

    def _search(char_id: str, allow_bastard: bool, female_only: Optional[bool],
                skip_id: Optional[str] = None) -> Optional[Character]:
        char = world.characters.get(char_id)
        if char is None:
            return None
        children = [
            world.characters[cid]
            for cid in char.child_ids
            if cid in world.characters
            and _char_dynasty_id(world.characters[cid]) == ruler_dynasty
            and (allow_bastard or not world.characters[cid].is_bastard)
        ]
        # female_only filters at EVERY level, so the search only ever traverses the
        # included-gender line (e.g. ENATIC never passes through a son to his daughter).
        if female_only is True:
            children = [c for c in children if c.is_female]
        elif female_only is False:
            children = [c for c in children if not c.is_female]
        children.sort(key=_birth_key, reverse=reverse)

        for child in children:
            if skip_id and child.id == skip_id:
                continue  # branch already covered when climbing up from it
            if _eligible(child, allow_bastard):
                return child
            found = _search(child.id, allow_bastard, female_only)
            if found:
                return found
        return None

    # Map gender law to search passes
    passes: list[Optional[bool]]
    if gl == "AGNATIC":
        passes = [False]         # males only — never females
    elif gl == "AGNATIC_COGNATIC":
        passes = [False, True]   # males first, then females
    elif gl == "ABSOLUTE_COGNATIC":
        passes = [None]          # both together (unsorted by sex)
    elif gl == "ENATIC_COGNATIC":
        passes = [True, False]   # females first, then males
    else:  # ENATIC
        passes = [True]          # females only — never males

    # Build the ancestor chain through the dynasty line (mother for matrilineal/ENATIC
    # dynasties, father for AGNATIC) so collateral relatives can inherit when the
    # ruler's own descendants yield no heir: own line → siblings/nieces → aunts/cousins.
    def _dynasty_parent(c: Character) -> Optional[Character]:
        for pid in (c.father_id, c.mother_id):
            p = world.characters.get(pid) if pid else None
            if p and _char_dynasty_id(p) == ruler_dynasty:
                return p
        return None

    chain: list[tuple[Character, Optional[str]]] = []  # (ancestor, child-branch-to-skip)
    node: Optional[Character] = ruler
    skip: Optional[str] = None
    seen: set[str] = set()
    while node is not None and node.id not in seen:
        seen.add(node.id)
        chain.append((node, skip))
        skip = node.id
        node = _dynasty_parent(node)

    for allow_bastard in (False, True):
        for female_only in passes:
            for ancestor, skip_child in chain:
                result = _search(ancestor.id, allow_bastard, female_only, skip_child)
                if result:
                    return result

    return None


def _ruler_sex_is_female(gl: Optional[str], rng: random.Random) -> bool:
    """Sex a fabricated ruler/founder must have to satisfy a dynasty's gender law.
    AGNATIC* → male, ENATIC* → female, ABSOLUTE_COGNATIC / unset → either."""
    if gl in ("ENATIC", "ENATIC_COGNATIC"):
        return True
    if gl in ("AGNATIC", "AGNATIC_COGNATIC"):
        return False
    return rng.random() < 0.5


def _filter_by_gender(pool: list[Character], gl: str) -> list[Character]:
    """Filter a flat pool of characters by gender law for SENIORITY searches."""
    males = [c for c in pool if not c.is_female]
    females = [c for c in pool if c.is_female]
    if gl == "AGNATIC":
        return males
    elif gl == "AGNATIC_COGNATIC":
        return males if males else females
    elif gl == "ABSOLUTE_COGNATIC":
        return pool
    elif gl == "ENATIC_COGNATIC":
        return females if females else males
    else:  # ENATIC
        return females


def _execute_transition(
    world: WorldState,
    title_id: str,
    current_ruler: Character,
    current_seq: DynastySequence,
    next_seq: DynastySequence,
    year: int,
    modifiers: LifeCycleModifiers,
) -> None:
    method = current_seq.transition_method
    if method == "marriage":
        _transition_marriage(world, title_id, current_ruler, next_seq, year, modifiers)
    elif method == "usurpation":
        _transition_usurpation(world, title_id, current_ruler, next_seq, year)
    else:  # extinction
        _transition_extinction(world, title_id, current_ruler, next_seq, year)


def _transition_marriage(
    world: WorldState,
    title_id: str,
    ruler: Character,
    next_seq: DynastySequence,
    year: int,
    modifiers: LifeCycleModifiers,
) -> None:
    heir = _find_heir(world, ruler)
    if heir is None:
        rddef = world.dynasty_defs.get(_char_dynasty_id(ruler))
        parent_kw = {"mother_id": ruler.id} if ruler.is_female else {"father_id": ruler.id}
        heir = world.make_character(
            dynasty=_char_dynasty_id(ruler),
            culture=ruler.culture,
            religion=ruler.religion,
            is_female=_ruler_sex_is_female(rddef.gender_law if rddef else None, world.rng),
            birth_year=year - 25,
            **parent_kw,
        )

    # Find or create a partner from House B
    partner = world.find_eligible_spouse(heir, next_seq.dynasty_id, year, modifiers)
    if partner is None:
        partner = world.make_character(
            dynasty=next_seq.dynasty_id,
            culture=ruler.culture,
            religion=ruler.religion,
            is_female=not heir.is_female,
            birth_year=year - 22,
        )

    world.marry(heir, partner, year)
    heir.force_child_house = next_seq.dynasty_id
    partner.force_child_house = next_seq.dynasty_id

    world.title_holders[title_id].append((f"{year}.6.15", heir.id))


def _transition_usurpation(
    world: WorldState,
    title_id: str,
    ruler: Character,
    next_seq: DynastySequence,
    year: int,
) -> None:
    nddef = world.dynasty_defs.get(next_seq.dynasty_id)
    antagonist = world.make_character(
        dynasty=next_seq.dynasty_id,
        culture=ruler.culture,
        religion=ruler.religion,
        is_female=_ruler_sex_is_female(nddef.gender_law if nddef else None, world.rng),
        birth_year=year - 35,
    )
    reason = pick_hostile_death(world.rng)
    world.kill(ruler, year, reason, killer_id=antagonist.id)

    family = [
        world.characters[cid]
        for cid in (ruler.child_ids + ruler.spouse_ids)
        if cid in world.characters and world.characters[cid].is_alive
    ]
    friendly_ruler = _find_friendly_ruler(world, ruler, antagonist.id)
    for member in family:
        if friendly_ruler:
            member.employer_id = friendly_ruler.id
            member.employer_date = f"{year}.6.15"

    world.title_holders[title_id].append((f"{year}.6.15", antagonist.id))


def _transition_extinction(
    world: WorldState,
    title_id: str,
    ruler: Character,
    next_seq: DynastySequence,
    year: int,
) -> None:
    ruler.fertility_multiplier = 0.0
    for cid in ruler.child_ids:
        if cid in world.characters:
            world.characters[cid].fertility_multiplier = 0.0

    nddef = world.dynasty_defs.get(next_seq.dynasty_id)
    incoming = world.make_character(
        dynasty=next_seq.dynasty_id,
        culture=ruler.culture,
        religion=ruler.religion,
        is_female=_ruler_sex_is_female(nddef.gender_law if nddef else None, world.rng),
        birth_year=year - 35,
    )
    transfer_year = year
    if ruler.death_date:
        transfer_year = int(ruler.death_date.split(".")[0])
    world.title_holders[title_id].append((f"{transfer_year}.6.15", incoming.id))


def _find_friendly_ruler(
    world: WorldState,
    displaced: Character,
    exclude_id: str,
) -> Optional[Character]:
    for tid, holders in world.title_holders.items():
        if not holders:
            continue
        latest_id = holders[-1][1]
        if latest_id == exclude_id:
            continue
        candidate = world.characters.get(latest_id)
        if not candidate or not candidate.is_alive:
            continue
        if (candidate.culture == displaced.culture
                or candidate.religion == displaced.religion):
            return candidate
    return None
