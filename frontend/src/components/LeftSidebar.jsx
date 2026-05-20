import { useStore } from '../store';
import Dropzone from './Dropzone';
import {
  uploadTitles, uploadTraits, uploadNames,
  uploadReligions, uploadCultures,
  startGeneration,
} from '../api';

const BASE_NAV = [
  { id: 'global', label: 'Global Settings' },
  { id: 'lifecycle', label: 'Life Cycle Modifiers' },
  { id: 'titles', label: 'Title Histories' },
];

export default function LeftSidebar() {
  const {
    parsed_files, global_settings, active_view, setView,
    simplified_mode, setSimplified,
    dark_mode, setDarkMode,
    tutorial_enabled, setTutorialEnabled,
    task_state,
    setParsedTitles, clearParsedTitles,
    setParsedTraits, clearParsedTraits,
    setParsedNames, clearParsedNames,
    setParsedReligions, clearParsedReligions,
    setParsedCultures, clearParsedCultures,
    setDrawer, setTaskState, resetTask, buildPayload, resetAll,
  } = useStore();

  const nav = task_state === 'SUCCESS'
    ? [...BASE_NAV, { id: 'tree', label: 'Family Tree' }]
    : BASE_NAV;

  const hasTitles = parsed_files.titles.length > 0;
  const hasNames = Object.keys(parsed_files.name_lists).length > 0;
  const hasNamesFile = parsed_files.names_filenames.length > 0;
  const skipTitles = global_settings.ignore_title_generation;
  const ready = (hasTitles || skipTitles) && hasNames;

  const handle = (uploader, setter) => async (file) => {
    try {
      const data = await uploader(file);
      setter(data);
    } catch (err) {
      alert(`Upload failed: ${err.message}`);
    }
  };

  const onGenerate = async () => {
    resetTask();
    setDrawer(true);
    try {
      const { task_id } = await startGeneration(buildPayload());
      setTaskState({ task_id, task_state: 'PENDING', append_message: 'Submitted to worker.' });
    } catch (err) {
      setTaskState({ task_state: 'FAILURE', task_error: err.message });
    }
  };

  // Human-readable reason the Generate button is disabled (shown inline, not just on hover).
  const disabledReason = ready ? null
    : (!hasNames && !hasTitles && !skipTitles) ? 'Upload a Title History and a Name Lists file to generate.'
    : (!hasNames && hasNamesFile) ? 'Name list is empty — use format: list_id: name1, name2'
    : !hasNames ? 'Upload a Name Lists file to generate.'
    : "Upload a Title History file, or tick 'Skip Title History' in Global Settings.";

  const onResetAll = () => {
    if (window.confirm('Reset everything? This clears all uploaded files, dynasties, title sequences, and settings.')) {
      resetAll();
    }
  };

  return (
    <aside className="w-[250px] shrink-0 bg-gray-50 dark:bg-gray-900 border-r border-gray-300 dark:border-gray-700 flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-4 border-b border-gray-300 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-extrabold text-black dark:text-white uppercase tracking-wider">CK3 History</div>
            <div className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">v7.0 Generator</div>
          </div>
          <div className="flex items-center gap-1">
            {/* Dark mode toggle */}
            <button
              onClick={() => setDarkMode(!dark_mode)}
              title={dark_mode ? 'Switch to light mode' : 'Switch to dark mode'}
              className="w-7 h-7 flex items-center justify-center text-gray-500 dark:text-gray-400 hover:text-black dark:hover:text-white text-base leading-none"
            >
              {dark_mode ? '☀' : '☾'}
            </button>
            {/* Simplified mode toggle */}
            <button
              onClick={() => setSimplified(!simplified_mode)}
              title={simplified_mode ? 'Switch to advanced mode' : 'Hide non-essential options'}
              className={[
                'text-[10px] font-extrabold uppercase tracking-wide px-2 py-1 border shrink-0',
                simplified_mode
                  ? 'border-black dark:border-white bg-black dark:bg-white text-white dark:text-black'
                  : 'border-gray-300 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:border-black dark:hover:border-white hover:text-black dark:hover:text-white',
              ].join(' ')}
            >
              {simplified_mode ? 'Advanced' : 'Simple'}
            </button>
          </div>
        </div>
        {/* Tutorial toggle — sits under the Simple/Advanced button */}
        <div className="flex justify-end mt-2">
          <label className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 cursor-pointer hover:text-black dark:hover:text-white">
            <input
              type="checkbox"
              checked={tutorial_enabled}
              onChange={(e) => setTutorialEnabled(e.target.checked)}
              className="w-3 h-3 accent-amber-500"
            />
            Tutorial
          </label>
        </div>
      </div>

      {/* Dropzones */}
      <div className="px-3 py-3 overflow-y-auto flex-1">
        <Dropzone
          label={skipTitles ? 'Title History (optional)' : 'Title History'}
          onFile={handle(uploadTitles, setParsedTitles)}
          filename={parsed_files.titles_filename}
          onClear={clearParsedTitles}
          info={skipTitles
            ? "Skip Title History is on — not required. Upload only if you want to configure title sequences."
            : "Found in your mod under:\\history\\titles"}
        />
        <div data-tour="namelist">
          <Dropzone
            label="Name Lists"
            multiple
            onFile={handle(uploadNames, setParsedNames)}
            filenames={parsed_files.names_filenames}
            onClear={clearParsedNames}
            error={hasNamesFile && !hasNames ? 'No names parsed — use format: list_id: name1, name2' : null}
            info="Found in your mod under:\common\culture\name_lists"
          />
        </div>
        {!simplified_mode && (
          <Dropzone
            label="Genetic Traits"
            multiple
            onFile={handle(uploadTraits, setParsedTraits)}
            filenames={parsed_files.traits_filenames}
            onClear={clearParsedTraits}
            info="Found in your mod under:\common\traits"
          />
        )}
        <div data-tour="religion">
          <Dropzone
            label="Religions"
            multiple
            onFile={handle(uploadReligions, setParsedReligions)}
            filenames={parsed_files.religions_filenames}
            onClear={clearParsedReligions}
            info="Found in your mod under:\common\religion\religion_types — used to determine marital doctrine (monogamy, polygamy, concubines) per faith."
          />
        </div>
        <div data-tour="culture">
          <Dropzone
            label="Cultures"
            multiple
            onFile={handle(uploadCultures, setParsedCultures)}
            filenames={parsed_files.cultures_filenames}
            onClear={clearParsedCultures}
            info="Found in your mod under:\common\culture\cultures — enables culture dropdown with name list info in dynasty settings."
          />
        </div>

        <div className="border-t border-gray-300 dark:border-gray-700 my-4" />

        {/* Navigation */}
        <nav className="flex flex-col gap-1">
          {nav.filter((item) => !simplified_mode || item.id !== 'lifecycle').map((item) => (
            <button
              key={item.id}
              data-tour={item.id === 'tree' ? 'family-tree' : undefined}
              onClick={() => setView(item.id)}
              className={[
                'text-left px-3 py-2 text-sm font-extrabold uppercase tracking-wide',
                active_view === item.id
                  ? 'bg-black dark:bg-white text-white dark:text-black'
                  : 'text-gray-600 dark:text-gray-400 hover:text-black dark:hover:text-white',
              ].join(' ')}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Execution button */}
      <div className="px-3 py-3 border-t border-gray-300 dark:border-gray-700" data-tour="generate">
        <button
          disabled={!ready}
          onClick={onGenerate}
          className={[
            'w-full py-3 text-sm font-extrabold uppercase tracking-wider',
            ready
              ? 'bg-gray-800 dark:bg-gray-100 text-white dark:text-black hover:bg-black dark:hover:bg-white cursor-pointer'
              : 'bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-500 cursor-not-allowed',
          ].join(' ')}
        >
          Generate Simulation
        </button>
        {disabledReason && (
          <p className="mt-1.5 text-[11px] leading-snug text-amber-600 dark:text-amber-400">{disabledReason}</p>
        )}
        <button
          onClick={onResetAll}
          className="mt-2 w-full text-[11px] font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500 hover:text-red-500 dark:hover:text-red-400"
        >
          Reset all
        </button>
      </div>
    </aside>
  );
}
