import { useStore } from '../../store';

function Slider({ label, value, onChange, min, max, step }) {
  const clamp = (v) => Math.min(max, Math.max(min, v));
  return (
    <label className="block mb-5">
      <div className="flex justify-between items-baseline mb-1">
        <span className="text-xs font-extrabold uppercase tracking-wider text-gray-600 dark:text-gray-400">{label}</span>
        <input
          type="number"
          value={value}
          min={min}
          max={max}
          step={step}
          onChange={(e) => {
            const v = Number(e.target.value);
            if (!Number.isNaN(v)) onChange(clamp(v));
          }}
          className="w-20 text-right bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 px-1.5 py-0.5 text-sm text-black dark:text-white focus:outline-none focus:border-black dark:focus:border-white"
        />
      </div>
      <input
        type="range"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-black dark:accent-white"
      />
    </label>
  );
}

export default function LifeCycleModifiers() {
  const { life_cycle, setLifeCycle } = useStore();
  return (
    <div className="max-w-xl">
      <h2 className="text-2xl font-extrabold text-black dark:text-white mb-1">Life Cycle Modifiers</h2>
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">Demographic probabilities driving the engine.</p>

      <Slider
        label="Max Age Difference Between Partners"
        value={life_cycle.max_age_difference_between_partners}
        onChange={(v) => setLifeCycle({ max_age_difference_between_partners: v })}
        min={1} max={50} step={1}
      />
      <Slider
        label="Max Children Per Couple"
        value={life_cycle.max_children_per_couple}
        onChange={(v) => setLifeCycle({ max_children_per_couple: v })}
        min={0} max={15} step={1}
      />
      <Slider
        label="Base Fertility Rate"
        value={life_cycle.base_fertility_rate}
        onChange={(v) => setLifeCycle({ base_fertility_rate: v })}
        min={0} max={1} step={0.01}
      />
      <Slider
        label="Male Bastard Chance"
        value={life_cycle.male_bastard_chance}
        onChange={(v) => setLifeCycle({ male_bastard_chance: v })}
        min={0} max={1} step={0.01}
      />
      <Slider
        label="Female Bastard Chance"
        value={life_cycle.female_bastard_chance}
        onChange={(v) => setLifeCycle({ female_bastard_chance: v })}
        min={0} max={1} step={0.01}
      />
      <Slider
        label="Dynasty Soft Cap"
        value={life_cycle.dynasty_soft_cap}
        onChange={(v) => setLifeCycle({ dynasty_soft_cap: v })}
        min={5} max={500} step={5}
      />
    </div>
  );
}
