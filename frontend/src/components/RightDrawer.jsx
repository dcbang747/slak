import { useStore } from '../store';

export default function RightDrawer() {
  const {
    drawer_open, setDrawer,
    task_state, task_result, task_error, download_url,
  } = useStore();

  if (!drawer_open) return null;

  const running = task_state === 'RUNNING';

  return (
    <aside className="w-[30vw] min-w-[360px] shrink-0 bg-gray-50 dark:bg-gray-900 border-l border-gray-300 dark:border-gray-700 h-full flex flex-col">
      <div className="px-4 py-3 border-b border-gray-300 dark:border-gray-700 flex justify-between items-center">
        <div className="text-xs font-extrabold uppercase tracking-wider text-black dark:text-white">
          Generation Log
        </div>
        <button
          onClick={() => setDrawer(false)}
          className="text-gray-600 dark:text-gray-400 hover:text-black dark:hover:text-white text-sm"
        >
          ✕
        </button>
      </div>

      {/* Terminal — intentionally stays dark in both modes */}
      <div className="flex-1 overflow-y-auto bg-black text-gray-300 font-mono text-xs p-3">
        {running && <div className="text-white">▌ Generating…</div>}
        {task_state === 'SUCCESS' && <div className="text-green-400">✓ Generation complete.</div>}
        {task_state === 'FAILURE' && (
          <div className="text-gray-300 mt-2">ERROR: {task_error}</div>
        )}
        {!task_state && (
          <div className="text-gray-600">Idle. Click Generate Simulation to start.</div>
        )}
      </div>

      <div className="px-3 py-3 border-t border-gray-300 dark:border-gray-700">
        {task_state === 'SUCCESS' && download_url ? (
          <>
            <a
              href={download_url}
              download="CK3_HISTORY_GENERATOR_OUTPUT.zip"
              className="block w-full text-center bg-gray-800 dark:bg-gray-200 text-white dark:text-black py-3 text-sm font-extrabold uppercase tracking-wider hover:bg-black dark:hover:bg-white"
            >
              Download ZIP
            </a>
            {task_result && (
              <div className="text-xs text-gray-600 dark:text-gray-400 mt-2 text-center">
                {task_result.characters} characters · {task_result.titles_with_history} titles
              </div>
            )}
          </>
        ) : (
          <div className="text-xs text-gray-600 dark:text-gray-400 text-center italic">
            {running ? 'Running the simulation…' : 'Output will appear here when generation completes.'}
          </div>
        )}
      </div>
    </aside>
  );
}
