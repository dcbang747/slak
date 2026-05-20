import { useState, useCallback } from 'react';
import InfoTip from './InfoTip';

export default function Dropzone({ label, accept = '.txt', onFile, filename, filenames, onClear, error, info }) {
  const [hover, setHover] = useState(false);
  const isMulti = filenames !== undefined;

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setHover(false);
    const files = isMulti
      ? Array.from(e.dataTransfer?.files ?? []).filter(Boolean)
      : [e.dataTransfer?.files?.[0]].filter(Boolean);
    files.forEach(f => onFile(f));
  }, [onFile, isMulti]);

  const handleChange = useCallback((e) => {
    const files = isMulti
      ? Array.from(e.target?.files ?? []).filter(Boolean)
      : [e.target?.files?.[0]].filter(Boolean);
    files.forEach(f => onFile(f));
    e.target.value = '';
  }, [onFile, isMulti]);

  const loadedCount = isMulti ? filenames.length : (filename ? 1 : 0);

  return (
    <div className="relative mb-3">
      {info && (
        <div className="absolute top-1 right-1 z-10">
          <InfoTip text={info} />
        </div>
      )}
      <label
        onDragOver={(e) => { e.preventDefault(); setHover(true); }}
        onDragLeave={() => setHover(false)}
        onDrop={handleDrop}
        className={[
          'block cursor-pointer text-center text-xs',
          'rounded border-2 border-dashed',
          'px-3 py-4',
          hover
            ? 'bg-gray-100 dark:bg-gray-700 border-black dark:border-white'
            : 'bg-gray-50 dark:bg-gray-800 border-gray-300 dark:border-gray-600',
          error ? 'border-gray-600 dark:border-gray-400' : '',
        ].join(' ')}
      >
        <div className="font-extrabold text-black dark:text-white uppercase tracking-wide">{label}</div>
        {isMulti ? (
          loadedCount === 0 ? (
            <div className="mt-1 text-gray-600 dark:text-gray-400">drag .txt files here or click</div>
          ) : loadedCount === 1 ? (
            <div className="mt-1 text-gray-600 dark:text-gray-400 truncate">
              <span className="text-black dark:text-white">✓</span> {filenames[0]}
            </div>
          ) : (
            <div className="mt-1 text-gray-600 dark:text-gray-400">
              <span className="text-black dark:text-white">✓</span> {loadedCount} files loaded
            </div>
          )
        ) : (
          filename ? (
            <div className="mt-1 text-gray-600 dark:text-gray-400 truncate">
              <span className="text-black dark:text-white">✓</span> {filename}
            </div>
          ) : (
            <div className="mt-1 text-gray-600 dark:text-gray-400">drag .txt here or click</div>
          )
        )}
        {error && <div className="mt-1 text-gray-600 dark:text-gray-400">{error}</div>}
        <input type="file" accept={accept} onChange={handleChange} className="hidden" multiple={isMulti} />
      </label>
      {loadedCount > 0 && onClear && (
        <button
          onClick={onClear}
          className="text-[10px] text-gray-400 dark:text-gray-500 hover:text-red-500 dark:hover:text-red-400 underline block text-right pr-1 mt-1"
        >
          clear
        </button>
      )}
    </div>
  );
}
