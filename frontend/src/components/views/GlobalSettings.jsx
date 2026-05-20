import { useState } from 'react';
import { useStore } from '../../store';
import InfoTip from '../InfoTip';
import { toInGameYearLabel } from '../../yearConvert';

// ---------------------------------------------------------------------------
// Shared field components
// ---------------------------------------------------------------------------

function NumberField({ label, value, onChange, min, max, step = 1, hint }) {
  return (
    <label className="block mb-4">
      <span className="block text-xs font-extrabold uppercase tracking-wider text-gray-600 dark:text-gray-400 mb-1">
        {label}
      </span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 px-3 py-2 text-sm text-black dark:text-white focus:outline-none focus:border-black dark:focus:border-white"
      />
      {hint && (
        <span className="block mt-0.5 text-[10px] italic text-gray-400 dark:text-gray-500">{hint}</span>
      )}
    </label>
  );
}

function TextField({ label, value, onChange, placeholder }) {
  return (
    <label className="block mb-3">
      <span className="block text-xs font-extrabold uppercase tracking-wider text-gray-600 dark:text-gray-400 mb-1">
        {label}
      </span>
      <input
        type="text"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 px-3 py-2 text-sm text-black dark:text-white focus:outline-none focus:border-black dark:focus:border-white"
      />
    </label>
  );
}

function CheckboxField({ label, description, value, onChange, disabled, info, infoUp = false }) {
  return (
    <label className={['flex items-start gap-3 mb-4', disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'].join(' ')}>
      <input
        type="checkbox"
        checked={value}
        onChange={(e) => { if (!disabled) onChange(e.target.checked); }}
        disabled={disabled}
        className="mt-0.5 w-4 h-4 border border-gray-400 dark:border-gray-600 accent-black dark:accent-white shrink-0"
      />
      <span className="flex-1">
        <span className="flex items-center gap-1.5">
          <span className="text-xs font-extrabold uppercase tracking-wider text-gray-600 dark:text-gray-400">
            {label}
          </span>
          {info && <InfoTip text={info} up={infoUp} />}
        </span>
        {description && (
          <span className="block text-xs text-gray-500 dark:text-gray-500 mt-0.5">{description}</span>
        )}
      </span>
    </label>
  );
}

function SelectField({ label, value, onChange, options }) {
  return (
    <label className="block mb-4">
      <span className="block text-xs font-extrabold uppercase tracking-wider text-gray-600 dark:text-gray-400 mb-1">
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 px-3 py-2 text-sm text-black dark:text-white focus:outline-none focus:border-black dark:focus:border-white"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </label>
  );
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const GENDER_LAW_OPTIONS = [
  { value: 'AGNATIC',          label: 'Agnatic (Males only)' },
  { value: 'AGNATIC_COGNATIC', label: 'Agnatic-Cognatic (Males first, females fallback)' },
  { value: 'ABSOLUTE_COGNATIC', label: 'Absolute Cognatic (Equal, elder_of decides)' },
  { value: 'ENATIC_COGNATIC',  label: 'Enatic-Cognatic (Females first, males fallback)' },
  { value: 'ENATIC',           label: 'Enatic (Females only)' },
];

const SUCCESSION_OPTIONS = [
  { value: 'PRIMOGENITURE',  label: 'Primogeniture (eldest child)' },
  { value: 'ULTIMOGENITURE', label: 'Ultimogeniture (youngest child)' },
  { value: 'SENIORITY',      label: 'Seniority (oldest dynasty member)' },
];

// ---------------------------------------------------------------------------
// Dynasty sub-components
// ---------------------------------------------------------------------------

function CultureFaithRow({ period, onUpdate, onRemove, canRemove, religions, cultures }) {
  const cultureOptions = Object.entries(cultures ?? {});
  const hasCultures = cultureOptions.length > 0;
  const currentNameList = period.culture ? (cultures?.[period.culture] ?? null) : null;

  const faithOptions = Object.entries(religions ?? {});
  const hasReligions = faithOptions.length > 0;
  const currentDoctrine = period.faith ? (religions?.[period.faith] ?? null) : null;

  const inputCls = 'flex-1 bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 px-2 py-1 text-xs text-black dark:text-white focus:outline-none focus:border-black dark:focus:border-white';

  return (
    <div className="flex gap-2 mb-2 items-start">
      <div className="w-20 shrink-0">
        <input
          type="number"
          value={period.start_year}
          onChange={(e) => onUpdate({ start_year: Number(e.target.value) })}
          className="w-full bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 px-2 py-1 text-xs text-black dark:text-white focus:outline-none focus:border-black dark:focus:border-white"
          placeholder="Year"
        />
      </div>
      <div className="flex-1 flex items-center gap-1">
        {hasCultures ? (
          <select
            value={period.culture}
            onChange={(e) => onUpdate({ culture: e.target.value })}
            className={inputCls}
          >
            <option value="">— select culture —</option>
            {cultureOptions.map(([ck, nl]) => (
              <option key={ck} value={ck}>{ck}</option>
            ))}
          </select>
        ) : (
          <input
            type="text"
            value={period.culture}
            onChange={(e) => onUpdate({ culture: e.target.value })}
            className={inputCls}
            placeholder="culture_fallback"
          />
        )}
        {currentNameList && (
          <InfoTip text={`Name list: ${currentNameList}`} />
        )}
      </div>
      <div className="flex-1 flex items-center gap-1">
        {hasReligions ? (
          <select
            value={period.faith}
            onChange={(e) => onUpdate({ faith: e.target.value })}
            className={inputCls}
          >
            <option value="">— select faith —</option>
            {faithOptions.map(([fk, doctrine]) => (
              <option key={fk} value={fk}>{fk} ({doctrine})</option>
            ))}
          </select>
        ) : (
          <input
            type="text"
            value={period.faith}
            onChange={(e) => onUpdate({ faith: e.target.value })}
            className={inputCls}
            placeholder="religion_fallback"
          />
        )}
        {currentDoctrine && (
          <InfoTip text={`Marital doctrine: ${currentDoctrine}`} />
        )}
      </div>
      {canRemove && (
        <button
          onClick={onRemove}
          className="text-gray-400 dark:text-gray-500 hover:text-black dark:hover:text-white text-xs px-1 py-1 shrink-0"
          title="Remove period"
        >
          ×
        </button>
      )}
    </div>
  );
}

function NameInheritanceSection({ dynasty }) {
  const { updateDynastyNameInheritance } = useStore();
  const ni = dynasty.name_inheritance ?? { grandparent_chance: 0.05, parent_chance: 0.05, no_name_chance: 0.90 };
  const sum = +(ni.grandparent_chance + ni.parent_chance + ni.no_name_chance).toFixed(6);
  const valid = Math.abs(sum - 1.0) < 1e-5;

  const upd = (patch) => updateDynastyNameInheritance(dynasty.id, patch);
  const inputCls = 'w-full bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 px-2 py-1 text-xs text-black dark:text-white focus:outline-none focus:border-black dark:focus:border-white';

  return (
    <div className="mb-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-extrabold uppercase tracking-wider text-gray-600 dark:text-gray-400">
          Name Inheritance
        </span>
        <span className={`text-[10px] font-mono px-1 ${valid ? 'text-gray-400 dark:text-gray-500' : 'text-red-600 font-bold'}`}>
          sum={sum.toFixed(2)}
        </span>
      </div>
      <div className="flex gap-2">
        <label className="flex-1">
          <span className="block text-[10px] text-gray-400 dark:text-gray-500 uppercase mb-0.5">Grandparent</span>
          <input type="number" value={ni.grandparent_chance} min={0} max={1} step={0.01}
            onChange={(e) => upd({ grandparent_chance: Number(e.target.value) })} className={inputCls} />
        </label>
        <label className="flex-1">
          <span className="block text-[10px] text-gray-400 dark:text-gray-500 uppercase mb-0.5">Parent</span>
          <input type="number" value={ni.parent_chance} min={0} max={1} step={0.01}
            onChange={(e) => upd({ parent_chance: Number(e.target.value) })} className={inputCls} />
        </label>
        <label className="flex-1">
          <span className="block text-[10px] text-gray-400 dark:text-gray-500 uppercase mb-0.5">Fresh (none)</span>
          <input type="number" value={ni.no_name_chance} min={0} max={1} step={0.01}
            onChange={(e) => upd({ no_name_chance: Number(e.target.value) })} className={inputCls} />
        </label>
      </div>
      {!valid && (
        <p className="text-[10px] text-red-600 mt-1">Must sum to 1.0</p>
      )}
    </div>
  );
}

function LanguagesSection({ dynasty }) {
  const { addDynastyLanguage, updateDynastyLanguage, removeDynastyLanguage } = useStore();
  const langs = dynasty.languages ?? [];
  const inputCls = 'bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 px-2 py-1 text-xs text-black dark:text-white focus:outline-none focus:border-black dark:focus:border-white';

  return (
    <div className="mb-4">
      <div className="text-xs font-extrabold uppercase tracking-wider text-gray-600 dark:text-gray-400 mb-2">
        Languages
      </div>
      {langs.length === 0 && (
        <p className="text-[10px] text-gray-400 dark:text-gray-500 italic mb-2">
          No languages — characters will have no learn_language in their birth block.
        </p>
      )}
      {langs.map((lang, i) => {
        const l = typeof lang === 'string'
          ? (() => { const [id, s, e] = lang.split(','); return { id: id ?? '', start_year: Number(s) || 0, end_year: Number(e) || 0 }; })()
          : lang;
        return (
          <div key={i} className="flex gap-2 mb-2 items-start">
            <input type="text" value={l.id}
              onChange={(e) => updateDynastyLanguage(dynasty.id, i, { id: e.target.value })}
              className={`flex-1 ${inputCls}`} placeholder="language_westron" />
            <input type="number" value={l.start_year}
              onChange={(e) => updateDynastyLanguage(dynasty.id, i, { start_year: Number(e.target.value) })}
              className={`w-20 shrink-0 ${inputCls}`} placeholder="Start" />
            <input type="number" value={l.end_year}
              onChange={(e) => updateDynastyLanguage(dynasty.id, i, { end_year: Number(e.target.value) })}
              className={`w-20 shrink-0 ${inputCls}`} placeholder="End" />
            <button onClick={() => removeDynastyLanguage(dynasty.id, i)}
              className="text-gray-400 dark:text-gray-500 hover:text-black dark:hover:text-white text-xs px-1 py-1 shrink-0"
              title="Remove language">×</button>
          </div>
        );
      })}
      {langs.length > 0 && (
        <div className="flex gap-2 mb-1">
          <div className="flex-1 text-[10px] text-gray-400 dark:text-gray-500 uppercase">Language ID</div>
          <div className="w-20 shrink-0 text-[10px] text-gray-400 dark:text-gray-500 uppercase">Start</div>
          <div className="w-20 shrink-0 text-[10px] text-gray-400 dark:text-gray-500 uppercase">End</div>
          <div className="w-4" />
        </div>
      )}
      <button
        onClick={() => addDynastyLanguage(dynasty.id)}
        className="text-xs text-gray-500 dark:text-gray-400 hover:text-black dark:hover:text-white border border-gray-300 dark:border-gray-700 hover:border-black dark:hover:border-white px-2 py-1 mt-1"
      >
        + Add Language
      </button>
    </div>
  );
}

function DynastyCard({ dynasty }) {
  const {
    updateDynastyDef, removeDynastyDef,
    addCultureFaithPeriod, removeCultureFaithPeriod, updateCultureFaithPeriod,
    parsed_files, simplified_mode,
  } = useStore();
  const [expanded, setExpanded] = useState(true);

  const upd = (patch) => updateDynastyDef(dynasty.id, patch);

  return (
    <div className="border border-gray-300 dark:border-gray-700 mb-3">
      <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 dark:bg-gray-800 border-b border-gray-300 dark:border-gray-700">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="text-xs text-gray-500 dark:text-gray-400 hover:text-black dark:hover:text-white w-4 shrink-0"
        >
          {expanded ? '▾' : '▸'}
        </button>
        <span className="text-xs font-extrabold text-black dark:text-white flex-1 truncate">
          {dynasty.name || 'Unnamed Dynasty'}
        </span>
        <span className="text-[10px] text-gray-400 dark:text-gray-500 font-mono truncate max-w-[120px]">
          {dynasty.id}
        </span>
        <button
          onClick={() => removeDynastyDef(dynasty.id)}
          className="text-gray-400 dark:text-gray-500 hover:text-black dark:hover:text-white text-sm ml-1 shrink-0"
          title="Remove dynasty"
        >
          ×
        </button>
      </div>

      {expanded && (
        <div className="px-3 py-3">
          <TextField label="Dynasty ID (Paradox)" value={dynasty.id} onChange={(v) => upd({ id: v })} placeholder="dynasty_beor" />
          <div className="flex gap-2">
            <div className="flex-1">
              <TextField label="Name" value={dynasty.name} onChange={(v) => upd({ name: v })} placeholder="House of Beor" />
            </div>
            <div className="flex-1">
              <TextField label="Motto" value={dynasty.motto} onChange={(v) => upd({ motto: v })} placeholder="Born of Earth and Star" />
            </div>
          </div>

          <div className="flex gap-2">
            <div className="flex-1">
              <NumberField label="Start Year" value={dynasty.start_year} onChange={(v) => upd({ start_year: v })} hint={toInGameYearLabel(dynasty.start_year)} />
            </div>
            <div className="flex-1">
              <NumberField label="End Year" value={dynasty.end_year} onChange={(v) => upd({ end_year: v })} hint={toInGameYearLabel(dynasty.end_year)} />
            </div>
          </div>

          <div className="mb-4">
            <div className="text-xs font-extrabold uppercase tracking-wider text-gray-600 dark:text-gray-400 mb-2">
              Culture / Faith Periods
            </div>
            <div className="flex gap-2 mb-1">
              <div className="w-20 shrink-0 text-[10px] text-gray-400 dark:text-gray-500 uppercase">Year</div>
              <div className="flex-1 text-[10px] text-gray-400 dark:text-gray-500 uppercase">Culture</div>
              <div className="flex-1 text-[10px] text-gray-400 dark:text-gray-500 uppercase">Faith</div>
              {dynasty.culture_faith_periods.length > 1 && <div className="w-4" />}
            </div>
            {dynasty.culture_faith_periods.map((p, i) => (
              <CultureFaithRow
                key={i}
                period={p}
                onUpdate={(patch) => updateCultureFaithPeriod(dynasty.id, i, patch)}
                onRemove={() => removeCultureFaithPeriod(dynasty.id, i)}
                canRemove={dynasty.culture_faith_periods.length > 1}
                religions={parsed_files.religions}
                cultures={parsed_files.cultures}
              />
            ))}
            <button
              onClick={() => addCultureFaithPeriod(dynasty.id)}
              className="text-xs text-gray-500 dark:text-gray-400 hover:text-black dark:hover:text-white border border-gray-300 dark:border-gray-700 hover:border-black dark:hover:border-white px-2 py-1 mt-1"
            >
              + Add Period
            </button>
          </div>

          {!simplified_mode && (
            <>
              <div className="flex gap-2">
                <div className="flex-1 min-w-0">
                  <SelectField
                    label="Succession Type"
                    value={dynasty.succession ?? 'PRIMOGENITURE'}
                    onChange={(v) => upd({ succession: v })}
                    options={SUCCESSION_OPTIONS}
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <SelectField
                    label="Gender Law"
                    value={dynasty.gender_law ?? 'AGNATIC_COGNATIC'}
                    onChange={(v) => upd({ gender_law: v })}
                    options={GENDER_LAW_OPTIONS}
                  />
                </div>
              </div>

              <NameInheritanceSection dynasty={dynasty} />
              <LanguagesSection dynasty={dynasty} />
            </>
          )}

          <div className="flex gap-4">
            <div className="flex-1 min-w-0">
              <CheckboxField
                label="Lowborn Spouses"
                info="Higher chance of dynasty members marrying lowborn characters."
                infoUp
                value={dynasty.lowborn_spouses}
                onChange={(v) => upd({ lowborn_spouses: v })}
              />
            </div>
            <div className="flex-1 min-w-0">
              <CheckboxField
                label="Guaranteed Survival"
                info="Ensures this dynasty survives to its end year. Without this, the dynasty may die out early."
                infoUp
                value={dynasty.guaranteed_survival}
                onChange={(v) => upd({ guaranteed_survival: v })}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Personality Traits panel (global, left column)
// ---------------------------------------------------------------------------

function PersonalityTraitsPanel({ config, setTotalTraits, setTraitWeight }) {
  const [expanded, setExpanded] = useState(false);
  const traitEntries = Object.entries(config.traits).sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-extrabold uppercase tracking-wider text-black dark:text-white">
          Personality Traits
        </h3>
        <button
          onClick={() => setExpanded((v) => !v)}
          className="text-xs text-gray-500 dark:text-gray-400 hover:text-black dark:hover:text-white"
        >
          {expanded ? 'Collapse' : 'Edit Weights'}
        </button>
      </div>

      <NumberField
        label="Traits per Character"
        value={config.total_traits_per_character}
        onChange={setTotalTraits}
        min={1}
        max={8}
        step={1}
      />
      <p className="text-xs text-gray-500 dark:text-gray-400 -mt-2 mb-4">
        Personality traits drawn at age 16. Childhood trait assigned at age 3 from education skill.
      </p>

      {expanded && (
        <div className="border border-gray-200 dark:border-gray-700 p-2 mb-2">
          <div className="flex justify-between mb-1 px-1">
            <span className="text-[10px] text-gray-400 dark:text-gray-500 uppercase">Trait</span>
            <span className="text-[10px] text-gray-400 dark:text-gray-500 uppercase">Weight</span>
          </div>
          {traitEntries.map(([name, trait]) => (
            <div key={name} className="flex items-center justify-between gap-2 mb-1">
              <span className="text-xs text-gray-700 dark:text-gray-300 capitalize flex-1">{name}</span>
              <input
                type="number"
                value={trait.weight}
                min={0}
                step={0.1}
                onChange={(e) => setTraitWeight(name, Number(e.target.value))}
                className="w-20 bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 px-2 py-0.5 text-xs text-black dark:text-white focus:outline-none focus:border-black dark:focus:border-white"
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main view
// ---------------------------------------------------------------------------

export default function GlobalSettings() {
  const {
    global_settings, setGlobal,
    setPersonalityTraitsConfig, setPersonalityTraitWeight,
    dynasty_definitions, addDynastyDef,
    simplified_mode,
  } = useStore();

  const ptConfig = global_settings.personality_traits;

  return (
    <div className="flex gap-8 h-full">
      {/* Left column — simulation settings */}
      <div className="w-80 shrink-0 overflow-y-auto">
        <h2 className="text-2xl font-extrabold text-black dark:text-white mb-1">Global Settings</h2>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">Bounds of the simulation timeline.</p>

        <NumberField label="Start Year" value={global_settings.start_year} onChange={(v) => setGlobal({ start_year: v })} step={1} hint={toInGameYearLabel(global_settings.start_year)} />
        <NumberField label="End Year" value={global_settings.end_year} onChange={(v) => setGlobal({ end_year: v })} min={global_settings.start_year + 1} step={1} hint={toInGameYearLabel(global_settings.end_year)} />
        {global_settings.end_year <= global_settings.start_year && (
          <p className="-mt-2 mb-4 text-[11px] leading-snug text-amber-600 dark:text-amber-400">
            End Year must be after Start Year — the simulation has no years to run.
          </p>
        )}
        <NumberField label="Maximum Generations" value={global_settings.maximum_generations} onChange={(v) => setGlobal({ maximum_generations: v })} min={1} step={1} />
        {global_settings.maximum_generations < 1 && (
          <p className="-mt-2 mb-4 text-[11px] leading-snug text-amber-600 dark:text-amber-400">
            Maximum Generations must be at least 1.
          </p>
        )}

        {!simplified_mode && (
          <>
            <div className="border-t border-gray-300 dark:border-gray-700 my-6" />
            <h3 className="text-sm font-extrabold uppercase tracking-wider text-black dark:text-white mb-4">Genetics</h3>

            <NumberField
              label="Trait Frequency Multiplier"
              value={global_settings.trait_frequency_multiplier}
              onChange={(v) => setGlobal({ trait_frequency_multiplier: v })}
              min={0} max={5} step={0.1}
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 -mt-2 mb-4">
              Scales how often genetic traits are inherited and mutated. 1.0 = default, 0.0 = no traits.
            </p>

            <div className="border-t border-gray-300 dark:border-gray-700 my-6" />

            <PersonalityTraitsPanel
              config={ptConfig}
              setTotalTraits={(v) => setPersonalityTraitsConfig({ total_traits_per_character: v })}
              setTraitWeight={setPersonalityTraitWeight}
            />
          </>
        )}

        <div className="border-t border-gray-300 dark:border-gray-700 my-6" />
        <h3 className="text-sm font-extrabold uppercase tracking-wider text-black dark:text-white mb-4">Output Options</h3>
        <div data-tour="skip-title">
          <CheckboxField
            label="Skip Title History"
            description="Generate character_history.txt only — omits title_history.txt and removes the Title History upload requirement."
            value={global_settings.ignore_title_generation}
            onChange={(v) => setGlobal({ ignore_title_generation: v })}
          />
        </div>
        {!simplified_mode && (
          <>
            <CheckboxField
              label="Enable Secrets"
              description="Roll secrets (deviant, lover, murder, incest, …) for characters during simulation."
              value={global_settings.enable_secrets}
              onChange={(v) => setGlobal({ enable_secrets: v })}
            />
            <CheckboxField
              label="Enable Relationships"
              description="Generate relationship blocks (friend, rival, lover, bully, crush, …) between characters."
              value={global_settings.enable_relationships}
              onChange={(v) => setGlobal({ enable_relationships: v })}
            />
          </>
        )}
      </div>

      {/* Divider */}
      <div className="border-l border-gray-300 dark:border-gray-700" />

      {/* Right column — dynasty definitions */}
      <div className="flex-1 min-w-0 overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-2xl font-extrabold text-black dark:text-white mb-1">
              Dynasties
              {dynasty_definitions.length > 0 && (
                <span className="ml-2 text-lg text-gray-400 dark:text-gray-500 font-normal">
                  ({dynasty_definitions.length})
                </span>
              )}
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400">Define dynasties to assign to title sequences.</p>
          </div>
          <button
            data-tour="add-dynasty"
            onClick={addDynastyDef}
            className="text-xs font-extrabold uppercase tracking-wide border border-gray-300 dark:border-gray-700 hover:border-black dark:hover:border-white px-3 py-1.5 text-gray-600 dark:text-gray-400 hover:text-black dark:hover:text-white shrink-0"
          >
            + Add Dynasty
          </button>
        </div>

        {dynasty_definitions.length === 0 && (
          <p className="text-xs text-gray-500 dark:text-gray-400 italic">
            No dynasties defined. Add a dynasty to configure culture, faith, succession, and other properties.
            The dynasty ID is used in the Title Histories tab to assign dynasties to titles.
          </p>
        )}

        {dynasty_definitions.map((d) => (
          <DynastyCard key={d.id} dynasty={d} />
        ))}
      </div>
    </div>
  );
}
