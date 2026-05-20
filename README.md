# CK3 Character History Generator

Procedural multi-generational character & title history generator for *Crusader
Kings III* total conversion mods. Implements spec **v7.0** (`Jis.pdf`) and
amendment **v2.0** (`Jis_Additional.pdf`) end-to-end.

## Architecture

| Layer    | Stack                                                      |
| -------- | ---------------------------------------------------------- |
| Frontend | React + Vite, Tailwind CSS (monochrome), Zustand state     |
| API      | FastAPI (file uploads + a single synchronous `/generate`)  |
| Generation | Synchronous, in-request (`generation.py`) — stateless; one call returns stats + family tree + base64 ZIP |
| Output   | Custom Paradox AST parser → simulation engine → ZIP bundle |

## Quick start

### Docker (recommended)

```bash
docker compose up --build
```

Open <http://localhost:5173>. Backend at <http://localhost:8000>.

### Local dev

Backend (Python 3.11+ — no Redis/worker needed):

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Trying it out

`RawSampleFiles/` contains real LotR CK3 mod files for manual testing:

* `TitleHistory/` — title holder sequences for empires and kingdoms
* `TraitFiles/` — genetic trait definitions (beauty, health, courage groups)
* `DeathReasonFiles/` — natural + hostile + trait-triggered death reasons
* `NameListFiles/` — culture-specific name pools (Rohirrim, Tedjin, Dunedain, etc.)
* `Religions/` — religion and faith definitions with marital doctrines
* `Dynasties/` — example dynasty definitions (reference only — dynasties are now configured via the UI)

Upload files into the sidebar dropzones, define your dynasties in the Global
Settings panel, assign them to titles on the Title Histories Gantt chart, then
click **Generate Simulation**. The right drawer streams worker progress; the
download button delivers a ZIP with `character_history.txt`,
`title_history.txt`, `00_dynasties.txt`, `dynasty_names_l_english.yml`, and
`dynasty_mottos_l_english.yml` in exact CK3 Paradox script syntax.

Minimum required to enable the Generate button: **Title History + Name Lists**.

## Spec coverage

* **Ch. 1** — FastAPI runs generation synchronously (`generation.py`) and returns
  stats + family tree + the ZIP (base64) in one `/generate` response. Stateless.
* **Ch. 2** — Three-column SPA: left sidebar (dropzones + nav + Generate),
  center contextual editor, right drawer with mock terminal log. Strict
  monochrome Tailwind palette.
* **Ch. 3** — Single Zustand store (`src/store.js`) with the exact categories
  from the spec; serialized to JSON at submission time. `onChange` drives state
  directly without per-field save buttons.
* **Ch. 4** — Pydantic schemas in `backend/app/schemas.py` (Character, DynastyDefinition, etc.).
* **Ch. 5** — AST compiler (`backend/app/parser.py`):
  * Comment stripping, brace/equals padding, quote-preserving split.
  * Recursive parser with state stack.
  * Duplicate-key edge case → list collapse.
  * Title hierarchy classifier honoring `h_/e_/k_/d_/c_/b_` prefixes.
  * Hegemony titular-vs-landed dynamic classification.
  * `metadata` bundling for non-title keys.
  * Trait filter (`genetic = yes` only); `natural_death_trigger.has_trait` extraction.
* **Ch. 6** — Genetics engine: parent trait evaluation w/ opposites cancellation,
  active inheritance (80%/20%), passive (50%/10%), spontaneous mutation against
  `random_creation`. Mortality: exponential age curve with hardcoded trait/age death reasons.
* **Ch. 7** — Title transitions:
  * Marriage: forced heir + spouse from House B; child forced into House B.
  * Usurpation: hostile death w/ `killer_id`; family displacement via `employer_id`.
  * Extinction: fertility forced to 0; incoming house founder created fresh.
  * **Cascading inheritance**: high-tier sequences propagate to children unless
    explicitly overridden (`cascade_sequences()`).
* **Ch. 8** — Interactive Gantt chart: y-axis title hierarchy with collapse,
  x-axis scrollable years, draggable resize handles on dynasty blocks, clickable
  transition-boundary nodes opening a transition-type popover.
* **Ch. 9** — Output formatter (`backend/app/output.py`) emits:
  * `character_history.txt` — conditional `female`/`killer`/`employer` blocks; dated relationship + secret effect blocks when enabled
  * `title_history.txt` — sequential `YYYY.M.D = { holder = ... }` entries
  * `00_dynasties.txt` — Paradox dynasty definitions with real culture + optional motto
  * `dynasty_names_l_english.yml` / `dynasty_mottos_l_english.yml` — UTF-8 BOM localization, names and mottos split into two files
* **Jis_Additional v2.0** — Dynasty definitions panel (culture/faith periods,
  succession type, gender preference, lowborn spouses, guaranteed survival);
  `dynasty_definitions` top-level payload field.

## Repo layout

```
backend/
  app/
    main.py          FastAPI endpoints
    generation.py    Synchronous run_generation() → stats + tree + base64 ZIP
    parser.py        Paradox AST compiler (ch. 5)
    schemas.py       Pydantic models (ch. 4)
    genetics.py      Inheritance algorithm (ch. 6.1)
    mortality.py     Death-roll & reason picker (ch. 6.2)
    simulation.py    Year tick loop + transitions (ch. 7)
    output.py        Paradox-script writer (ch. 9)
frontend/
  src/
    App.jsx
    store.js                 Zustand single source of truth
    api.js                   Backend client
    yearConvert.js           In-game era year conversion helpers
    components/
      LeftSidebar.jsx        Dropzones + nav + Generate button + Tutorial toggle
      CenterWorkspace.jsx    View router
      RightDrawer.jsx        Polled task log + download
      TutorialOverlay.jsx    Onboarding coachmark tour
      Dropzone.jsx
      GanttChart.jsx         Interactive Gantt for title sequences
      views/
        GlobalSettings.jsx   Simulation settings + Dynasties panel (two-column)
        LifeCycleModifiers.jsx
        TitleHistories.jsx
        FamilyTree.jsx       React Flow family tree (post-run)
RawSampleFiles/
  TitleHistory/    CharacterHistory/  TraitFiles/  DeathReasonFiles/
  NameListFiles/   Dynasties/         Religions/   Secrets/  TitleFiles/
docker-compose.yml
Jis.pdf             v7.0 spec
Jis_Additional.pdf  amendment v2.0
```

## Explicitly omitted (per spec mandate)

Culling mechanics, dynamic nicknames, 3D DNA strings.

Cadet branches, secrets, and relationships are **in scope** via `Jis_Additional.pdf`
and implemented (secrets + relationships are rolled when their Global Settings flags are on).

## Deployment

The whole app deploys to **Vercel as one project** — the Vite SPA as static output
plus the FastAPI backend as a Python serverless function (`api/index.py`), since
generation is now stateless and synchronous. No separate backend host, no database.

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for the full walkthrough (Vercel project
setup, the `vercel.json` build + `/api` rewrite, custom domain on 1-grid, and the
serverless caveats — execution time limit, response size, cold starts).
