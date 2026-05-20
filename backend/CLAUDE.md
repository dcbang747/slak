# Backend — `backend/app/`

See root `CLAUDE.md` for architecture overview, commands, and coupling points.

---

## Module responsibilities

| File | Role |
|---|---|
| `main.py` | FastAPI endpoints. Thin layer: upload endpoints parse on-the-fly and return previews; `/generate` queues a job via `jobs.py`. |
| `jobs.py` | In-process generation: a `ThreadPoolExecutor` + in-memory job store. `submit_generation()` queues a run (parse → `run_simulation()` → ZIP → `RESULTS_DIR`); `get_job()` reads its state. Replaces Celery/Redis. TTL-prunes finished jobs. |
| `parser.py` | Paradox `.txt` → Python dict AST + all domain extractors. |
| `schemas.py` | Pydantic models for `SimulationPayload` and all internal entities. |
| `simulation.py` | `WorldState` class + `run_simulation()` year-tick loop + all transition helpers. |
| `genetics.py` | `inherit_traits()` for children; `roll_birth_traits()` for founder characters. |
| `mortality.py` | `annual_death_check()` — Gompertz age curve calibrated to `average_lifespan` → death reason picker. |
| `output.py` | Renders `WorldState` → Paradox `.txt` + `.yml` files. **Format is immutable per spec — do not alter output templates without a spec change.** |

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Returns `{"status":"ok"}` |
| POST | `/upload/titles` | Parses title history → `{filename, title_ids (flat list), raw}` |
| POST | `/upload/traits` | Parses genetic traits → `{filename, traits (list), raw}` |
| POST | `/upload/deaths` | Parses death reasons → `{filename, deaths (list), raw}` |
| POST | `/upload/names` | Parses name lists → `{filename, name_lists (dict), raw}` |
| POST | `/upload/dynasties` | ⚠️ Exists but **unused by frontend** — dynasties are user-defined via UI, not uploaded |
| POST | `/upload/religions` | Parses religion file → `{filename, religions (marital doctrines dict), raw}` |
| POST | `/upload/secrets` | Parses secret types → `{filename, secret_ids (list), raw}` |
| POST | `/generate` | Accepts `SimulationPayload`, queues a job, returns `{task_id}` |
| GET | `/status/{task_id}` | Returns `{state, message?, result?, error?}` |
| GET | `/result/{task_id}/tree` | Returns the family-tree JSON (used by the Family Tree view) |
| GET | `/download/{task_id}` | Streams the result ZIP |

The `/status` response shape: `state` (`PENDING`/`PROGRESS`/`SUCCESS`/`FAILURE`), `message` (during PROGRESS), `result.characters` + `result.titles_with_history` on SUCCESS, `error` on FAILURE. `RightDrawer.jsx` reads exactly these keys — do not rename them. `jobs.py` emits these state strings to match what the frontend already expected from Celery.

---

## Parser — `parser.py`

### How the Paradox AST parser works

`parse(text)` → `tokenize()` → `_parse_block()` → Python dict/list

**Tokenizer rules:**
- Strips UTF-8 BOM — common in Windows-saved Paradox files
- Strips `# comments`
- Pads `{`, `}`, `=` with spaces so they split as standalone tokens
- Preserves double-quoted strings as single tokens (strips the quotes)

**Block parser rules:**
- `key = value` → dict entry
- `key = { ... }` → nested dict or list (recursive)
- Bare token with no `=` following → list element (e.g. `colors = { 1 2 3 }`)
- **Duplicate keys at the same scope collapse into a Python list**

### Domain extractors

| Function | Input | Returns |
|---|---|---|
| `transform_titles(ast)` | top-level AST dict | Recursive title tree: `{id, tier, is_landed, metadata, children}` |
| `extract_title_ids_from_history(ast)` | title history AST dict | Flat list of title ID strings (top-level keys) |
| `extract_genetic_traits(ast)` | top-level AST dict | List of `{id, group, level, birth_chance, random_creation, opposites}` |
| `extract_death_reasons(ast)` | top-level AST dict | List of `{id, is_natural, required_trait}` |
| `extract_name_lists(ast)` | top-level AST dict | Dict: `{culture_male: [...], culture_female: [...], default_male: [...], default_female: [...]}` |
| `extract_dynasties(ast)` | top-level AST dict | `{dynasties: [{id, name, culture, motto}], houses: [{id, name, dynasty, motto}]}` |
| `extract_religions(ast)` | top-level AST dict | Dict: `{faith_id: marital_doctrine_string}` — root sets default; faith overrides if present |
| `extract_secrets(ast)` | top-level AST dict | List of `secret_*` ID strings — root keys only, all internal blocks discarded |

### Title classification

Prefix → tier: `h_` hegemony, `e_` empire, `k_` kingdom, `d_` duchy, `c_` county, `b_` barony.
`h_` titles are titular (not landed) unless they contain at least one child map-title key.

### Genetic trait field name conventions

Real Paradox files use `birth = 5` (integer 0–100). The custom `samples/` format uses `birth_chance = 0.06` (float 0–1). `extract_genetic_traits()` prefers `birth_chance`; falls back to `birth / 100`. `random_creation` normalised the same way (divide by 100 if > 1.0).

### Name list format

Real Paradox files: `name_list_culture = { male_names = { 0 = { never-use } 10 = { common } } female_names = { ... } }`.

`extract_name_lists()`:
- Walks `name_list_*` keys; strips prefix to get culture ID
- Skips weight-0 groups (`0 = { ... }` = "never sample" in Paradox)
- Recurses through list-of-lists from duplicate `0 = {}` keys via `_flatten_names()`
- Adds `default_male` / `default_female` from the first name list — required because characters start with `culture = "default_culture"` and `_pick_name()` falls back to these keys

### Dynasty / house file format

`RawSampleFiles/Dynasties/` shows the canonical structure:
- `dynasty_X = { name = "dynn_X" culture = "culture_id" motto = dynn_X_motto }` — base dynasty
- `house_Y = { name = "dynn_Y" dynasty = dynasty_X motto = dynn_Y_motto }` — cadet branch only

**The main house of a dynasty does NOT get a `house_` entry** (confirmed by comments in `arnorian_houses.txt`). Only cadet branches are defined as `house_` entries. `motto` is optional.

Dynasties are now user-defined via the UI (`dynasty_definitions` in the payload) rather than uploaded from file. `extract_dynasties()` is kept for potential future use but is not called during generation.

### Religion file format

Structure: `religion_id = { ... faiths = { faith_id = { ... } } }`. Extract only marital doctrines:
- Root religion sets the default: `doctrine = doctrine_monogamy` (or other marital doctrine)
- Individual faiths may override: inner `doctrine = doctrine_concubines` overrides root; absent = inherits root
- Discard all other content (cosmetic blocks, localization, holy orders, non-marital doctrines)

Valid marital doctrine values: `doctrine_monogamy`, `doctrine_polygamy`, `doctrine_concubines`.

### Secret type file format

⚠️ **Secrets are no longer uploaded.** `extract_secrets()` still parses root-level keys (used by the `/upload/secrets` endpoint) but the simulation ignores it. Secrets come from a hardcoded catalogue in `simulation.py`:

```
_SECRET_CATALOGUE = {
  secret_deviant, secret_homosexual, secret_cannibal, secret_non_believer,  # bare add_secret
  secret_murder_attempt, secret_murder,                                     # block w/ target
  secret_lover,                                                             # block w/ target + set_relation_lover
  secret_incest,                                                            # bare; partner is a ≤3rd-degree relative; optional lover
}
```

`_generate_secrets()` (post-pass, gated on `enable_secrets`) rolls these for ~15% of characters; `output.py` chooses the bare vs. block form via `_SECRET_TARGET_FORM`.

---

## Simulation Engine — `simulation.py`

### `run_simulation()` flow

1. **`cascade_sequences()`** — any title without an explicit user-configured sequence inherits the nearest ancestor's sequence. User-configured titles are always included even if absent from the uploaded title hierarchy.
2. **Bootstrap** — each title gets a founder character born 35 years before `start_year`, plus an immediate spouse so natural children can be born. `world.explicit_title_ids` is populated from `payload.title_sequences.keys()`.
3. **Year-by-year tick** (`start_year` → `end_year`):
   - **Mortality**: `annual_death_check()` for every living character
   - **Childhood traits**: characters reaching age 3 get their `childhood_trait` assigned from the `_EDUCATION_CHILDHOOD_TRAITS` map (guarded by `childhood_trait_assigned`)
   - **Personality traits**: characters reaching age 16 get `personality_traits` assigned via weighted draw with exclusion groups (guarded by `personality_assigned`)
   - **Fertility**: legitimate children + bastards for living married couples; sex biased by `gender_law` if no male/female heir yet (`_bias_sex()`)
   - **Succession**: if a ruler is dead, `_find_heir()` searches by succession type (PRIMOGENITURE/ULTIMOGENITURE/SENIORITY) and gender_law filter. If none, fabricates a new ruler. If a sequence has expired, executes the transition.
4. Stops early if `maximum_generations` is reached.

### Succession system

**`_find_heir(dynasty_def, ruler, world, year)`** — selects the next ruler based on `dynasty_def.succession` and `dynasty_def.gender_law`:

| Succession | Candidate pool |
|---|---|
| PRIMOGENITURE | Depth-first eldest child → recurse into eldest child's line before next sibling |
| ULTIMOGENITURE | Same as PRIMOGENITURE but youngest child first |
| SENIORITY | All living dynasty members aged 16–80 born ≤ death year; pick oldest |

Gender filtering by `gender_law`:
- `AGNATIC` → males only
- `AGNATIC_COGNATIC` → males first, then females if no male found
- `ABSOLUTE_COGNATIC` → all together (elder_of determines child dynasty)
- `ENATIC_COGNATIC` → females first, then males
- `ENATIC` → females only

**`_bias_sex(gender_law, dynasty_id, world, rng)`** — if an AGNATIC/AGNATIC_COGNATIC dynasty has no living male heir, next child is 90% male. ENATIC/ENATIC_COGNATIC flips to 90% female. ABSOLUTE_COGNATIC is always 50/50.

**`_elder_of(father, mother, world)`** — used under ABSOLUTE_COGNATIC to assign the child to the senior parent's dynasty (climbs sibling birth order recursively).

**Marriage type** in output: male ruler → `add_spouse`; female ruler → `add_matrilineal_spouse`.

### Name inheritance

**`_pick_name_with_inheritance(char, dynasty_def, name_lists, rng)`** — weighted draw over `["grandparent", "parent", "none"]` using `dynasty_def.name_inheritance`. Grandparent/parent fallback to `none` if the relevant ancestor is missing. Used for non-founders; founders still use `_pick_name()`.

### Personality traits

**`_assign_personality_traits(char, config, rng)`** — draws `config.total_traits_per_character` traits via weighted random without replacement, skipping any trait whose exclusions are already in the selection. Stores result in `char.personality_traits` and `char.personality_trait_date`.

### Languages

**`_get_birth_languages(dynasty_def, birth_year)`** — parses `"language_id,start_year,end_year"` entries and returns IDs whose range covers `birth_year`. Malformed entries are skipped with a warning.

### Title transitions

Dispatch is based on `current_seq.transition_method` (describes how the outgoing sequence ends):

| Method | Behaviour |
|---|---|
| `marriage` | Heir of outgoing house marries into incoming house; children born into incoming house via `force_child_house` |
| `usurpation` | Outgoing ruler displaced (killed hostile death); incoming house claimant takes title |
| `extinction` | Last generation of outgoing house has `fertility_multiplier = 0`; incoming house founder created fresh |

### `_pick_name()` key priority

Tries in order: `{culture}_female/male` → `{culture}` → `default_female/male` → `default`. Returns `"Unnamed"` if nothing matches.

### `_dynasty_culture_faith(dynasty_def, year)`

Returns `(culture, faith)` for a dynasty at a given year by finding the active `CultureFaithPeriod` (latest period with `start_year <= year`). Falls back to `("default_culture", "default_faith")` if no periods are configured.

### Character IDs

`WorldState._make_char_id(dynasty)` generates `lineof{slug}{N}` where slug is the last segment of the dynasty ID after stripping the `dynasty_`/`house_` prefix. Examples: `lineofbeor1`, `lineofX3`, `bastard2`. Bastards (empty dynasty) always get the `bastard_N` prefix.

### Character dynasty field

The `Character` model has two distinct fields — exactly one should be set:
- `dynasty: str` — main-house members; outputs `dynasty = dynasty_X` in character_history.txt
- `dynasty_house: str` — cadet branch members; outputs `dynasty_house = house_Y`

`make_character(dynasty=...)` auto-detects: if the string starts with `house_`, sets `dynasty_house`; otherwise sets `dynasty`. Bastards get both fields empty.

`_char_dynasty_id(c)` helper returns `c.dynasty_house or c.dynasty` for comparisons (e.g., in `_find_heir`).

### Random seed

`global_settings.random_seed` (default `1337`) is passed to `random.Random(seed)`. Identical inputs always produce identical outputs.

---

## Genetics — `genetics.py`

`inherit_traits(mother_traits, father_traits, registry, rng, trait_multiplier=1.0)`:
1. Cancel opposite pairs across parents
2. Homogenous (both share a group): 80% × multiplier chance to inherit at highest level; 20% × multiplier at level+1
3. Heterogenous (one parent): 50% × multiplier inherit level-1, 10% × multiplier inherit parent level
4. Spontaneous mutation: roll `random_creation × multiplier` for every group neither parent has (level-1 wins)

`roll_birth_traits(registry, rng, trait_multiplier=1.0)` — for founder characters with no parents; uses `birth_chance × multiplier` at level 1 only.

`trait_multiplier` comes from `global_settings.trait_frequency_multiplier` (default 1.0). Values > 1.0 increase frequency, < 1.0 reduce it, 0.0 disables all trait inheritance. Applied as a pre-roll scale — the registry is never mutated.

---

## Mortality — `mortality.py`

`annual_death_check(character, year, rng, avg_lifespan)` → `base_mortality(age, avg_lifespan)` → if death rolls, pick a death reason via `pick_death_reason()`. `avg_lifespan` comes from `life_cycle.average_lifespan`.

**Mortality curve**: a Gompertz hazard `h(age) = A·e^(G·age)` with `G = 0.10`, and `A` solved so the **mean age at death equals `average_lifespan`** (`A = G·e^(−(G·L + γ))`, γ = Euler-Mascheroni). Capped at 0.99. Deaths cluster around `L` with a spread of ~13 years, so characters rarely exceed ~`L + 25`. Verified empirically: setting 50/70/90 yields mean death age ≈ 50/70/89 with the max staying below ~`L + 25`.

**Death reasons are hardcoded** (no upload). `pick_death_reason()` builds a weighted pool: `death_natural_causes` (baseline), `death_old_age` for age ≥ 60, plus any trait-triggered death the character qualifies for (8× weight). Trait→reason map in `_TRAIT_DEATH_REASONS` (e.g. `giant`→`death_giant`, `physique_bad_1`→`death_physique_bad_1`). `pick_hostile_death(rng)` returns one of `death_murder` / `death_battle` / `death_execution` for usurpation transitions.

---

## Schemas — `schemas.py`

### `SimulationPayload` (current shape)

```
SimulationPayload
├── global_settings: GlobalSettings
│   ├── start_year (default 6800)
│   ├── end_year (default 7000)
│   ├── maximum_generations (default 30)
│   ├── random_seed (default 1337)          ← always overwritten by buildPayload() with Math.random()
│   ├── trait_frequency_multiplier (default 1.0)
│   ├── ignore_title_generation (default false)
│   ├── enable_secrets (default false)      ← when true, rolls hardcoded secrets (no upload)
│   ├── enable_relationships (default false) ← when true, rolls built-in relationships between contemporaries
│   └── personality_traits: PersonalityTraitsConfig
│       ├── total_traits_per_character (default 3)
│       └── traits: dict[name → {weight, excludes[]}]  ← 28 CK3 traits pre-populated
├── life_cycle: LifeCycleModifiers
│   ├── max_age_difference_between_partners (default 20)
│   ├── max_children_per_couple (default 3)
│   ├── base_fertility_rate (default 0.35)
│   ├── male_bastard_chance (default 0.05)
│   ├── female_bastard_chance (default 0.02)
│   ├── dynasty_soft_cap (default 50)       ← living-member count beyond which fertility damps
│   └── average_lifespan (default 70)       ← mean age at death; calibrates the mortality curve
├── parsed_files: ParsedFileData
│   ├── titles_txt: str | null        ← raw .txt, re-parsed at generation time
│   ├── traits_txt: str | null        ← raw .txt, re-parsed at generation time
│   ├── deaths_txt: str | null        ← legacy field, unused (deaths are hardcoded)
│   ├── name_lists: dict[str, list]   ← already-extracted, used directly
│   ├── religions_txt: str | null     ← raw .txt, re-parsed at generation time
│   ├── secrets_txt: str | null       ← legacy field, unused (secrets are hardcoded)
│   ├── dynasties_txt: str | null     ← legacy field, not sent by frontend
│   └── dynasties: dict               ← legacy field, not sent by frontend
├── title_sequences: dict[title_id → list[DynastySequence]]
│   └── {dynasty_id, duration_type, duration_value, transition_method,
│        government_type, liege_title_id, lowborn_spouses_only, conversions[]}
└── dynasty_definitions: list[DynastyDefinition]
    └── {id, name, motto, start_year, end_year,
         culture_faith_periods[{start_year, culture, faith}],
         gender_law,        ← AGNATIC|AGNATIC_COGNATIC|ABSOLUTE_COGNATIC|ENATIC_COGNATIC|ENATIC
         succession,        ← PRIMOGENITURE|ULTIMOGENITURE|SENIORITY
         lowborn_spouses, guaranteed_survival,
         name_inheritance: {grandparent_chance, parent_chance, no_name_chance},
         languages[]}       ← each entry: "language_id,start_year,end_year"
```

**`store.buildPayload()` must stay in sync with this schema.** Adding a field to one without the other silently drops or rejects it.

### `Character` internals

| Field | Purpose |
|---|---|
| `dynasty: str` | Base dynasty ID for main-house members → `dynasty = dynasty_X` in output |
| `dynasty_house: str` | Cadet house ID → `dynasty_house = house_Y` in output; set only for cadet members |
| `force_child_house: Optional[str]` | Set during marriage transitions — next child born to this couple inherits House B |
| `is_bastard: bool` | Bastards have both dynasty fields empty; don't count against `max_children_per_couple` |
| `fertility_multiplier: float` | Set to `0.0` for extinction last-generation zero-out |
| `education_skill: str` | One of 5 skills assigned at birth; determines childhood trait pool |
| `childhood_trait: Optional[str]` | Assigned at age 3 from `education_skill` map; written as top-level `trait =` line |
| `personality_traits: list[str]` | Assigned at age 16 via weighted draw respecting exclusion groups |
| `personality_trait_date: Optional[str]` | `YYYY.M.D` of 16th birthday — gates the personality trait date block in output |
| `marriages: list[dict]` | Each entry: `{"date", "spouse_id", "type"}` — written as date blocks before birth block |
| `birth_languages: list[str]` | Language IDs active at birth year; written as `learn_language` in birth block effect |
| `childhood_trait_assigned: bool` | Guard flag — prevents double-assignment at age 3 |
| `personality_assigned: bool` | Guard flag — prevents double-assignment at age 16 |

---

## Output — `output.py`

Renders `WorldState` into files packed into a ZIP:

- `character_history.txt` — characters grouped by dynasty (sorted alphabetically by dynasty ID), each group preceded by a comment header; bastards appended last
- `title_history.txt` — one block per **explicitly user-configured title** only (cascade-inherited child titles are filtered out); omitted entirely if `ignore_title_generation = true`
- `00_dynasties.txt` — Paradox dynasty definitions; generated from `world.dynasty_ids_used`, looked up against `world.dynasty_defs` for real culture and motto
- `dynasty_names_l_english.yml` — UTF-8 BOM localization; dynasty display names only (`dynn_X: "..."`)
- `dynasty_mottos_l_english.yml` — UTF-8 BOM localization; dynasty mottos only (`dynn_X_motto: "..."`). Names and mottos are split into two files; the `_l_english` suffix is mandatory for CK3 to load the localization. Both fall back to `#DEBUG TEMP#!` if blank.

**The output format is immutable** — exact Paradox Clausewitz syntax. Any whitespace change, key reorder, or conditional omission breaks the game parser. Do not modify templates unless the spec changes.

Key formatting rules per character block (in order):
1. `name`, `dynasty`/`dynasty_house`, `religion`, `culture`
2. `female = yes` only if female (omit for males — never write `female = no`)
3. `father`/`mother` if known
4. Genetic `trait =` lines (top-level, no date block)
5. `trait = {childhood_trait}` (top-level, no date block) if set
6. Marriage date blocks: `YYYY.M.D = { add_spouse = id }` or `add_matrilineal_spouse`; sorted chronologically; before birth block
7. Birth block: `YYYY.M.D = { birth = yes }` — with `effect = { learn_language = X }` lines if `birth_languages` is non-empty
8. Relationship effect blocks (if any): `YYYY.M.D = { effect = { set_relation_X = character:ID } }` — one per `Character.relationships` entry (X ∈ lover/soulmate/rival/nemesis/friend/best_friend/bully/crush)
9. Secret effect blocks (if any): bare `add_secret = secret_X`, or block `add_secret = { type = secret_X target = character:Y }` for murder/murder_attempt/lover; `secret_lover` (and incest-lover) also emit `set_relation_lover = character:Y` in the same block — one per `Character.secrets` entry
10. Personality trait date block: `YYYY.M.D = { trait = ... }` at age-16 date; after birth block
11. Employer block (claimant displacement) if `employer_id` and `employer_date`
12. Death block if `death_date`

Other rules:
- `dynasty = X` or `dynasty_house = Y` — never both; auto-detected from `Character.dynasty_house`
- `killer = ...` included only if `killer_id` is set
- Death reason fallback: `death_natural_causes`
- Title history date blocks: `government` and `liege` fields *(not yet implemented)*
- LAAMP titles (`d_laamp_*`): special `effect` block format *(not yet implemented)*
- NF titles (`d_nf_*`): `noble_family_succession_law` format *(not yet implemented)*

### Character history dynasty headers

```
################################
### dynasty_beor | House of Beor ###
################################
```

`render_character_history()` groups characters by `dynasty_house or dynasty`, sorts groups alphabetically by dynasty ID, prepends a header for each group. Bastards (no dynasty) are collected into a `BASTARDS` group appended at the end.

### Auto-generated dynasty `.txt` format

Base dynasties output first, then houses. Culture comes from the first non-empty `culture_faith_periods` entry. `motto =` line **always emitted** (never conditional):

```
dynasty_beor = {
    name = "dynn_beor"
    culture = "beorian"
    motto = dynn_beor_motto
}

house_isildur = {
    name = "dynn_isildur"
    # dynasty = dynasty_PARENT  # fill in parent dynasty
}
```

### Dynasty `.yml` output format

Names and mottos go to **two separate files**, each written with UTF-8 BOM, `l_english:` header, and one leading space before every key. Values double-quoted; fallback text is `#DEBUG TEMP#!` when blank:

`dynasty_names_l_english.yml`:
```
l_english:

 dynn_beor: "House of Beor"
```

`dynasty_mottos_l_english.yml`:
```
l_english:

 dynn_beor_motto: "Born of Earth and Star"
```

---

## File Format Compatibility

`RawSampleFiles/` contains actual Paradox mod files from the LotR CK3 mod. Use these for all real testing.

| Upload | Real Paradox format | Parser status |
|---|---|---|
| Title History | `k_/e_/d_` blocks with `YYYY.M.D = { holder = ... }` | ✅ Fully supported — `extract_title_ids_from_history()` |
| Death Reasons | `death_id = { natural = yes ... }` blocks | ⚠️ Parser exists but **unused** — death reasons are hardcoded by trait/age in `mortality.py` (no upload needed) |
| Genetic Traits | `trait_id = { genetic = yes birth = 5 ... }` | ✅ Fully supported — both `birth` (int 0–100) and `birth_chance` (float 0–1) normalised |
| Name Lists | `name_list_X = { male_names = { 10 = { ... } } }` | ✅ Fully supported — weighted groups, flat lists, weight-0 skip, BOM strip |
| Dynasties | `dynasty_X = { ... }` and `house_Y = { dynasty = dynasty_X }` | ✅ Parser supported — but not used; dynasties are user-defined via UI |
| Religions | `religion_id = { ... faiths = { faith_id = { ... } } }` | ✅ Supported — marital doctrines only; `extract_religions()` |
| Secrets | Root-level `secret_type_id = { ... }` blocks | ⚠️ Parser exists but **unused** — secrets are a hardcoded catalogue in `simulation.py` (`_SECRET_CATALOGUE`), no upload needed |
| Localization (.yml) | UTF-8 BOM + `l_english:` + ` key: "value"` | ✅ Output only — `render_dynasties_yml()` |

### Multiple files per upload

Name list files frequently contain multiple `name_list_*` blocks in one file — all are extracted in one upload.
