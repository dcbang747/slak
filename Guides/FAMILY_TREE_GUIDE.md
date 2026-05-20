# CK3 Character History Generator — Family Tree (Graphviz) Guide

This document is the complete technical reference for the Graphviz family-tree
subsystem: what it reads, how it parses it, every visual distinction it makes,
every config option that controls its behaviour, how the output is named and
stored, and the known current limitations.

---

## Table of Contents

1. [Overview and Pipeline Position](#1-overview-and-pipeline-position)
2. [Data Sources](#2-data-sources)
3. [Parsing — Characters](#3-parsing--characters)
4. [Parsing — Title Holders](#4-parsing--title-holders)
5. [Year Conversion System](#5-year-conversion-system)
6. [Graph Construction](#6-graph-construction)
   - 6.1 [One Graph Per Dynasty](#61-one-graph-per-dynasty)
   - 6.2 [Graph-Level Attributes](#62-graph-level-attributes)
   - 6.3 [The Stats Node](#63-the-stats-node)
   - 6.4 [Character Nodes — Visual Encoding](#64-character-nodes--visual-encoding)
   - 6.5 [Node Label Content](#65-node-label-content)
   - 6.6 [Bastard Nodes](#66-bastard-nodes)
   - 6.7 [Numenorean Blood Tiers](#67-numenorean-blood-tiers)
   - 6.8 [Title Holder Nodes](#68-title-holder-nodes)
   - 6.9 [Parent → Child Edges](#69-parent--child-edges)
   - 6.10 [External Parent Nodes](#610-external-parent-nodes)
   - 6.11 [Marriage Edges](#611-marriage-edges)
7. [Rendering](#7-rendering)
8. [Configuration Options](#8-configuration-options)
9. [UI — DynastyTrees Tab](#9-ui--dynastytrees-tab)
10. [Known Limitations and Bugs](#10-known-limitations-and-bugs)
11. [Quick Visual Legend](#11-quick-visual-legend)

---

## 1. Overview and Pipeline Position

The family tree renderer is the **fourth and final stage** of the simulation
pipeline. It runs after all characters have been written to
`family_history.txt` and all title histories have been written to
`title_history.txt`. It is entirely read-only with respect to those files — it
re-parses them from scratch using its own independent regex parser and does not
use the live `Character` objects from the simulation.

```
Simulation runs
      ↓
export_characters() → family_history.txt
      ↓
TitleHistory → title_history.txt
      ↓
FamilyTree → Dynasty Preview/family_tree_<dynasty>.png  ← this subsystem
```

The entry point in `main.py`:

```python
tree = FamilyTree(str(character_file), str(title_file), config)
tree.build_trees()
tree.render_trees()
```

`FamilyTree` is also the standalone entry point at the bottom of
`family_tree.py` — it can be run directly against any pair of output files
without re-running the full simulation.

---

## 2. Data Sources

| Source | Used for |
|---|---|
| `Character and Title files/family_history.txt` | Character identities, parentage, dynasty, sex, bastard status, Numenorean tier, birth year, death year |
| `Character and Title files/title_history.txt` | Which characters held a title and for how long (start date, end date) |
| `config["initialization"]` | `treeGeneration` (layout direction), `spouseVisible` (whether external parents are shown) |

The `FamilyTree` class does not touch the config JSON files directly — it
receives the already-loaded config dict that was passed in from `main.py`.

---

## 3. Parsing — Characters

`load_characters(filename)` reads `family_history.txt` and populates:

- `self.characters` — dict keyed by character ID → character data dict
- `self.dynasties` — dict keyed by dynasty name → list of character IDs

**Regex used to find character blocks:**

```python
re.findall(
    r"(\w+) = \{\s*((?:[^{}]*|\{(?:[^{}]*|\{[^}]*\})*\})*)\s*\}",
    data, re.DOTALL
)
```

This matches `identifier = { ... }` blocks, handling one level of nested braces
(the `effect = { ... }` or `death = { ... }` blocks inside a date entry).

**Fields extracted for each character:**

| Field | Regex | Default | Notes |
|---|---|---|---|
| `id` | (the outer capture group) | — | e.g. `lineofDurin42` |
| `name` | `name\s*=\s*(\w+)` | `""` | |
| `father` | `father\s*=\s*(\w+)` | `None` | |
| `mother` | `mother\s*=\s*(\w+)` | `None` | |
| `dynasty` | `dynasty\s*=\s*(\w+)` | `"Lowborn"` | Reads `dynasty =` not `dynasty_house =` |
| `female` | `\bfemale\b\s*=\s*yes` | `"no"` | Boolean-as-string: `"yes"` or `"no"` |
| `is_bastard` | `\btrait\s*=\s*bastard\b` | `False` | Boolean |
| `numenor_tier` | `\btrait\s*=\s*blood_of_numenor_(\d+)\b` | `None` | Integer if present |
| `birth_year` | `(\d{4})\.\d{2}\.\d{2}\s*=\s*\{\s*birth\s*=\s*yes` | `""` | Stored as in-game year string |
| `death_year` | Iterates all `(\d{4})\.(\d{2})\.(\d{2}) = { ... }` blocks, picks first containing `\bdeath\b` | `""` | Stored as in-game year string |

**Important:** All year values stored in `self.characters` are the **in-game
year strings** (e.g. `"2767"`, not `"6800"`). The conversion from simulation
year to in-game year happens immediately during parsing. See
[Section 5](#5-year-conversion-system) for the conversion logic.

---

## 4. Parsing — Title Holders

`load_titles(filename)` reads `title_history.txt` and populates
`self.title_holders` — a dict mapping character ID → `{ "start_date": str, "end_date": str }`.

**Regex:**

```python
# Outer: find each placeholder_title block
re.findall(r"(\w+)\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", data, re.DOTALL)

# Inner: find each dated holder entry
re.findall(r"(\d{4}\.\d{2}\.\d{2})\s*=\s*\{[^}]*\bholder\s*=\s*(\w+)", content)
```

**Logic:**

The inner matches are iterated in document order (which is chronological, since
`write_title_histories_to_file` writes them that way). For each
`(date, holder_id)` pair:

1. If there was a previous holder who is different from the current holder, the
   previous holder's `end_date` is set to the current date.
2. The current holder is registered with the current date as their `start_date`
   (or updated if already present).
3. After all entries, the **last holder** in the block always has
   `end_date = "Present"`.

Holder ID `"0"` is explicitly skipped — it represents an empty title (no
holder) and is used as a separator in some title history formats.

**Multiple reigns:** If a character appears as holder more than once in the
same block, their `start_date` is overwritten with the most recent entry. This
means only the last reign period is preserved for a given character. This is
intentional for the expected case (each character rules once), but would lose
data if a character ruled, lost the title, and reclaimed it.

---

## 5. Year Conversion System

Both `load_characters` and `build_trees` define an identical local helper:

```python
def convert_to_ingame_date(year):
    if year.isdigit():
        year = int(year)
        if year > 4033:
            return f"{year - 4033}"
        elif 592 < year <= 4033:
            return f"{year - 592}"
    return ""
```

This converts the raw four-digit simulation year (which is an absolute calendar
value in the mod's timeline) to the displayed in-game era year:

| Simulation year range | Formula | Era |
|---|---|---|
| > 4033 | year − 4033 | Fourth Age (displayed as bare number, e.g. `"2767"`) |
| 593 – 4033 | year − 592 | Third Age (displayed as bare number, e.g. `"150"`) |
| ≤ 592 | no match → `""` | Falls through — returns empty string |

**Note:** The era prefix ("T.A.", "F.A.", "S.A.") is **not** written by the
family tree renderer. Only the bare number is displayed. The `title_history.py`
module has a separate `convert_to_ingame_date` that does write prefixes, but
the family tree module does not.

**Current config range (6800–7033):**
All years fall in the `> 4033` bracket: 6800 → 2767, 7033 → 3000. All
displayed years will be bare Fourth Age numbers in the 2767–3000 range.

**Age calculation:** Because both birth and death years are stored as the same
era's bare number, subtracting them gives the correct lifespan:

```python
if birth_date.isdigit() and death_date.isdigit():
    age = int(death_date) - int(birth_date)
    age_suffix = f" ({age})"
```

This only works correctly when birth and death are in the same era. A character
born in the Third Age who dies in the Fourth Age would show a wrong (negative)
age. With the current config this cannot occur since all years are well above
4033.

---

## 6. Graph Construction

### 6.1 One Graph Per Dynasty

`build_trees()` loops over `self.dynasties` — one `graphviz.Digraph` object is
created per dynasty. Lowborn characters (dynasty = `"Lowborn"`) are grouped into
their own graph alongside characters from other dynasties who happen to share the
Lowborn group. In practice, the simulation assigns Lowborn spouses to the dynasty
of their partner for export, so very few characters appear under `"Lowborn"` in
the output files.

---

### 6.2 Graph-Level Attributes

```python
graphviz.Digraph(
    comment=f"{dynasty} Family Tree",
    graph_attr={
        "rankdir": self.graphLook,   # from config
        "bgcolor": "#A0C878"         # fixed green background
    }
)
```

| Attribute | Value | Notes |
|---|---|---|
| `rankdir` | From `config["initialization"]["treeGeneration"]` | See [Section 8](#8-configuration-options) |
| `bgcolor` | `#A0C878` | Fixed sage-green background; not configurable |
| `comment` | `"{dynasty} Family Tree"` | Embedded in the DOT source; not visible in PNG |

---

### 6.3 The Stats Node

Each graph contains exactly one informational summary node positioned
separately from the character nodes:

```python
graph.node(
    "dynasty_count",
    label=count_label,
    shape="plaintext",
    width="0", height="0",
    style="solid", color="transparent", fontcolor="black"
)
```

The label contains:

```
Total Members: N
Males: N
Females: N
Rulers: N
```

- **Total Members:** count of all character IDs in this dynasty group
- **Males:** characters where `female != "yes"`
- **Females:** characters where `female == "yes"`
- **Rulers:** characters whose ID appears in `self.title_holders`

The node has `shape="plaintext"` (no border box), `color="transparent"` (no
border), and zero explicit size, so Graphviz sizes it to fit the text only.
`fontcolor="black"` ensures readability on the green background.

Note: `oldest_birth_year` and `youngest_birth_year` are computed in the same
section but are **not** included in the label — this is dead code left over from
an earlier version that displayed the dynasty's year span.

---

### 6.4 Character Nodes — Visual Encoding

Each character gets one node. The visual encoding uses four independent visual
channels:

#### Fill colour (background of node)

| Condition | Colour |
|---|---|
| Character appears in `self.title_holders` (held a title) | `pink` |
| All other characters | `white` |

#### Border colour

| Condition | Colour |
|---|---|
| Female (`female == "yes"`) | `red` |
| Male (default) | `blue` |

#### Border thickness

Fixed at `penwidth = "5"` for all character nodes. This is deliberately thick
to make the sex-colour distinction clearly visible.

#### Node style

`"filled"` for non-bastards; `"filled, diagonals"` for bastards. See
[Section 6.6](#66-bastard-nodes).

---

### 6.5 Node Label Content

Labels use Graphviz HTML-like syntax (enclosed in `< >`) to support bold text
and line breaks:

```
< <b>NAME</b><br/>
char_id<br/>
BIRTH - DEATH (AGE) (BLOOD_TIER)<br/>
Ruled: START - END >
```

**Line 1 — Name:** Character's given name in bold.

**Line 2 — ID:** The full character ID (e.g. `lineofDurin42`). Useful for
cross-referencing with `family_history.txt`.

**Line 3 — Dates and blood tier:**
- `birth_date`: in-game year string (bare number), or `""` if not found
- `death_date`: in-game year string, or `""` if not found
- `(AGE)`: only appended if **both** `birth_date` and `death_date` are non-empty
  digit strings; calculated as `int(death_date) - int(birth_date)`
- `(BLOOD_TIER)`: only appended if `numenor_tier` is non-null; displayed as a
  Roman numeral using the `ROMAN` dict (I through X for tiers 1–10)

**Line 4 — Reign dates:**
Only rendered if the character is a title holder **and** both `start_year` and
`end_year` convert to non-empty, non-"N/A" values. Format: `Ruled: START - END`.
The `"Present"` end date (for the last holder) is passed through
`convert_to_ingame_date()` which returns `""` for non-digit strings — so the
last holder's reign line will read `Ruled: N - ` with an empty end year rather
than `Ruled: N - Present`. This is a minor display gap.

---

### 6.6 Bastard Nodes

Bastard characters (those with `trait = bastard` in their character block) are
detected during parsing and flagged as `is_bastard = True`.

In `build_trees()` the node style for bastards is extended:

```python
node_style += ", diagonals"
```

The Graphviz `diagonals` shape style draws diagonal lines at each corner of the
node's rectangle — a standard heraldic visual shorthand for illegitimate birth.
The fill colour, border colour, and border thickness are otherwise identical to
a legitimate character of the same sex and ruler-status.

---

### 6.7 Numenorean Blood Tiers

The `ROMAN` class constant maps tiers to display strings:

```python
ROMAN = {
    1: "I",  2: "II",  3: "III",  4: "IV",  5: "V",
    6: "VI", 7: "VII", 8: "VIII", 9: "IX",  10: "X"
}
```

If `numenor_tier` is a value outside 1–10 (which cannot happen through normal
simulation but could occur in a manually edited file), `ROMAN.get(tier, str(tier))`
falls back to displaying the integer as a string.

The blood tier appears in the node label as ` (I)`, ` (II)`, etc., on the same
line as the birth and death years. There is no separate visual distinction for
tier level — tier 1 and tier 10 look identical except for the Roman numeral.

---

### 6.8 Title Holder Nodes

A character is considered a title holder if their character ID appears as a key
in `self.title_holders` (populated by `load_titles`). Being a title holder
triggers two changes:

1. **Node fill colour** changes from white → **pink**
2. **Reign dates** are added to the node label if both start and end are valid

Title holder status is per-dynasty-graph — if a character appears in a
`placeholder_title` block in `title_history.txt`, they are marked as a ruler in
every dynasty graph they appear in (though in practice a character belongs to
exactly one dynasty).

---

### 6.9 Parent → Child Edges

For each character, the parser checks both `father` and `mother` fields. For
each parent that exists in `self.characters`, the dynasty of that parent is
compared to the current graph's dynasty:

**Same dynasty → direct arrow:**

```python
graph.edge(parent_id, char_id)
```

A plain directed edge (arrow) from parent to child. Graphviz will route it
according to the `rankdir` layout. Default styling (no colour, no weight
override) — thin solid arrow.

**Different dynasty → external parent node (if `spouseVisible == "yes"`):**
See [Section 6.10](#610-external-parent-nodes).

**Different dynasty + `spouseVisible != "yes"` → edge omitted.** The cross-
dynasty parent is completely invisible in the default configuration. Children of
lowborn spouses will have one hanging edge (to the dynasty parent) and the
lowborn parent simply does not appear.

---

### 6.10 External Parent Nodes

Only rendered when `config["initialization"]["spouseVisible"] == "yes"`.

When a character's parent belongs to a different dynasty, an external node is
created (once per unique parent — duplicates are tracked in `external_nodes`):

```python
graph.node(
    f"external_{parent_id}",
    label=f'< <b>NAME</b><br/>BIRTH - DEATH >',
    shape="ellipse",
    style="dashed"
)
```

External nodes use:
- **Ellipse shape** (vs rectangle for dynasty members) — immediately visually
  distinguishable
- **Dashed style** — communicates "not a full member of this dynasty"
- **Minimal label** — only name, birth year, and death year (no ID, no ruled
  dates, no blood tier)

The edge from the external node to the child is also dashed:

```python
graph.edge(external_node_id, char_id, style="dashed")
```

Additionally, if the external parent has a `"spouse"` field in their character
data pointing to a character who exists in `self.characters`, a bold spouse edge
is drawn:

```python
graph.edge(external_node_id, spouse_id, style="bold", penwidth="3", color="black")
```

**Important:** this spouse-of-external-parent edge is subject to the same
marriage-detection limitation described in [Section 10](#10-known-limitations-and-bugs)
— `self.characters` does not store a `"spouse"` field for any character, so this
edge is also never rendered in practice.

---

### 6.11 Marriage Edges

After all character nodes and parent edges are drawn, the code attempts to draw
marriage lines:

```python
for spouse1, spouse2 in marriages.items():
    graph.edge(spouse1, spouse2, style="bold", penwidth="3", color="black")
    with graph.subgraph() as s:
        s.attr(rankdir=self.graphLook, rank='same')
        s.node(spouse1)
        s.node(spouse2)
        s.edge(spouse1, spouse2, style="bold", penwidth="3", color="black")
```

**Intended behaviour:** a bold black horizontal line connecting spouses, with a
`rank='same'` subgraph forcing Graphviz to place them side-by-side on the same
rank (row in TB layout, column in LR layout).

**Actual behaviour:** the `marriages` dict is always empty. See
[Section 10](#10-known-limitations-and-bugs).

---

## 7. Rendering

`render_trees()` iterates `self.graphs` and writes one PNG per dynasty:

```python
graph.render(filename, format="png", cleanup=True)
```

| Parameter | Value | Effect |
|---|---|---|
| `filename` | `TREE_OUTPUT_DIR / f"family_tree_{dynasty}"` | No extension — Graphviz appends `.png` |
| `format` | `"png"` | Always rasterised PNG; vector formats (SVG, PDF) not exposed |
| `cleanup=True` | Deletes the intermediate `.dot` source file after rendering | Only the `.png` is kept; raw DOT source is not preserved |

**Output location:**
- Dev mode: `Dynasty Preview/` at the project root
- Packaged app: `~/Documents/CK3 Character Generator/Dynasty Preview/`

**Output filenames:** `family_tree_dynasty_Durin.png`, `family_tree_dynasty_Gondor.png`, etc.
The dynasty portion is the raw `dynastyID` string including the `dynasty_` prefix.

**DynastyTrees tab strips the prefix for display:**

```typescript
const dynastyLabel = (filename: string) =>
  filename.replace("family_tree_", "").replace(".png", "");
```

So `family_tree_dynasty_Durin.png` is displayed in the UI as `dynasty_Durin`.

---

## 8. Configuration Options

Both options live in `config/initialization.json` under the top-level object
(not inside any dynasty entry).

---

### `treeGeneration`

Controls the Graphviz `rankdir` — the primary direction of the layout.

```json
"treeGeneration": "TB"
```

| Value | Meaning | Best for |
|---|---|---|
| `"TB"` | **Top → Bottom** (default) | Standard family tree feel; eldest ancestors at top, descendants below |
| `"BT"` | **Bottom → Top** | Inverted; descendants at top (unusual) |
| `"LR"` | **Left → Right** | Wide trees with many generations; time flows left to right |
| `"RL"` | **Right → Left** | Mirror of LR |

> **"Both" is documented in the source comment but not implemented.** The
> comment at the top of `family_tree.py` lists `"Both"` as a valid option that
> "will generate LR and TB both", but there is no code path that handles this
> value. Passing `"Both"` would send it directly to Graphviz as a `rankdir`
> attribute, which is invalid and will cause a rendering error.

**Layout implications:**
- `TB` and `BT`: generations form horizontal bands; wide dynasties produce very
  wide PNGs
- `LR` and `RL`: generations form vertical columns; long-running dynasties
  produce very tall PNGs
- The marriage subgraph (`rank='same'`) is also given `rankdir=self.graphLook` —
  this is somewhat redundant (subgraph rankdir doesn't override the root graph)
  but harmless

**Current config:** `"TB"` (Top to Bottom).

---

### `spouseVisible`

Controls whether parents from outside the dynasty are rendered as dashed ellipse
nodes.

```json
"spouseVisible": "no"
```

| Value | Effect |
|---|---|
| `"yes"` | External parents are shown as dashed ellipses with dashed edges to their children |
| `"no"` (or any other value) | External parents are invisible; cross-dynasty parent edges are silently dropped |

> **Important implementation detail:** the code reads this as:
> ```python
> self.config.get('initialization', {}).get('spouseVisible', []) == "yes"
> ```
> The default value is `[]` (an empty list), not `"no"`. Since `[] != "yes"`,
> the default behaviour is always to hide external parents, even if the key is
> missing from the config entirely.

**Current config:** `"no"` — external parents are not shown.

**When to use `"yes"`:** Useful when you want to see which outside dynasty a
spouse came from, or to trace matrilineal lines in agnatic dynasties. Warning:
enabling this on large simulations with many intermarriages can produce very
cluttered trees.

---

## 9. UI — DynastyTrees Tab

The **Dynasty Trees** tab in the GUI (`DynastyTrees.tsx`) is a simple image
browser layered on top of the API's image endpoints.

**On mount**, it calls `GET /images` which returns a sorted list of filenames
from `TREE_OUTPUT_DIR`:

```python
@app.get("/images")
def list_images() -> list[str]:
    if not TREE_OUTPUT_DIR.exists(): return []
    return sorted(p.name for p in TREE_OUTPUT_DIR.glob("family_tree_*.png"))
```

Only files matching `family_tree_*.png` are listed — other files in the
directory are ignored.

**Each image** is shown in an accordion row. The row header displays the dynasty
name (filename with `family_tree_` prefix and `.png` suffix stripped). Clicking
the header toggles the image open or closed.

**The image** is loaded via `GET /images/{filename}` which serves the file with
`media_type="image/png"`. Images use `loading="lazy"` so the browser defers
loading until the accordion is expanded.

**Refresh button:** calls `GET /images` again and updates the list. This is
necessary after running a new simulation — the tab does not auto-refresh.

**No zoom or pan controls are provided in the UI.** For large trees, the user
must either open the PNG file directly, or rely on browser-level zoom (Ctrl+scroll
in most browsers when the image is expanded).

---

## 10. Known Limitations and Bugs

### 10.1 Marriage Lines Are Never Drawn

The most significant limitation. The marriage detection code does:

```python
spouse_id = self.characters.get(char_id, {}).get("spouse")
```

But the `load_characters()` method **never parses a `"spouse"` field** from
`family_history.txt` — the character data dict only contains `id`, `name`,
`father`, `mother`, `dynasty`, `female`, `is_bastard`, `numenor_tier`,
`birth_year`, and `death_year`. The `"spouse"` key does not exist.

`spouse_id` is therefore always `None`, the `marriages` dict is always empty,
and no marriage lines (bold black edges) are ever rendered. Spouses will appear
as unconnected sibling nodes unless they share a parent → child edge.

**To fix this:** `load_characters` would need to parse the `add_spouse` or
`add_matrilineal_spouse` events from each character's date blocks. The event
format is `YYYY.MM.DD = { add_spouse = OTHER_CHAR_ID }`, so the regex would be
something like `r"add_(?:matrilineal_)?spouse\s*=\s*(\w+)"`.

---

### 10.2 Last Title Holder's Reign End Displays as Empty

In `build_trees()`, the `end_date` for the last title holder is `"Present"` (a
literal string set by `load_titles`). When passed to `convert_to_ingame_date()`,
`"Present"` fails the `.isdigit()` check and returns `""`. The ruled label
condition checks `if end_year and end_year != "N/A"` — an empty string is falsy,
so the entire ruled label is suppressed for the last holder.

The last holder thus shows **no reign dates at all** in their node label despite
being a pink (ruler) node. They look visually identical to a ruler whose reign
dates simply weren't found.

**To fix:** treat `"Present"` as a special case: `end_year = "Present"` if
`end_date == "Present"`.

---

### 10.3 `dynasty_house` Characters Are Not Grouped Correctly

The `load_characters` parser uses the regex `dynasty\s*=\s*(\w+)` to find the
dynasty field. Characters belonging to a `dynasty_house` (i.e. cadet branches
with `isHouse: true`) are written to `family_history.txt` with
`dynasty_house = X` not `dynasty = X`. The regex only matches `dynasty =`, so
these characters will have `dynasty = "Lowborn"` in the tree and will appear in
the Lowborn graph instead of their actual house's graph.

**To fix:** add a separate match for `dynasty_house\s*=\s*(\w+)` in
`load_characters`, using it as a fallback when `dynasty =` is absent.

---

### 10.4 Birth Year Sort Is String-Lexicographic, Not Numeric

```python
sorted_members = sorted(members, key=lambda char_id: self.characters[char_id]["birth_year"])
```

`birth_year` is stored as a string (the output of `convert_to_ingame_date`).
Python's default string sort is lexicographic, not numeric. For numbers with the
same number of digits this is harmless (e.g. `"100"` < `"200"`), but a four-
digit year will always sort after a three-digit year (`"999"` < `"1000"`), so a
character born in year 999 (T.A.) would be sorted after a character born in year
1000 (T.A.), which is correct. However, a character with `birth_year = ""` (not
found during parsing) would sort before all others (empty string sorts first).

**To fix:** convert to int before sorting, with a fallback of 0 for empty strings:
`key=lambda char_id: int(self.characters[char_id]["birth_year"] or 0)`.

---

### 10.5 Oldest/Youngest Birth Years Are Dead Code

The `build_trees` method computes:

```python
birth_years = [self.characters[char_id]["birth_year"] for char_id in members]
oldest_birth_year  = min(birth_years)
youngest_birth_year = max(birth_years)
oldest_in_game_year  = convert_to_ingame_date(str(oldest_birth_year))
youngest_in_game_year = convert_to_ingame_date(str(youngest_birth_year))
```

Neither `oldest_in_game_year` nor `youngest_in_game_year` is used anywhere after
this. They were presumably intended for the stats node label (which currently only
shows member/sex/ruler counts) but were never wired in. Additionally,
`min`/`max` here inherits the string-comparison issue from 10.4.

---

### 10.6 "Both" Direction Not Implemented

The comment block at the top of `family_tree.py` documents `"Both"` as a valid
`treeGeneration` value that generates two PNGs (LR and TB). No code implements
this. Setting `"treeGeneration": "Both"` would pass `rankdir="Both"` to
Graphviz, which would likely produce a rendering error or a malformed graph.

---

### 10.7 Adoption Parentage Is Not Visible

Adopted characters (`is_adopted = True`) have their parentage written via
`set_father` / `set_mother` inside an `effect = { }` block in the export format,
not via top-level `father =` / `mother =` fields. The `load_characters` parser
only reads the top-level `father\s*=\s*(\w+)` pattern, so adopted characters
will appear with `father = None` and `mother = None` in the tree — floating
with no parent edges even though they have an adoptive parent.

---

## 11. Quick Visual Legend

| Visual property | Meaning |
|---|---|
| **Blue border** | Male character |
| **Red border** | Female character |
| **White fill** | Non-ruler |
| **Pink fill** | Title holder (ruled at some point) |
| **Thick border** (penwidth 5) | Applied to all characters |
| **Diagonal corner marks** | Bastard (illegitimate) |
| `(I)` … `(X)` in label | Numenorean blood tier (Roman numeral) |
| `Ruled: N - M` in label | Approximate reign years (in-game era format) |
| **Dashed ellipse node** | External parent from another dynasty (only if `spouseVisible = "yes"`) |
| **Dashed edge** | Parent → child link crossing dynasty boundaries |
| **Bold black edge** | Marriage line — *currently never rendered* (see §10.1) |
| **Plain arrow** | Parent → child within the same dynasty |
| **Green background** (`#A0C878`) | Fixed graph background colour |
| **Stats node** (top-left, no border) | Dynasty summary: total members, males, females, rulers |
