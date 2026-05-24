import { useState, useRef, useMemo, useLayoutEffect } from 'react';
import { useStore } from '../store';

const ROW_HEIGHT = 48;
const LABEL_WIDTH = 240;
const MIN_PX_PER_YEAR = 2;
const MAX_PX_PER_YEAR = 20;
const MIN_GAP_YEARS = 50; // gaps of 50 years or shorter are too short to fill

const TIER_FROM_PREFIX = { h_: 'hegemony', e_: 'empire', k_: 'kingdom', d_: 'duchy', c_: 'county', b_: 'barony' };

// Mirror of backend compute_title_gaps + occupancy: walk holder events and split
// [start,end] into occupied (any non-0 holder) and vacant gaps (>50yr → fillable).
function computeSegments(events, start, end, minGap = MIN_GAP_YEARS) {
  const occupied = [];
  const gaps = [];
  if (end <= start) return { occupied, gaps };

  const changes = [];
  let prev = null;
  for (const e of [...(events || [])].sort((a, b) => a.year - b.year)) {
    if (prev === null || e.vacant !== prev) { changes.push([e.year, e.vacant]); prev = e.vacant; }
  }

  let stateVacant = true;
  const future = [];
  for (const [y, v] of changes) { if (y <= start) stateVacant = v; else future.push([y, v]); }

  let cursor = start;
  let state = stateVacant;
  const push = (s, e, vac) => {
    if (e <= s) return;
    if (vac) { if (e - s > minGap) gaps.push({ start: s, end: e }); }
    else occupied.push({ start: s, end: e });
  };
  for (const [y, v] of future) {
    if (y >= end) break;
    push(cursor, y, state);
    cursor = y;
    state = v;
  }
  push(cursor, end, state);
  return { occupied, gaps };
}

function YearRuler({ startYear, endYear, pxPerYear }) {
  const totalYears = endYear - startYear;
  const tickStep = totalYears > 400 ? 50 : totalYears > 150 ? 25 : 10;
  return (
    <div className="flex border-b-2 border-gray-400 dark:border-gray-600 bg-gray-50 dark:bg-gray-800 sticky top-0 z-20" style={{ height: 28 }}>
      <div
        className="sticky left-0 z-30 shrink-0 border-r border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-800"
        style={{ width: LABEL_WIDTH }}
      >
        <div className="px-3 py-1 text-[10px] font-extrabold uppercase tracking-wider text-gray-600 dark:text-gray-400">Title</div>
      </div>
      <div className="relative" style={{ width: totalYears * pxPerYear, minWidth: totalYears * pxPerYear, flexShrink: 0 }}>
        {Array.from({ length: Math.floor(totalYears / tickStep) + 1 }, (_, i) => {
          const y = startYear + i * tickStep;
          return (
            <div
              key={i}
              className="absolute top-0 bottom-0 border-l border-gray-300 dark:border-gray-700 px-1 text-[10px] text-gray-600 dark:text-gray-400"
              style={{ left: i * tickStep * pxPerYear }}
            >
              {y}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// A gap >100yr may be ruled by multiple dynasties in sequence (one extra slot per
// additional 100 years). The gap width is split evenly among the visible slots.
function GapSlots({ gap, assigned, dynastyOptions, onAssign, width }) {
  const gapLen = gap.end - gap.start;
  const maxDyn = 1 + Math.floor((gapLen - 1) / 100);
  const slotCount = Math.min(maxDyn, assigned.length + 1);
  const slotW = Math.max(width / slotCount, 80);

  const change = (i, val) => {
    const ids = [...assigned];
    if (i < ids.length) {
      if (val) ids[i] = val; else ids.splice(i, 1);
    } else if (val) {
      ids.push(val);
    }
    onAssign(gap.start, gap.end, ids);
  };

  return (
    <>
      {Array.from({ length: slotCount }, (_, i) => (
        <select
          key={i}
          value={assigned[i] || ''}
          onChange={(e) => change(i, e.target.value)}
          title={`Gap ${gap.start}–${gap.end} (${gapLen} yrs)${maxDyn > 1 ? ` — up to ${maxDyn} dynasties` : ''} — assign a dynasty to generate rulers here`}
          className="absolute bg-amber-50 dark:bg-amber-950/40 text-amber-900 dark:text-amber-200 border border-dashed border-amber-500 dark:border-amber-600 text-[11px] px-1 focus:outline-none focus:border-amber-700 cursor-pointer truncate"
          style={{ left: i * slotW, top: 8, width: slotW - 2, height: ROW_HEIGHT - 16 }}
        >
          <option value="">{assigned.length === 0 ? '— gap: assign dynasty —' : '+ dynasty'}</option>
          {dynastyOptions.map((d) => (
            <option key={d.id} value={d.id}>{d.name || d.id}</option>
          ))}
        </select>
      ))}
    </>
  );
}

function TitleLane({ row, events, startYear, endYear, pxPerYear, gapFills, dynastyOptions, onAssign }) {
  const totalYears = endYear - startYear;
  const { occupied, gaps } = useMemo(
    () => computeSegments(events, startYear, endYear),
    [events, startYear, endYear],
  );
  const xOf = (year) => (year - startYear) * pxPerYear;
  const assignedFor = (g) => {
    const hit = (gapFills || []).find((f) => f.gap_start_year === g.start && f.gap_end_year === g.end);
    return hit ? (hit.dynasty_ids || []) : [];
  };

  return (
    <div className="flex border-b border-gray-300 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800" style={{ height: ROW_HEIGHT }}>
      <div
        className="sticky left-0 z-10 shrink-0 flex items-center pr-3 border-r border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 text-xs"
        style={{ width: LABEL_WIDTH, paddingLeft: 12 }}
      >
        <span className="truncate text-black dark:text-white">{row.id}</span>
        <span className="ml-2 text-[10px] text-gray-500 uppercase">{row.tier[0]}</span>
        {gaps.length > 0 && (
          <span className="ml-auto text-[10px] text-amber-600 dark:text-amber-400 shrink-0" title="Fillable gaps (>50yr)">{gaps.length} gap{gaps.length > 1 ? 's' : ''}</span>
        )}
      </div>

      <div className="relative bg-white dark:bg-gray-900" style={{ width: totalYears * pxPerYear, minWidth: totalYears * pxPerYear, flexShrink: 0 }}>
        {/* decade gridlines */}
        {Array.from({ length: Math.floor(totalYears / 10) + 1 }, (_, i) => (
          <div key={`g${i}`} className="absolute top-0 bottom-0 border-l border-gray-100 dark:border-gray-800" style={{ left: i * 10 * pxPerYear }} />
        ))}

        {/* locked existing-history bars (read-only) */}
        {occupied.map((o, i) => {
          const w = Math.max((o.end - o.start) * pxPerYear, 3);
          return (
            <div
              key={`o${i}`}
              className="absolute bg-gray-300 dark:bg-gray-700 border border-gray-400 dark:border-gray-600 flex items-center justify-center overflow-hidden cursor-not-allowed"
              style={{ left: xOf(o.start), top: 8, width: w, height: ROW_HEIGHT - 16 }}
              title={`Existing history ${o.start}–${o.end} (locked)`}
            >
              {w > 64 && <span className="text-[10px] text-gray-600 dark:text-gray-300 italic px-1 truncate">existing</span>}
            </div>
          );
        })}

        {/* editable gaps (>50yr) with per-gap dynasty assignment */}
        {gaps.map((g, i) => (
          <div key={`gap${i}`} className="absolute" style={{ left: xOf(g.start), top: 0, width: (g.end - g.start) * pxPerYear, height: ROW_HEIGHT }}>
            <GapSlots
              gap={g}
              assigned={assignedFor(g)}
              dynastyOptions={dynastyOptions}
              onAssign={(s, e, ids) => onAssign(row.id, s, e, ids)}
              width={(g.end - g.start) * pxPerYear}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function GanttChart() {
  const { parsed_files, global_settings, title_gap_fills, setTitleGapFillDynasties, dynasty_definitions } = useStore();
  const [pxPerYear, setPxPerYear] = useState(6);
  const [filter, setFilter] = useState('');

  const titles = parsed_files.titles;
  const holderEvents = parsed_files.title_holder_events || {};
  const rows = useMemo(
    () => (titles || []).map((id) => ({ id, tier: TIER_FROM_PREFIX[id.slice(0, 2)] ?? 'unknown' })),
    [titles],
  );
  const visibleRows = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return q ? rows.filter((r) => r.id.toLowerCase().includes(q)) : rows;
  }, [rows, filter]);
  const totalYears = Math.max(1, global_settings.end_year - global_settings.start_year);

  const containerRef = useRef(null);
  useLayoutEffect(() => {
    if (!containerRef.current) return undefined;
    const compute = () => {
      const containerWidth = containerRef.current?.clientWidth ?? 0;
      const available = containerWidth - LABEL_WIDTH;
      if (available <= 0 || totalYears <= 0) return;
      setPxPerYear(Math.max(MIN_PX_PER_YEAR, Math.min(MAX_PX_PER_YEAR, available / totalYears)));
    };
    compute();
    const ro = new ResizeObserver(compute);
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, [totalYears]);

  if (!titles || titles.length === 0) {
    return (
      <div className="p-12 text-sm text-gray-600 dark:text-gray-400 italic">
        {global_settings.ignore_title_generation
          ? 'Skip Title History is on — no title_history.txt will be generated. Dynasties you define still produce character histories. Upload a title history file only if you want to fill gaps in existing title histories.'
          : 'Upload a title history file in the sidebar to start filling gaps in existing title histories.'}
      </div>
    );
  }

  const hasDynasties = dynasty_definitions.length > 0;
  const contentWidth = LABEL_WIDTH + totalYears * pxPerYear;

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <input
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter titles…"
          className="w-64 bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 px-3 py-1.5 text-sm text-black dark:text-white focus:outline-none focus:border-black dark:focus:border-white"
        />
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {filter ? `${visibleRows.length} of ${rows.length}` : `${rows.length} titles`}
        </span>
        <span className="ml-auto flex items-center gap-3 text-[11px] text-gray-500 dark:text-gray-400">
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 bg-gray-300 dark:bg-gray-700 border border-gray-400 dark:border-gray-600" /> existing (locked)</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 bg-amber-50 dark:bg-amber-950/40 border border-dashed border-amber-500" /> fillable gap (&gt;50yr)</span>
        </span>
      </div>

      {!hasDynasties && (
        <p className="mb-2 text-[11px] text-amber-600 dark:text-amber-400">
          Define dynasties in Global Settings to assign them to gaps below.
        </p>
      )}

      <div
        ref={containerRef}
        className="border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 overflow-auto"
        style={{ maxHeight: '70vh' }}
      >
        <div style={{ minWidth: contentWidth }}>
          <YearRuler startYear={global_settings.start_year} endYear={global_settings.end_year} pxPerYear={pxPerYear} />
          {visibleRows.length === 0 && (
            <div className="px-4 py-6 text-sm italic text-gray-500 dark:text-gray-400">No titles match “{filter}”.</div>
          )}
          {visibleRows.map((row) => (
            <TitleLane
              key={row.id}
              row={row}
              events={holderEvents[row.id]}
              startYear={global_settings.start_year}
              endYear={global_settings.end_year}
              pxPerYear={pxPerYear}
              gapFills={title_gap_fills[row.id]}
              dynastyOptions={dynasty_definitions}
              onAssign={setTitleGapFillDynasties}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
