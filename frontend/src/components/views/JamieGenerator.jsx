import { useStore } from '../../store';

// Jamie's Handy Character History Generator — the linear single-dynasty mode.
// Faithfully exposes the Excel tool's inputs; culture/faith/names come from the
// app's upload system instead of being typed into a spreadsheet.

const inputCls =
  'border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-black dark:text-white px-2 py-1.5 text-sm focus:outline-none focus:border-black dark:focus:border-white';

function Num({ label, value, onChange, step, min, max, hint }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">{label}</span>
      <input
        type="number"
        value={value}
        step={step}
        min={min}
        max={max}
        onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
        className={inputCls}
      />
      {hint && <span className="text-[10px] text-gray-500 dark:text-gray-500">{hint}</span>}
    </label>
  );
}

function Text({ label, value, onChange, placeholder, hint }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">{label}</span>
      <input type="text" value={value} placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)} className={inputCls} />
      {hint && <span className="text-[10px] text-gray-500 dark:text-gray-500">{hint}</span>}
    </label>
  );
}

function Select({ label, value, onChange, options, hint }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className={inputCls}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      {hint && <span className="text-[10px] text-gray-500 dark:text-gray-500">{hint}</span>}
    </label>
  );
}

function Check({ label, value, onChange, hint }) {
  return (
    <label className="flex items-start gap-2 cursor-pointer py-0.5">
      <input type="checkbox" checked={value} onChange={(e) => onChange(e.target.checked)}
        className="w-4 h-4 accent-amber-500 mt-0.5" />
      <span>
        <span className="text-sm text-black dark:text-white">{label}</span>
        {hint && <span className="block text-[10px] text-gray-500 dark:text-gray-500">{hint}</span>}
      </span>
    </label>
  );
}

function Section({ title, children, cols = 2 }) {
  return (
    <div className="mb-7">
      <h3 className="text-sm font-extrabold uppercase tracking-wider text-black dark:text-white mb-3">{title}</h3>
      <div className={`grid gap-3 ${cols === 3 ? 'grid-cols-3' : cols === 1 ? 'grid-cols-1' : 'grid-cols-2'}`}>
        {children}
      </div>
    </div>
  );
}

export default function JamieGenerator() {
  const { jamie_settings: j, setJamie, parsed_files, jamieNames } = useStore();
  const upd = (patch) => setJamie(patch);

  const cultureIds = Object.keys(parsed_files.cultures || {}).sort();
  // Name-list bases discoverable from uploaded name lists (strip the _male/_female suffix).
  const nameBases = [...new Set(
    Object.keys(parsed_files.name_lists || {})
      .filter((k) => k.endsWith('_male') || k.endsWith('_female'))
      .map((k) => k.replace(/_(male|female)$/, ''))
  )].filter((b) => b !== 'default').sort();

  const { male, female, base } = jamieNames();
  const namesOk = male.length > 0 && female.length > 0;

  const religionIds = Object.keys(parsed_files.religions || {}).sort();

  // Culture options: prefer the uploaded cultures file; otherwise let the user
  // pick a name-list base directly (also used as the culture id written out).
  const cultureOptions = cultureIds.length > 0
    ? [{ value: '', label: '— select culture —' }, ...cultureIds.map((c) => ({ value: c, label: c }))]
    : [{ value: '', label: '— select name list —' }, ...nameBases.map((b) => ({ value: b, label: b }))];

  return (
    <div className="max-w-4xl">
      <div className="mb-6">
        <h2 className="text-lg font-extrabold text-black dark:text-white">Jamie's Handy Character Generator</h2>
        <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
          A linear single-dynasty generator: one founder couple grown generation by generation into a
          full family tree with a title-succession chain. Culture, faith and names come from your uploaded files.
        </p>
      </div>

      <Section title="Identity">
        <Text label="Dynasty ID" value={j.dynasty_id} onChange={(v) => upd({ dynasty_id: v })} placeholder="dynasty_guthmunding" />
        <Text label="Character ID String" value={j.char_id_string} onChange={(v) => upd({ char_id_string: v })}
          placeholder="lineofguthmunding" hint="Common prefix for every generated character id." />
        <Select label="Culture" value={j.culture_id} onChange={(v) => upd({ culture_id: v })} options={cultureOptions}
          hint={namesOk
            ? `✓ Name list "${base}" — ${male.length} male / ${female.length} female names`
            : '⚠ No name list found for this culture — upload one or pick another.'} />
        {religionIds.length > 0 ? (
          <Select label="Faith" value={j.faith_id} onChange={(v) => upd({ faith_id: v })}
            options={[{ value: '', label: '— select faith —' }, ...religionIds.map((r) => ({ value: r, label: r }))]} />
        ) : (
          <Text label="Faith ID" value={j.faith_id} onChange={(v) => upd({ faith_id: v })} placeholder="faith_withered_court"
            hint="Upload a Religions file to pick from a list." />
        )}
        <Num label="Starting ID Number" value={j.initial_char_id} onChange={(v) => upd({ initial_char_id: v })} min={0} />
        <Num label="Starting Birth Year" value={j.start_birth_year} onChange={(v) => upd({ start_birth_year: v })} />
        <Text label="Title ID (optional)" value={j.title_id} onChange={(v) => upd({ title_id: v })} placeholder="d_example"
          hint="If set, the succession chain is wrapped in this title; otherwise a bare holder fragment is emitted." />
      </Section>

      <Section title="Family Structure">
        <Num label="Generations" value={j.generations} onChange={(v) => upd({ generations: v })} min={1} max={12} />
        <Num label="Generations of Siblings" value={j.generation_siblings} onChange={(v) => upd({ generation_siblings: v })} min={0}
          hint="How many generations from the end branch into siblings (earlier ones are a single line)." />
        <Num label="Maximum Children" value={j.children_max} onChange={(v) => upd({ children_max: v })} min={1} />
        <Select label="Dominant Sex" value={j.dominant_sex} onChange={(v) => upd({ dominant_sex: v })}
          options={[{ value: 'MALE', label: 'Male (agnatic)' }, { value: 'FEMALE', label: 'Female (matrilineal)' }, { value: 'EQUAL', label: 'Equal (both lines continue)' }]}
          hint="Which sex carries the dynasty and title succession." />
      </Section>

      <Section title="Marriage & Childbearing">
        <Num label="Minimum Marriage Age" value={j.marriage_min_age} onChange={(v) => upd({ marriage_min_age: v })} min={0} />
        <Num label="Maximum Marriage Age" value={j.marriage_max_age} onChange={(v) => upd({ marriage_max_age: v })} min={0} />
        <Num label="Min (Heir Age − Spouse Age)" value={j.agediff_min} onChange={(v) => upd({ agediff_min: v })} />
        <Num label="Max (Heir Age − Spouse Age)" value={j.agediff_max} onChange={(v) => upd({ agediff_max: v })} />
        <Num label="Minimum Childbearing Age" value={j.childbirth_min_age} onChange={(v) => upd({ childbirth_min_age: v })} min={0} />
        <Num label="Maximum Childbearing Age" value={j.childbirth_max_age} onChange={(v) => upd({ childbirth_max_age: v })} min={0} />
      </Section>

      <Section title="Mortality" cols={3}>
        <Num label="Battle Death Chance" value={j.battle_death_chance} onChange={(v) => upd({ battle_death_chance: v })} step={0.01} min={0} max={1} hint="Males only." />
        <Num label="Battle Min Age" value={j.battle_death_min_age} onChange={(v) => upd({ battle_death_min_age: v })} min={0} />
        <Num label="Battle Max Age" value={j.battle_death_max_age} onChange={(v) => upd({ battle_death_max_age: v })} min={0} />
        <Num label="Illness Death Chance" value={j.ill_death_chance} onChange={(v) => upd({ ill_death_chance: v })} step={0.01} min={0} max={1} />
        <Num label="Illness Min Age" value={j.ill_death_min_age} onChange={(v) => upd({ ill_death_min_age: v })} min={0} />
        <Num label="Illness Max Age" value={j.ill_death_max_age} onChange={(v) => upd({ ill_death_max_age: v })} min={0} />
        <Num label="Intrigue Death Chance" value={j.intrigue_death_chance} onChange={(v) => upd({ intrigue_death_chance: v })} step={0.01} min={0} max={1} />
        <Num label="Intrigue Min Age" value={j.intrigue_death_min_age} onChange={(v) => upd({ intrigue_death_min_age: v })} min={0} />
        <Num label="Intrigue Max Age" value={j.intrigue_death_max_age} onChange={(v) => upd({ intrigue_death_max_age: v })} min={0} />
        <Num label="Old Age Min" value={j.old_death_min_age} onChange={(v) => upd({ old_death_min_age: v })} min={0} />
        <Num label="Old Age Max" value={j.old_death_max_age} onChange={(v) => upd({ old_death_max_age: v })} min={0} />
      </Section>

      <Section title="Heroes" cols={3}>
        <Num label="Hero Chance" value={j.hero_chance} onChange={(v) => upd({ hero_chance: v })} step={0.01} min={0} max={1} hint="Chance a male gets a skill buff." />
        <Num label="Hero Buff Min" value={j.hero_buff_min} onChange={(v) => upd({ hero_buff_min: v })} min={0} />
        <Num label="Hero Buff Max" value={j.hero_buff_max} onChange={(v) => upd({ hero_buff_max: v })} min={0} />
      </Section>

      <Section title="Options" cols={1}>
        <Check label="Enforce unbroken dominant-sex line" value={j.option_male_line} onChange={(v) => upd({ option_male_line: v })}
          hint="Guarantee at least one dominant-sex child each generation so the line never dies out." />
        <Check label="Add sexuality" value={j.option_sexuality} onChange={(v) => upd({ option_sexuality: v })} />
        <Check label="Add nicknames" value={j.option_nicknames} onChange={(v) => upd({ option_nicknames: v })}
          hint="Small chance per heir from the built-in nickname list." />
        <Check label="Add personality traits" value={j.option_personality_traits} onChange={(v) => upd({ option_personality_traits: v })} />
        <Check label="Add skills" value={j.option_skills} onChange={(v) => upd({ option_skills: v })} />
        <Check label="Add education (requires skills)" value={j.option_education} onChange={(v) => upd({ option_education: v })} />
        <Check label="Add heroes (requires skills)" value={j.option_heroes} onChange={(v) => upd({ option_heroes: v })} />
        <Check label="Use name loc keys" value={j.option_loc_keys} onChange={(v) => upd({ option_loc_keys: v })}
          hint="Treat names as localisation keys (no surrounding quotes)." />
      </Section>
    </div>
  );
}
