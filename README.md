# CK3 Character History Generator

Procedural multi-generational character & title history generator for *Crusader
Kings III* total conversion mods. Implements spec **v7.0** (`Jis.pdf`) and
amendment **v2.0** (`Jis_Additional.pdf`) end-to-end.

## Architecture

| Layer    | Stack                                                      |
| -------- | ---------------------------------------------------------- |
| Frontend | React + Vite, Tailwind CSS (monochrome), Zustand state     |
| API      | FastAPI (file uploads, /generate, /status, /download)      |
| Worker   | Celery + Redis (long-running simulation off the request)   |
| Output   | Custom Paradox AST parser → simulation engine → ZIP bundle |

## Quick start

### Docker (recommended)

```bash
docker compose up --build
```

Open <http://localhost:5173>. Backend at <http://localhost:8000>.

### Local dev

Backend (Python 3.11+, Redis on `localhost:6379`):

```bash
cd backend
pip install -r requirements.txt
celery -A app.celery_app.celery_app worker --loglevel=info --pool=solo  # Windows
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

* **Ch. 1** — Cloud architecture: FastAPI dispatches to Celery worker via Redis
  broker; frontend polls `/status`; final ZIP at `/download/{task_id}`.
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
    celery_app.py    Celery config
    tasks.py         run_generation worker task
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
    components/
      LeftSidebar.jsx        Dropzones + nav + Generate button
      CenterWorkspace.jsx    View router
      RightDrawer.jsx        Polled task log + download
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
but not yet fully implemented in the simulation engine.
