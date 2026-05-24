// Zustand global state — sole source of truth (spec ch. 3).
// Serialized into JSON and POSTed to /generate when the user clicks
// "Generate Simulation".

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

// ---------------------------------------------------------------------------
// Personality traits default config (mirrors schemas.py _default_personality_traits)
// ---------------------------------------------------------------------------

function _defaultPersonalityTraits() {
  const pairs = [
    ['brave', 'craven'], ['calm', 'wrathful'], ['chaste', 'lustful'],
    ['content', 'ambitious'], ['diligent', 'lazy'], ['forgiving', 'vengeful'],
    ['generous', 'greedy'], ['gregarious', 'shy'], ['honest', 'deceitful'],
    ['humble', 'arrogant'], ['just', 'arbitrary'], ['patient', 'impatient'],
    ['temperate', 'gluttonous'], ['trusting', 'paranoid'], ['zealous', 'cynical'],
  ];
  const traits = {};
  for (const [a, b] of pairs) {
    traits[a] = { weight: 1.0, excludes: [b] };
    traits[b] = { weight: 1.0, excludes: [a] };
  }
  for (const t of ['compassionate', 'callous', 'sadistic']) {
    traits[t] = { weight: 1.0, excludes: ['compassionate', 'callous', 'sadistic'].filter(x => x !== t) };
  }
  for (const t of ['fickle', 'stubborn', 'eccentric']) {
    traits[t] = { weight: 1.0, excludes: ['fickle', 'stubborn', 'eccentric'].filter(x => x !== t) };
  }
  return traits;
}

function _defaultDynasty(globalSettings) {
  return {
    id: `dynasty_new_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    name: 'New Dynasty',
    motto: '',
    start_year: globalSettings.start_year,
    end_year: globalSettings.end_year,
    culture_faith_periods: [
      { start_year: globalSettings.start_year, culture: '', faith: '' },
    ],
    gender_law: 'AGNATIC_COGNATIC',
    succession: 'PRIMOGENITURE',
    lowborn_spouses: false,
    guaranteed_survival: false,
    name_inheritance: {
      grandparent_chance: 0.05,
      parent_chance: 0.05,
      no_name_chance: 0.90,
    },
    languages: [],
  };
}

function _defaultGlobalSettings() {
  return {
    start_year: 6800,
    end_year: 7000,
    maximum_generations: 30,
    trait_frequency_multiplier: 1.0,
    ignore_title_generation: false,
    enable_secrets: false,
    enable_relationships: false,
    enable_nicknames: true,
    personality_traits: {
      total_traits_per_character: 3,
      traits: _defaultPersonalityTraits(),
    },
  };
}

function _defaultLifeCycle() {
  return {
    max_age_difference_between_partners: 20,
    max_children_per_couple: 3,
    base_fertility_rate: 0.35,
    male_bastard_chance: 0.05,
    female_bastard_chance: 0.02,
    dynasty_soft_cap: 50,
    average_lifespan: 70,
    average_marriage_age: 22,
    gap_between_children: 2,
  };
}

// Defaults for "Jamie's Handy Character History Generator" (the linear mode).
// Mirrors backend JamieSettings; culture/faith/names are supplied from uploads.
function _defaultJamie() {
  return {
    dynasty_id: 'dynasty_new',
    faith_id: '',
    culture_id: '',
    char_id_string: 'myline',
    initial_char_id: 1,
    start_birth_year: 6897,
    title_id: '',
    generations: 4,
    generation_siblings: 3,
    marriage_min_age: 16,
    marriage_max_age: 35,
    agediff_min: -3,
    agediff_max: 3,
    childbirth_min_age: 20,
    childbirth_max_age: 40,
    children_max: 5,
    battle_death_chance: 0.1,
    battle_death_min_age: 20,
    battle_death_max_age: 65,
    ill_death_chance: 0.1,
    ill_death_min_age: 25,
    ill_death_max_age: 65,
    intrigue_death_chance: 0.05,
    intrigue_death_min_age: 25,
    intrigue_death_max_age: 65,
    old_death_min_age: 60,
    old_death_max_age: 85,
    dominant_sex: 'MALE',
    option_male_line: false,
    option_sexuality: true,
    option_nicknames: true,
    option_personality_traits: true,
    option_skills: true,
    option_education: true,
    option_heroes: true,
    option_loc_keys: false,
    hero_chance: 0.01,
    hero_buff_min: 5,
    hero_buff_max: 10,
  };
}

function _defaultParsedFiles() {
  return {
    titles_txt: null,
    traits_txt: null,
    deaths_txt: null,
    name_lists: {},
    religions_txt: null,
    secrets_txt: null,
    // UI-only previews
    titles: [],             // flat list of title IDs from title history upload
    title_holder_events: {},// { titleId: [{date, year, vacant}] } from uploaded title history — drives locked periods + gap detection
    traits: [],             // genetic trait registry
    deaths: [],             // death reasons
    religions: {},          // { faith_id: marital_doctrine }
    secret_ids: [],         // list of secret type ID strings
    cultures: {},           // { culture_id: name_list_id }
    titles_filename: null,
    traits_filenames: [],
    deaths_filenames: [],
    names_filenames: [],
    religions_filenames: [],
    secrets_filenames: [],
    cultures_filenames: [],
  };
}

export const useStore = create(persist((set, get) => ({
  // Spec 3.1 — Global Settings
  global_settings: _defaultGlobalSettings(),

  // Life Cycle Modifiers
  life_cycle: _defaultLifeCycle(),

  // Parsed File Data — populated as the user drops files
  parsed_files: _defaultParsedFiles(),

  // Title Sequences — keyed by title id, value = ordered array of dynasty blocks
  title_sequences: {},

  // User-defined dynasty definitions (Jis_Revised_2)
  dynasty_definitions: [],

  // Per-gap dynasty assignments for uploaded titles with existing history.
  // { [titleId]: [{ gap_start_year, gap_end_year, dynasty_id }] }
  title_gap_fills: {},

  // Which generator is active. 'simulation' = the main timeline engine;
  // 'jamie' = the linear single-dynasty port of Jamie's Handy Character Generator.
  app_mode: 'simulation',
  jamie_settings: _defaultJamie(),

  // UI navigation
  active_view: 'global',  // 'global' | 'lifecycle' | 'titles' | 'tree'
  drawer_open: false,
  simplified_mode: true,
  // Default to dark mode; only light if the user has explicitly chosen it before.
  dark_mode: localStorage.getItem('ck3_dark_mode') !== 'false',

  // Onboarding tutorial — `tutorial_enabled` is the master switch (persisted,
  // toggled by the header checkbox); `tutorial_step` is the current coachmark.
  tutorial_enabled: true,
  tutorial_step: 0,

  // Simulation status. Generation is one synchronous request, so task_state is
  // just 'RUNNING' | 'SUCCESS' | 'FAILURE'; download_url is an object URL built
  // from the base64 ZIP returned by /generate.
  task_state: null,
  task_result: null,
  task_error: null,
  tree_data: null,
  download_url: null,

  // ----- Setters -----
  setGlobal: (patch) => set((s) => ({ global_settings: { ...s.global_settings, ...patch } })),
  setLifeCycle: (patch) => set((s) => ({ life_cycle: { ...s.life_cycle, ...patch } })),

  // Deep-patch personality_traits config inside global_settings
  setPersonalityTraitsConfig: (patch) => set((s) => ({
    global_settings: {
      ...s.global_settings,
      personality_traits: { ...s.global_settings.personality_traits, ...patch },
    },
  })),
  setPersonalityTraitWeight: (traitName, weight) => set((s) => ({
    global_settings: {
      ...s.global_settings,
      personality_traits: {
        ...s.global_settings.personality_traits,
        traits: {
          ...s.global_settings.personality_traits.traits,
          [traitName]: { ...s.global_settings.personality_traits.traits[traitName], weight },
        },
      },
    },
  })),

  setParsedTitles: (data) => set((s) => ({
    parsed_files: {
      ...s.parsed_files,
      titles_txt: data.raw,
      titles: data.title_ids,
      title_holder_events: data.holder_events || {},
      titles_filename: data.filename,
    },
  })),
  clearParsedTitles: () => set((s) => ({
    parsed_files: { ...s.parsed_files, titles_txt: null, titles: [], title_holder_events: {}, titles_filename: null },
    title_gap_fills: {},
  })),
  setParsedTraits: (data) => set((s) => ({
    parsed_files: {
      ...s.parsed_files,
      traits_txt: s.parsed_files.traits_txt ? s.parsed_files.traits_txt + '\n' + data.raw : data.raw,
      traits: [...new Set([...s.parsed_files.traits, ...data.traits])],
      traits_filenames: [...s.parsed_files.traits_filenames, data.filename],
    },
  })),
  clearParsedTraits: () => set((s) => ({
    parsed_files: { ...s.parsed_files, traits_txt: null, traits: [], traits_filenames: [] },
  })),

  setParsedDeaths: (data) => set((s) => ({
    parsed_files: {
      ...s.parsed_files,
      deaths_txt: s.parsed_files.deaths_txt ? s.parsed_files.deaths_txt + '\n' + data.raw : data.raw,
      deaths: [...new Set([...s.parsed_files.deaths, ...data.deaths])],
      deaths_filenames: [...s.parsed_files.deaths_filenames, data.filename],
    },
  })),
  clearParsedDeaths: () => set((s) => ({
    parsed_files: { ...s.parsed_files, deaths_txt: null, deaths: [], deaths_filenames: [] },
  })),

  setParsedNames: (data) => set((s) => {
    const merged = { ...s.parsed_files.name_lists };
    for (const [key, names] of Object.entries(data.name_lists)) {
      merged[key] = [...new Set([...(merged[key] || []), ...names])];
    }
    return {
      parsed_files: {
        ...s.parsed_files,
        name_lists: merged,
        names_filenames: [...s.parsed_files.names_filenames, data.filename],
      },
    };
  }),
  clearParsedNames: () => set((s) => ({
    parsed_files: { ...s.parsed_files, name_lists: {}, names_filenames: [] },
  })),

  setParsedReligions: (data) => set((s) => ({
    parsed_files: {
      ...s.parsed_files,
      religions_txt: s.parsed_files.religions_txt ? s.parsed_files.religions_txt + '\n' + data.raw : data.raw,
      religions: { ...s.parsed_files.religions, ...data.religions },
      religions_filenames: [...s.parsed_files.religions_filenames, data.filename],
    },
  })),
  clearParsedReligions: () => set((s) => ({
    parsed_files: { ...s.parsed_files, religions_txt: null, religions: {}, religions_filenames: [] },
  })),

  setParsedSecrets: (data) => set((s) => ({
    parsed_files: {
      ...s.parsed_files,
      secrets_txt: s.parsed_files.secrets_txt ? s.parsed_files.secrets_txt + '\n' + data.raw : data.raw,
      secret_ids: [...new Set([...s.parsed_files.secret_ids, ...data.secret_ids])],
      secrets_filenames: [...s.parsed_files.secrets_filenames, data.filename],
    },
  })),
  clearParsedSecrets: () => set((s) => ({
    parsed_files: { ...s.parsed_files, secrets_txt: null, secret_ids: [], secrets_filenames: [] },
  })),

  setParsedCultures: (data) => set((s) => ({
    parsed_files: {
      ...s.parsed_files,
      cultures: { ...s.parsed_files.cultures, ...data.cultures },
      cultures_filenames: [...s.parsed_files.cultures_filenames, data.filename],
    },
  })),
  clearParsedCultures: () => set((s) => ({
    parsed_files: { ...s.parsed_files, cultures: {}, cultures_filenames: [] },
  })),

  setSequences: (titleId, sequences) => set((s) => ({
    title_sequences: { ...s.title_sequences, [titleId]: sequences },
  })),

  // Assign an ordered list of dynasties to a specific gap of a title's existing
  // history (gaps >100yr may have several, ruling in sequence). Gaps are keyed by
  // their start/end years. An empty list clears the gap.
  setTitleGapFillDynasties: (titleId, gapStart, gapEnd, dynastyIds) => set((s) => {
    const ids = (dynastyIds || []).filter(Boolean);
    const others = (s.title_gap_fills[titleId] || []).filter(
      (g) => !(g.gap_start_year === gapStart && g.gap_end_year === gapEnd)
    );
    const next = ids.length
      ? [...others, { gap_start_year: gapStart, gap_end_year: gapEnd, dynasty_ids: ids }]
      : others;
    const out = { ...s.title_gap_fills };
    if (next.length) out[titleId] = next; else delete out[titleId];
    return { title_gap_fills: out };
  }),

  reorderBlock: (titleId, fromIdx, toIdx) => set((s) => {
    if (fromIdx === toIdx) return s;
    const seqs = [...(s.title_sequences[titleId] || [])];
    if (fromIdx < 0 || fromIdx >= seqs.length || toIdx < 0 || toIdx >= seqs.length) return s;
    const item = seqs[fromIdx];
    seqs.splice(fromIdx, 1);
    seqs.splice(toIdx > fromIdx ? toIdx - 1 : toIdx, 0, item);
    return { title_sequences: { ...s.title_sequences, [titleId]: seqs } };
  }),

  moveBlockToTitle: (fromTitleId, fromIdx, toTitleId, toIdx) => set((s) => {
    if (fromTitleId === toTitleId) return s;
    const fromSeqs = [...(s.title_sequences[fromTitleId] || [])];
    if (fromIdx < 0 || fromIdx >= fromSeqs.length) return s;
    const item = fromSeqs[fromIdx];
    fromSeqs.splice(fromIdx, 1);
    const toSeqs = [...(s.title_sequences[toTitleId] || [])];
    const insertAt = Math.max(0, Math.min(toIdx, toSeqs.length));
    toSeqs.splice(insertAt, 0, item);
    return {
      title_sequences: {
        ...s.title_sequences,
        [fromTitleId]: fromSeqs,
        [toTitleId]: toSeqs,
      },
    };
  }),

  addDynastyDef: () => set((s) => ({
    dynasty_definitions: [
      ...s.dynasty_definitions,
      _defaultDynasty(s.global_settings),
    ],
  })),
  updateDynastyDef: (id, patch) => set((s) => {
    const newId = 'id' in patch ? patch.id : id;
    let title_sequences = s.title_sequences;
    if (newId !== id) {
      const updated = {};
      for (const [titleId, seqs] of Object.entries(title_sequences)) {
        updated[titleId] = seqs.map((seq) =>
          seq.dynasty_id === id ? { ...seq, dynasty_id: newId } : seq
        );
      }
      title_sequences = updated;
    }
    return {
      dynasty_definitions: s.dynasty_definitions.map((d) => d.id === id ? { ...d, ...patch } : d),
      title_sequences,
    };
  }),
  removeDynastyDef: (id) => set((s) => ({
    dynasty_definitions: s.dynasty_definitions.filter((d) => d.id !== id),
  })),

  addCultureFaithPeriod: (dynId) => set((s) => ({
    dynasty_definitions: s.dynasty_definitions.map((d) =>
      d.id === dynId
        ? { ...d, culture_faith_periods: [...d.culture_faith_periods, { start_year: s.global_settings.start_year, culture: '', faith: '' }] }
        : d
    ),
  })),
  removeCultureFaithPeriod: (dynId, idx) => set((s) => ({
    dynasty_definitions: s.dynasty_definitions.map((d) =>
      d.id === dynId
        ? { ...d, culture_faith_periods: d.culture_faith_periods.filter((_, i) => i !== idx) }
        : d
    ),
  })),
  updateCultureFaithPeriod: (dynId, idx, patch) => set((s) => ({
    dynasty_definitions: s.dynasty_definitions.map((d) =>
      d.id === dynId
        ? {
            ...d,
            culture_faith_periods: d.culture_faith_periods.map((p, i) =>
              i === idx ? { ...p, ...patch } : p
            ),
          }
        : d
    ),
  })),

  updateDynastyNameInheritance: (dynId, patch) => set((s) => ({
    dynasty_definitions: s.dynasty_definitions.map((d) =>
      d.id === dynId
        ? { ...d, name_inheritance: { ...d.name_inheritance, ...patch } }
        : d
    ),
  })),

  addDynastyLanguage: (dynId) => set((s) => ({
    dynasty_definitions: s.dynasty_definitions.map((d) =>
      d.id === dynId
        ? { ...d, languages: [...d.languages, { id: '', start_year: s.global_settings.start_year, end_year: s.global_settings.end_year }] }
        : d
    ),
  })),
  updateDynastyLanguage: (dynId, idx, patch) => set((s) => ({
    dynasty_definitions: s.dynasty_definitions.map((d) =>
      d.id === dynId
        ? {
            ...d,
            languages: d.languages.map((l, i) => i === idx ? { ...l, ...patch } : l),
          }
        : d
    ),
  })),
  removeDynastyLanguage: (dynId, idx) => set((s) => ({
    dynasty_definitions: s.dynasty_definitions.map((d) =>
      d.id === dynId
        ? { ...d, languages: d.languages.filter((_, i) => i !== idx) }
        : d
    ),
  })),

  setDarkMode: (val) => {
    localStorage.setItem('ck3_dark_mode', val);
    set({ dark_mode: val });
  },

  setSimplified: (val) => set((s) => ({
    simplified_mode: val,
    active_view: val && s.active_view === 'lifecycle' ? 'global' : s.active_view,
  })),

  setView: (view) => set({ active_view: view }),
  setDrawer: (open) => set({ drawer_open: open }),

  // Switch generator mode; reset the active view to that mode's landing tab so the
  // center pane never shows a tab the other mode doesn't have.
  setAppMode: (mode) => set({ app_mode: mode, active_view: mode === 'jamie' ? 'jamie' : 'global' }),
  setJamie: (patch) => set((s) => ({ jamie_settings: { ...s.jamie_settings, ...patch } })),

  // Tutorial: enabling (re)starts at step 0; disabling dismisses it.
  setTutorialEnabled: (val) => set({ tutorial_enabled: val, tutorial_step: 0 }),
  setTutorialStep: (n) => set({ tutorial_step: n }),

  setTaskState: (patch) => set((s) => ({
    task_state: patch.task_state ?? s.task_state,
    task_result: patch.task_result ?? s.task_result,
    task_error: patch.task_error ?? s.task_error,
  })),
  // Store the full result of a synchronous generation in one shot.
  setGenerationResult: ({ characters, titles_with_history, family_tree, download_url }) => set({
    task_state: 'SUCCESS',
    task_result: { characters, titles_with_history },
    tree_data: family_tree,
    download_url,
    task_error: null,
  }),
  resetTask: () => set((s) => {
    if (s.download_url) URL.revokeObjectURL(s.download_url);
    return { task_state: null, task_result: null, task_error: null, tree_data: null, download_url: null };
  }),
  setTreeData: (data) => set({ tree_data: data }),

  // Clear all uploaded files, dynasties, sequences, and settings back to defaults.
  resetAll: () => set({
    global_settings: _defaultGlobalSettings(),
    life_cycle: _defaultLifeCycle(),
    parsed_files: _defaultParsedFiles(),
    title_sequences: {},
    title_gap_fills: {},
    dynasty_definitions: [],
    jamie_settings: _defaultJamie(),
    task_state: null, task_result: null, task_error: null, tree_data: null, download_url: null,
  }),

  // Build the JSON payload for /generate
  buildPayload: () => {
    const s = get();
    return {
      global_settings: {
        ...s.global_settings,
        random_seed: Math.floor(Math.random() * 2147483647),
      },
      life_cycle: s.life_cycle,
      parsed_files: {
        titles_txt: s.parsed_files.titles_txt,
        traits_txt: s.parsed_files.traits_txt,
        deaths_txt: s.parsed_files.deaths_txt,
        name_lists: s.parsed_files.name_lists,
        religions_txt: s.parsed_files.religions_txt,
        secrets_txt: s.parsed_files.secrets_txt,
      },
      title_sequences: s.title_sequences,
      title_gap_fills: s.title_gap_fills,
      // Serialize dynasty languages from object form [{id,start_year,end_year}] to "id,start,end" strings
      // Apply culture/faith fallbacks when fields are left blank
      dynasty_definitions: s.dynasty_definitions.map((d) => ({
        ...d,
        culture_faith_periods: d.culture_faith_periods.map((p) => ({
          ...p,
          culture: p.culture || 'culture_fallback',
          faith: p.faith || 'religion_fallback',
        })),
        languages: d.languages.map((l) =>
          typeof l === 'string' ? l : `${l.id},${l.start_year},${l.end_year}`
        ),
      })),
    };
  },

  // Resolve the male/female name pools for a culture, using the uploaded
  // cultures → name_list mapping when present (else treat the id as a list base).
  jamieNames: () => {
    const s = get();
    const nl = s.parsed_files.name_lists;
    const cultures = s.parsed_files.cultures;
    const cultureId = s.jamie_settings.culture_id;
    let base = cultureId;
    if (cultures[cultureId]) base = cultures[cultureId].replace(/^name_list_/, '');
    const male = nl[`${base}_male`] || nl.default_male || [];
    const female = nl[`${base}_female`] || nl.default_female || [];
    return { male, female, base };
  },

  // Build the JSON payload for /generate_jamie
  buildJamiePayload: () => {
    const s = get();
    const { male, female } = get().jamieNames();
    return {
      settings: {
        ...s.jamie_settings,
        faith_id: s.jamie_settings.faith_id || 'faith_fallback',
        culture_id: s.jamie_settings.culture_id || 'culture_fallback',
        random_seed: Math.floor(Math.random() * 2147483647),
      },
      male_names: male,
      female_names: female,
    };
  },

  isReady: () => {
    const s = get();
    return Boolean(s.parsed_files.titles_txt) && Object.keys(s.parsed_files.name_lists).length > 0;
  },
}), {
  name: 'ck3-history-store',
  storage: createJSONStorage(() => localStorage),
  // Persist user config only; task/tree state and transient UI flags stay ephemeral.
  partialize: (s) => ({
    global_settings: s.global_settings,
    life_cycle: s.life_cycle,
    parsed_files: s.parsed_files,
    title_sequences: s.title_sequences,
    title_gap_fills: s.title_gap_fills,
    dynasty_definitions: s.dynasty_definitions,
    app_mode: s.app_mode,
    jamie_settings: s.jamie_settings,
    simplified_mode: s.simplified_mode,
    // dark_mode is intentionally NOT persisted here — it derives from the dedicated
    // 'ck3_dark_mode' key (written only on an explicit toggle) so the default stays dark.
    active_view: s.active_view,
    tutorial_enabled: s.tutorial_enabled,
  }),
  // On rehydrate, always recompute dark_mode from the explicit key so a previously
  // persisted value can't override the dark default (default dark unless user picked light).
  merge: (persisted, current) => ({
    ...current,
    ...persisted,
    dark_mode: localStorage.getItem('ck3_dark_mode') !== 'false',
  }),
}));
