# Frontend — `frontend/src/`

See root `CLAUDE.md` for architecture overview, commands, and coupling points.

---

## Component tree

```
App.jsx
├── LeftSidebar.jsx      — file dropzones + navigation + Generate button + Tutorial toggle
├── CenterWorkspace.jsx  — renders the active view
│   ├── GlobalSettings.jsx     — two-column: simulation settings (left) + Dynasties panel (right)
│   ├── LifeCycleModifiers.jsx
│   ├── TitleHistories.jsx → GanttChart.jsx
│   └── FamilyTree.jsx     — React Flow tree (nav appears only after a successful run)
├── RightDrawer.jsx      — task progress log + Download ZIP
└── TutorialOverlay.jsx  — onboarding coachmarks (glow + arrow + popup) over data-tour anchors
```

Still pending (Jis_Additional.pdf):
- `CharacterNodeEditor.jsx` — interactive character editor modal

---

## Zustand store (`store.js`)

Single source of truth. Key sections:

| State key | Type | Description |
|---|---|---|
| `global_settings` | object | Simulation bounds + genetics/output flags |
| `life_cycle` | object | Fertility/mortality modifiers |
| `parsed_files` | object | Raw txt strings + extracted previews from all upload types |
| `title_sequences` | object | `{[titleId]: DynastySequence[]}` — legacy per-title block model (still in schema; superseded for uploaded titles by gap fills) |
| `title_gap_fills` | object | `{[titleId]: [{gap_start_year, gap_end_year, dynasty_ids[]}]}` — per-gap dynasty assignment (gaps >100yr allow several, split in order); set via `setTitleGapFillDynasties`, sent in `buildPayload` |
| `parsed_files.title_holder_events` | object | `{[titleId]: [{date, year, vacant}]}` from `/upload/titles` — drives the Gantt's locked bars + gap detection |
| `dynasty_definitions` | array | User-defined dynasties with full properties |
| `tutorial_enabled` | bool | Master switch for the onboarding tour (persisted); toggled by the header "Tutorial" checkbox. Finishing/skipping sets it false |
| `tutorial_step` | number | Current coachmark index (ephemeral, resets to 0) |
| `active_view` | string | `'global'` \| `'lifecycle'` \| `'events'` \| `'titles'` |
| `drawer_open` | bool | Right drawer visibility |
| `task_state/result/error` | various | `'RUNNING'`\|`'SUCCESS'`\|`'FAILURE'` + stats/error for the right drawer (set from the one-shot `/generate` response — no polling) |
| `tree_data` | object | Family-tree JSON from `/generate`, read by the Family Tree view |
| `download_url` | string | Object URL built from the base64 ZIP; powers the Download button (revoked on reset) |

### `global_settings` shape

```js
{
  start_year: 6800,
  end_year: 7000,
  maximum_generations: 30,
  // random_seed is NOT stored in the Zustand state — buildPayload() always injects
  // Math.floor(Math.random() * 2147483647) at call time so every generation is unique.
  trait_frequency_multiplier: 1.0,  // scales birth_chance + random_creation in genetics
  ignore_title_generation: false,    // omit title_history.txt from ZIP
  enable_secrets: false,             // when true, backend rolls a hardcoded secret catalogue (no upload)
  enable_relationships: false,       // when true, backend rolls built-in relationships between contemporaries
  personality_traits: {
    total_traits_per_character: 3,
    traits: {  // 28 CK3 personality traits — each {weight, excludes[]}
      brave: { weight: 1.0, excludes: ['craven'] },
      // ... all 28 traits pre-populated by _defaultPersonalityTraits()
    },
  },
}
```

### `parsed_files` shape

```js
{
  // Sent to backend as raw txt, re-parsed at generation time
  titles_txt: null, traits_txt: null, deaths_txt: null,
  religions_txt: null, secrets_txt: null,
  // Pre-extracted — used directly in payload
  name_lists: {},       // {culture_male: [...], default_male: [...], ...}
  // UI-only previews
  titles: [],           // flat list of title ID strings from title history upload
  traits: [],           // genetic trait registry
  deaths: [],           // death reason list
  religions: {},        // {faith_id: marital_doctrine}
  secret_ids: [],       // list of secret type ID strings
  // Filenames displayed in dropzones
  titles_filename: null, traits_filename: null, deaths_filename: null,
  names_filename: null, religions_filename: null, secrets_filename: null,
}
```

### `dynasty_definitions` item shape

```js
{
  id: "dynasty_beor",              // Paradox ID — used in title_sequences
  name: "House of Beor",           // display name → dynn_beor in .yml; "#DEBUG TEMP#!" if blank
  motto: "Born of Earth and Star", // → dynn_beor_motto in .yml; "#DEBUG TEMP#!" if blank
  start_year: 6800,
  end_year: 7000,
  culture_faith_periods: [
    { start_year: 6800, culture: "beorian", faith: "faith_numenorean" }
  ],
  gender_law: "AGNATIC_COGNATIC",  // AGNATIC|AGNATIC_COGNATIC|ABSOLUTE_COGNATIC|ENATIC_COGNATIC|ENATIC
  succession: "PRIMOGENITURE",     // PRIMOGENITURE|ULTIMOGENITURE|SENIORITY
  lowborn_spouses: false,
  guaranteed_survival: false,
  name_inheritance: {
    grandparent_chance: 0.05,
    parent_chance: 0.05,
    no_name_chance: 0.90,          // must sum to 1.0
  },
  languages: [
    // Object form in store: {id, start_year, end_year}
    // buildPayload() serializes to string: "language_westron,6800,7033"
    { id: "language_westron", start_year: 6800, end_year: 7000 },
  ],
}
```

### Store actions

| Action | Description |
|---|---|
| `setGlobal(patch)` | Merge patch into `global_settings` |
| `setLifeCycle(patch)` | Merge patch into `life_cycle` |
| `setPersonalityTraitsConfig(patch)` | Merge patch into `global_settings.personality_traits` |
| `setPersonalityTraitWeight(name, weight)` | Update a single trait weight in the trait pool |
| `setParsedTitles(data)` | Set `titles_txt`, `titles`, `titles_filename` |
| `setParsedTraits(data)` | Set `traits_txt`, `traits`, `traits_filename` |
| `setParsedDeaths(data)` | Set `deaths_txt`, `deaths`, `deaths_filename` |
| `setParsedNames(data)` | Set `name_lists`, `names_filename` |
| `setParsedReligions(data)` | Set `religions_txt`, `religions`, `religions_filename` |
| `setParsedSecrets(data)` | Set `secrets_txt`, `secret_ids`, `secrets_filename` |
| `addDynastyDef()` | Append a new dynasty definition with defaults |
| `updateDynastyDef(id, patch)` | Patch a dynasty definition by id; **if `id` changes, automatically rewrites matching `dynasty_id` in all `title_sequences`** |
| `removeDynastyDef(id)` | Remove a dynasty definition by id |
| `addCultureFaithPeriod(dynId)` | Append a new period to a dynasty |
| `updateCultureFaithPeriod(dynId, idx, patch)` | Patch a specific culture/faith period |
| `removeCultureFaithPeriod(dynId, idx)` | Remove a culture/faith period |
| `updateDynastyNameInheritance(dynId, patch)` | Patch `name_inheritance` on a dynasty |
| `addDynastyLanguage(dynId)` | Append a blank language entry to a dynasty |
| `updateDynastyLanguage(dynId, idx, patch)` | Patch a language entry by index |
| `removeDynastyLanguage(dynId, idx)` | Remove a language entry by index |
| `buildPayload()` | Serialise store → `SimulationPayload` JSON for `/generate`; always injects a fresh `random_seed` |

**`store.buildPayload()` must stay in sync with `SimulationPayload` in `backend/app/schemas.py`.** Adding a field to one without the other silently drops or rejects it.

### Critical invariant — Generate button

`hasTitles && hasNames` is computed directly in `LeftSidebar.jsx` from subscribed `parsed_files` state — NOT via `store.isReady()`. Reverting to the store method causes React 18 concurrent-mode state divergence where the button stays disabled after upload. This pattern must not change.

---

## API proxy

All `api.js` calls prefix `/api`. Vite proxies `/api → http://localhost:8000` in local dev (`vite.config.js`). In Docker, `VITE_API_PROXY=http://api:8000` overrides the target. FastAPI has no `/api` prefix on its routes — stripping is done entirely in the Vite config.

`api.js` exports: `uploadTitles`, `uploadTraits`, `uploadDeaths`, `uploadNames`, `uploadReligions`, `uploadSecrets`, `uploadCultures`, `startGeneration` (one-shot — returns the full result), `zipBlobUrl` (base64 ZIP → object URL). `BASE` is `import.meta.env.VITE_API_BASE || '/api'`.

Generation is a single request: `LeftSidebar.onGenerate` awaits `startGeneration()`, then calls `setGenerationResult()` (sets `task_state='SUCCESS'`, `tree_data`, and `download_url` via `zipBlobUrl`). There is no `/status` polling, `/download`, or `fetchTree` — those endpoints and helpers were removed.

Note: `uploadDynasties` does **not** exist — dynasties are user-defined via the UI, not uploaded from file.

---

## GanttChart (existing-history / gap model)

Rewritten around uploaded title history. Each title row renders, positioned by absolute year (`x = (year - start_year) * pxPerYear`):
- **Locked grey bars** for existing occupied periods (any non-`0` holder) — read-only, never overwritten.
- **Amber dashed gap dropdowns** for vacant stretches >50yr within the Start/End window. A gap >100yr shows multiple side-by-side slots (`maxDyn = 1 + floor((len-1)/100)`) splitting the gap; choosing dynasties calls `setTitleGapFillDynasties(titleId, gapStart, gapEnd, dynastyIds[])`. Holders are drawn backend-side from each dynasty's real simulated members.

`computeSegments(events, start, end, minGap=50)` mirrors the backend `compute_title_gaps`/occupancy split exactly (verify both stay in sync). Gaps recompute live when Start/End years change. The legacy draggable-block model (`DynastyBlock`, drag/reorder, transition popover) was removed — assignment is now per-gap. `ROW_HEIGHT = 48`, `LABEL_WIDTH = 240`, `pxPerYear` auto-fits the container.

---

## GlobalSettings layout

Two-column flex layout (`flex gap-8 h-full`):
- **Left column** (`w-80 shrink-0`) — simulation settings:
  - Start/end year, max generations, trait frequency multiplier
  - Output option checkboxes (`ignore_title_generation`, `enable_secrets`, `enable_relationships`)
  - **Personality Traits** section: `total_traits_per_character` input + collapsible weight table (all 28 traits)
  - Random seed is **not shown** — a fresh seed is injected by `buildPayload()` on every generation
- **Vertical divider** (`border-l border-gray-300`)
- **Right column** (`flex-1 min-w-0 overflow-y-auto`) — Dynasties panel: add/remove/edit dynasty cards, each card has collapsible sections:
  - Basic info: ID, name, motto, start/end year
  - Culture & Faith Periods: list of `{start_year, culture, faith}` entries
  - Succession + Gender Law: side-by-side `<select>`s — *hidden in Simple mode*
  - Name Inheritance: three probability inputs (grandparent / parent / no-name) with sum indicator — *hidden in Simple mode*
  - Languages: list of `{id, start_year, end_year}` entries; serialized to strings in `buildPayload()` — *hidden in Simple mode*
  - Lowborn Spouses / Guaranteed Survival checkboxes (side by side; description shown via `(i)` `InfoTip`)

All year inputs (simulation + dynasty start/end) show the converted in-game era year in weak italics below the field via `toInGameYearLabel()` from `src/yearConvert.js` (e.g. `6800 → F.A. 2767`). The Family Tree node years use the bare `toInGameYear()` form.

Dynasty IDs entered here are referenced by the Title Histories Gantt chart when assigning dynasty sequences to titles. **Renaming a dynasty ID in GlobalSettings automatically propagates to all matching Gantt blocks** via `updateDynastyDef`.

---

## Onboarding tutorial (`TutorialOverlay.jsx`)

A non-blocking coachmark tour rendered at the App level (z-1000, `pointer-events-none` except the popup, so the user can perform each step while it's shown). Driven by `tutorial_enabled` (header checkbox) + `tutorial_step`.

Each step targets a `data-tour="..."` anchor and shows a glowing ring + arrow + popup; steps with a `view` switch the center workspace first; the position re-polls (200 ms interval + resize/scroll) so it survives view switches and async layout. A step whose anchor isn't on screen (e.g. `family-tree` before any run) shows a centered popup instead.

Anchors: `namelist` / `religion` / `culture` (LeftSidebar dropzones), `skip-title` / `add-dynasty` (GlobalSettings, view `global`), `generate` (LeftSidebar button), `family-tree` (nav item, post-run). To add a step, drop a `data-tour` attribute on the target and append to the `STEPS` array.
