# CK3 Character History Generator — Configuration Guide

This document is the authoritative reference for every configuration option that
drives the simulation. It is structured around the four topics most critical to
producing historically believable, CK3-compatible output:

1. [Succession System (Gender Law × Succession Type)](#1-succession-system)
2. [Personality Traits](#2-personality-traits)
3. [Name Inheritance Chances](#3-name-inheritance-chances)
4. [Languages](#4-languages)

All values live in `config/initialization.json` or `config/skills_and_traits.json`
and can be edited directly or through the GUI's settings tabs.

---

## 1. Succession System

Every dynasty requires two interlocking fields that together answer the question
**"who inherits next?"** — both for the CK3 title history file and for the
simulation's marriage and child-dynasty logic.

```json
"succession": "PRIMOGENITURE",
"gender_law": "AGNATIC_COGNATIC"
```

These two fields are independent axes. Gender law filters **who is eligible** to
inherit; succession type determines **which eligible person comes first**.

---

### 1.1 Gender Law

The gender law governs three distinct things inside the generator:

| Effect | Where it matters |
|---|---|
| Who may inherit a title | `title_history.py` — heir determination |
| How marriages are recorded in the CK3 file | `simulation.py` → `marry_characters()` |
| Which parent's dynasty a child belongs to | `simulation.py` → `create_child()` |
| Which sex the simulation biases births toward | `simulation.py` → `create_child()` |
| What counts as "dynasty can still continue" | `simulation.py` → `_dynasty_can_continue()` |

#### `AGNATIC`
Only males may hold and transmit the title. Females are completely excluded from
the succession line.

- **CK3 marriage type written:** `add_spouse` (male dynastics marry in a woman)
- **Child dynasty:** always taken from the father
- **Birth bias:** if no male heir exists yet, first child has a **90% chance of
  being male**
- **Dynasty continuation check:** passes only when a living male aged 16–80 can
  still produce children
- **Title history heir search:** only males are considered at every step of the
  search tree

#### `AGNATIC_COGNATIC`
Males inherit first; females are a fallback when no living eligible male exists.
This is the standard medieval European model.

- **CK3 marriage type:** `add_spouse` (male members of the dynasty marry in)
- **Child dynasty:** always taken from the father
- **Birth bias:** same 90% male bias when no male heir exists
- **Dynasty continuation:** passes when any living male aged 16–80 can produce
  children (females are not counted for continuation)
- **Title history heir search:** the search builds two ordered lists — all
  eligible males sorted by succession order, then all eligible females. Males are
  exhausted first before any female is tried

#### `ABSOLUTE_COGNATIC`
All children are equally eligible regardless of sex. Birth order (or age, for
seniority) is the only deciding factor.

- **CK3 marriage type:** `add_spouse` if the marrying dynasty member is male;
  `add_matrilineal_spouse` if female — the `elder_of()` tiebreak decides whose
  dynasty the children join
- **Child dynasty:** decided by `elder_of()` — the parent whose lineage is the
  "senior" line (earlier birth order within their own parent's children, then
  recursively up the tree)
- **Birth bias:** 50/50 male/female
- **Dynasty continuation:** passes when *any* living member (male or female) in
  the appropriate age window can produce children
- **Title history heir search:** all eligible children sorted together by birth
  date with no sex partitioning

#### `ENATIC_COGNATIC`
Females inherit first; males are a fallback. The mirror image of
`AGNATIC_COGNATIC`.

- **CK3 marriage type:** `add_matrilineal_spouse` (female members of the dynasty
  marry men in)
- **Child dynasty:** always taken from the mother
- **Birth bias:** if no female heir exists yet, first child has a **10% chance of
  being male** (i.e. 90% female)
- **Dynasty continuation:** passes when a living female aged 16–50 can produce
  children
- **Title history heir search:** all eligible females sorted first, then all
  eligible males

#### `ENATIC`
Only females may hold and transmit the title. The strict mirror of `AGNATIC`.

- **CK3 marriage type:** `add_matrilineal_spouse`
- **Child dynasty:** always taken from the mother
- **Birth bias:** 90% female when no female heir exists
- **Dynasty continuation:** passes only when a living female aged 16–50 can
  produce children
- **Title history heir search:** only females are considered

---

### 1.2 Succession Type

Once the eligible pool has been filtered by gender law, the succession type
controls **ordering within that pool**.

#### `PRIMOGENITURE`
The eldest eligible child inherits. If that child predeceased the ruler, the
search recurses into *that child's* own eldest eligible descendant before moving
on to the next sibling. This creates the familiar "eldest line first" depth-first
traversal.

- **Heir search order:** children sorted ascending by birth date (oldest first)
- **Fallback:** if no eligible child exists, the search climbs to the relevant
  parent (father for agnatic laws, mother for enatic) and recurses there
- **Bastard fallback:** if no legitimate heir is found, the entire search reruns
  with bastards included

#### `ULTIMOGENITURE`
The youngest eligible child inherits. Identical logic to primogeniture except
children are sorted **descending** by birth date (youngest first).

- **Heir search order:** children sorted descending by birth date (youngest first)
- All other fallback rules are identical to primogeniture

#### `SENIORITY`
The oldest living eligible member of the **entire dynasty** inherits, regardless
of their relationship to the current ruler.

- **Heir pool:** all living members of the dynasty sorted ascending by birth date
- **Eligibility:** the candidate must have been born on or before the ruler's
  death date and must be alive at that date
- **No depth-first recursion:** unlike primogeniture, seniority does not recurse
  into dead candidates' descendants
- **Bastard fallback:** if no legitimate candidate is alive, the pool is retried
  with bastards included

---

### 1.3 Interaction Table

The combination of gender law and succession type produces 15 distinct behaviours.
The most important pairings in practice:

| Gender Law | Succession | CK3 equivalent | Typical use |
|---|---|---|---|
| AGNATIC | PRIMOGENITURE | Agnatic Primogeniture | Standard medieval patrilineal |
| AGNATIC | SENIORITY | Agnatic Seniority | Tribal/nomadic patrilineal elders |
| AGNATIC_COGNATIC | PRIMOGENITURE | Cognatic Primogeniture | Western Europe default |
| AGNATIC_COGNATIC | ULTIMOGENITURE | Cognatic Ultimogeniture | Youngest-son inheritance cultures |
| ABSOLUTE_COGNATIC | PRIMOGENITURE | Absolute Cognatic Primogeniture | Gender-equal succession |
| ENATIC_COGNATIC | PRIMOGENITURE | Enatic Cognatic Primogeniture | Matrilineal with male fallback |
| ENATIC | PRIMOGENITURE | Enatic Primogeniture | Strict matrilineal |

---

### 1.4 How Succession Affects the Simulation (not just the title file)

The gender law influences simulation behaviour in ways that affect the living
character pool — not just which name appears in `title_history.txt`.

**Marriage type recording.** The marriage event written into `family_history.txt`
is either `add_spouse` (patrilineal) or `add_matrilineal_spouse` (matrilineal).
Getting this wrong produces broken CK3 dynasties in-game.

**Child dynasty assignment.** Under agnatic laws the children always join the
father's dynasty. Under enatic laws they join the mother's. Under cognatic laws
the `elder_of()` tiebreak decides — it walks both parents' positions in their
respective sibling lists and grandparent chains to find the "senior" line. This
matters for dynasty population counts, which in turn affect fertility modifiers,
desperation marriage thresholds, and dynasty survival checks.

**Birth sex bias.** When a dynasty has no heir of the "correct" sex yet:
- AGNATIC / AGNATIC_COGNATIC: 90% chance first child is male
- ENATIC / ENATIC_COGNATIC: 90% chance first child is female
- ABSOLUTE_COGNATIC: 50/50

**Dynasty continuation check** (used by `forceDynastyAlive`). The check is
gender-law-aware: an agnatic dynasty is considered extinct if it has no living
male aged 16–80 capable of fathering children, even if many females remain alive.

---

### 1.5 Current Dynasty Configuration

| Dynasty | Gender Law | Succession |
|---|---|---|
| dynasty_enakynim | AGNATIC | PRIMOGENITURE |
| dynasty_haayaarim | AGNATIC | PRIMOGENITURE |
| dynasty_lokalim | AGNATIC | PRIMOGENITURE |
| dynasty_mbuumamim | AGNATIC | PRIMOGENITURE |
| dynasty_uyarazandim | AGNATIC | PRIMOGENITURE |

All five current dynasties use strict agnatic primogeniture. Only
`dynasty_uyarazandim` has `forceDynastyAlive: true`.

---

## 2. Personality Traits

Personality traits are assigned once per character at age 16 and written into the
CK3 history file as top-level `trait =` entries (outside any date block). They
are purely flavour from the simulation's perspective — they do not affect
fertility, mortality, or any other numerical system — but they matter enormously
for in-game character feel.

---

### 2.1 Assignment Mechanism

Configuration lives in `skills_and_traits.json` under `"personalityTraits"`.

```json
"personalityTraits": {
    "totalTraitsPerCharacter": 3,
    "brave": { "weight": 1, "excludes": ["craven"] },
    ...
}
```

The assignment algorithm (`Character.assign_personality_traits`) runs a weighted
random draw without replacement:

1. Build a pool of all traits, each with its configured weight.
2. Randomly draw one trait (weighted). Add it to the character's list.
3. Remove that trait **and every trait it excludes** from the pool.
4. Repeat until `totalTraitsPerCharacter` traits have been drawn or the pool is
   exhausted.

Because exclusions are one-directional in the JSON but applied bidirectionally at
draw time (a drawn trait removes both its own excludes *and* anything that lists
it in their own excludes), you will never see contradictory pairs on the same
character.

**`totalTraitsPerCharacter`** is currently **3**. Valid range: 1–N (bounded by
pool exhaustion after exclusions). Setting it higher than ~8 risks frequent pool
exhaustion for characters who happen to draw traits with many exclusions early.

---

### 2.2 Weight System

Every trait currently has `"weight": 1`, which means the draw is uniformly
random across all remaining eligible traits. To make a trait rarer, lower its
weight (e.g. `0.2`). To make it more common, raise it (e.g. `3`). Weights do
not need to sum to any particular value — only their *relative* ratios matter.

**Example:** setting `"sadistic"` to `"weight": 0.1` and everything else to `1`
makes sadistic roughly 10× less likely to appear than any other trait.

---

### 2.3 Complete Trait List and Exclusion Groups

Every pair listed below cannot appear on the same character. If the first trait
in a pair is drawn, the second is removed from the pool, and vice versa.

#### Paired Opposites (strict mutual exclusion)

| Trait A | Trait B | Interpretation |
|---|---|---|
| `brave` | `craven` | Courage vs cowardice |
| `calm` | `wrathful` | Temper |
| `chaste` | `lustful` | Sexual restraint |
| `content` | `ambitious` | Drive and desire |
| `diligent` | `lazy` | Work ethic |
| `forgiving` | `vengeful` | Response to slights |
| `generous` | `greedy` | Attitude to wealth |
| `gregarious` | `shy` | Social disposition |
| `honest` | `deceitful` | Truthfulness |
| `humble` | `arrogant` | Self-regard |
| `just` | `arbitrary` | Fairness |
| `patient` | `impatient` | Self-control over time |
| `temperate` | `gluttonous` | Restraint in pleasure |
| `trusting` | `paranoid` | Suspicion of others |
| `zealous` | `cynical` | Religious conviction |

#### Three-Way Exclusion Group

These three cannot coexist in any combination — drawing any one removes the
other two:

| Trait | Excludes |
|---|---|
| `compassionate` | `callous`, `sadistic` |
| `callous` | `compassionate`, `sadistic` |
| `sadistic` | `compassionate`, `callous` |

#### Four-Way Exclusion Group

These cannot coexist — drawing any one removes the other three:

| Trait | Excludes |
|---|---|
| `fickle` | `stubborn`, `eccentric` |
| `stubborn` | `fickle`, `eccentric` |
| `eccentric` | `stubborn`, `fickle` |

*(Note: `eccentric` also excludes both `fickle` and `stubborn`, effectively
making this a fully mutual 3-way group.)*

---

### 2.4 Total Pool Size and Draw Probability

With all weights at 1 the pool starts at 28 traits. After one draw and its
exclusion removals:

- Simple pairs (15 pairs): removes 1 trait → pool shrinks by 2
- Three-way group: removes 2 traits → pool shrinks by 3
- Four-way group: removes 2 traits → pool shrinks by 3

Worst case for first draw: drawing `compassionate`, `callous`, or `sadistic`
removes 2 others (pool → 25). For the second draw the pool is 25–26 traits. For
the third draw it is 23–24 traits. Pool exhaustion before 3 traits is essentially
impossible with the current 28 traits.

---

### 2.5 Childhood Traits

These five traits are **not** in `personalityTraits` and cannot be configured
there. They are assigned automatically by the simulation at age 3, derived from
the character's dominant education skill:

| Education Skill | Possible Childhood Traits |
|---|---|
| `diplomacy` | `charming`, `curious` |
| `intrigue` | `charming`, `rowdy` |
| `martial` | `rowdy`, `bossy` |
| `stewardship` | `pensive`, `bossy` |
| `learning` | `pensive`, `curious` |

One is chosen at random (50/50) from the pair for the character's education
skill. These traits are written as top-level `trait =` lines in the export (not
inside a date block), per CK3 requirements for childhood traits.

---

### 2.6 Export Behaviour

At age 16 the personality traits are emitted inside a `YYYY.MM.DD = { }` date
block in the character's history entry:

```
1016.04.12 = {
    trait = ambitious
    trait = wrathful
    trait = deceitful
}
```

Childhood traits (from the age-3 event) are stripped out of all date blocks by
`format_for_export()` and placed as bare `trait = charming` lines at the top
level of the character block instead. This is required by CK3's character history
parser.

---

## 3. Name Inheritance Chances

Each dynasty independently configures how likely its children are to receive
names from their lineage versus a fresh name from the culture pool.

```json
"nameInheritance": {
    "grandparentNameInheritanceChance": 0.05,
    "parentNameInheritanceChance":      0.05,
    "noNameInheritanceChance":          0.90
}
```

**Hard constraint: the three values must sum to exactly 1.0.** The GUI and the
Pydantic validator both enforce this. A sum outside 1.0 ± 0.000001 will cause a
save error in the GUI and a `ValueError` crash if the config is loaded directly.

---

### 3.1 How the Draw Works

When a child is born, the simulation performs a single weighted random draw from
three outcomes:

```
chosen = random.choices(
    ["grandparent", "parent", "none"],
    weights=[grandparentChance, parentChance, noChance]
)
```

#### `grandparent` outcome
- For a **male** child: takes the paternal grandfather's name (`father.father.name`)
- For a **female** child: takes the maternal grandmother's name (`mother.mother.name`)
- If the relevant grandparent does not exist (progenitor generation, or absent
  parent), the draw falls through to the `none` path and a fresh name is picked
  from the culture pool

#### `parent` outcome
- For a **male** child: takes the father's name
- For a **female** child: takes the mother's name

#### `none` outcome
Picks a fresh name from the culture name list (`name_lists/<culture>_<gender>.txt`),
with a uniqueness preference — names already used by living siblings are excluded
from the candidate pool. If all culture names are already taken by living siblings,
a duplicate is allowed with a warning logged.

---

### 3.2 Effect on Dynasty Feel

| Setting | Result |
|---|---|
| High `grandparentNameInheritanceChance` | Strong ancestral naming patterns; same names recur every two generations |
| High `parentNameInheritanceChance` | Father/son, mother/daughter name chains; surnames feel like nicknames |
| High `noNameInheritanceChance` | Diverse names; each character feels individually distinct |
| Balanced split (e.g. 0.25/0.25/0.50) | Mixed — some notable ancestral names but still plenty of variety |

---

### 3.3 Current Configuration

All five dynasties use the same defaults:

| Field | Value | Meaning |
|---|---|---|
| `grandparentNameInheritanceChance` | `0.05` | 5% chance of grandfather/grandmother's name |
| `parentNameInheritanceChance` | `0.05` | 5% chance of father/mother's name |
| `noNameInheritanceChance` | `0.90` | 90% chance of a fresh culture name |

This is a low-inheritance setting, producing very diverse name sets across the
dynasty. To increase dynastical naming patterns (more "Théodred son of Théoden"
feel), raise the grandparent and/or parent chances and lower `noNameInheritanceChance`
by the same total amount.

---

### 3.4 Interaction with `ensure_unique_name`

The `none` path calls `ensure_unique_name()`, which filters the culture pool to
exclude names already held by **living** siblings. This means:

- Large families with many living children will consume culture names faster
- If the culture name file is short and `maximumNumberOfChildren` is high, the
  pool can run dry — the simulation logs a warning and allows a duplicate
- The uniqueness check only looks at **living** siblings, so names of deceased
  children can be reused (historically common practice)

---

## 4. Languages

Languages allow you to mark that members of a dynasty born within a certain year
range automatically `learn_language` at birth. This is written directly into the
`birth = yes` event block in `family_history.txt` so CK3 picks it up without any
additional event scripting.

---

### 4.1 Format

Each language entry is a **comma-separated string** inside the dynasty's
`"languages"` array:

```json
"languages": [
    "language_westron,6800,7033",
    "language_sindarin,6900,7033"
]
```

The three parts are:
1. **`language_id`** — the CK3 script identifier for the language (must match
   your mod's language definitions exactly, case-sensitive)
2. **`start_year`** — first birth year for which the language is applied
   (inclusive)
3. **`end_year`** — last birth year for which the language is applied (inclusive)

---

### 4.2 What Gets Written to the File

When a character's birth year falls within a language entry's `[start_year,
end_year]` range, the generator emits a `learn_language` call inside that
character's birth event block:

```
1016.04.12 = {
    birth = yes
    effect = {
        learn_language = language_westron
        learn_language = language_sindarin
    }
}
```

If a character's birth year does not match any language entry for their dynasty,
no `effect` block is written and the birth event remains a bare `birth = yes`.

Multiple languages can be active simultaneously — all entries whose year range
covers the character's birth year are included in the same `effect` block.

---

### 4.3 Year Range Overlap

You can stack multiple entries with overlapping or sequential ranges to model
language shifts:

```json
"languages": [
    "language_khuzdul,5000,6500",
    "language_westron,6200,7033"
]
```

A character born in year 6300 would receive **both** `language_khuzdul` and
`language_westron`. A character born in 5500 receives only `language_khuzdul`.
A character born in 6700 receives only `language_westron`.

This is useful for modelling gradual cultural transitions — an overlap period
represents a bilingual generation.

---

### 4.4 Validation and Parsing

Language entries are parsed in both `config_loader.py` and `simulation.py`
(when building `Character.DYNASTY_LANGUAGE_RULES`). Malformed entries — wrong
number of comma-separated parts, or non-integer year values — are **silently
skipped** with a warning logged. They do not cause a crash.

The GUI (`DynastySettings.tsx`) provides per-entry inputs for the language ID,
start year, and end year, and stores them back as comma-separated strings. The
three inputs are always shown as separate fields for legibility.

---

### 4.5 Current Configuration

All five dynasties currently have empty language arrays:

```json
"languages": []
```

No `learn_language` effects will be written to any character's birth block. To
add a language to a dynasty, either edit `initialization.json` directly or use
the **Dynasty Settings** tab → expand a dynasty → **Add Language**.

---

### 4.6 Common `language_id` Values (CK3 vanilla + popular mods)

These are example identifiers only — the correct IDs depend on your specific
mod's `common/languages/` definitions:

| Context | Example ID |
|---|---|
| Vanilla English | `language_english` |
| Vanilla Latin | `language_latin` |
| Vanilla Old Norse | `language_old_norse` |
| LOTR mod (Westron) | `language_westron` |
| LOTR mod (Sindarin) | `language_sindarin` |
| LOTR mod (Khuzdul) | `language_khuzdul` |
| LOTR mod (Black Speech) | `language_black_speech` |

Always verify identifiers against the actual language files in your mod before
configuring them here.

---

## Quick Reference

### Changing succession for a dynasty
```json
"succession": "PRIMOGENITURE",   // PRIMOGENITURE | ULTIMOGENITURE | SENIORITY
"gender_law": "AGNATIC_COGNATIC" // AGNATIC | AGNATIC_COGNATIC | ABSOLUTE_COGNATIC | ENATIC_COGNATIC | ENATIC
```

### Making a trait rarer
```json
"sadistic": { "weight": 0.1, "excludes": ["compassionate", "callous"] }
```

### Making names more ancestral
```json
"nameInheritance": {
    "grandparentNameInheritanceChance": 0.30,
    "parentNameInheritanceChance":      0.20,
    "noNameInheritanceChance":          0.50
}
```

### Adding a language
```json
"languages": ["language_westron,6800,7033"]
```
