import { useState, useRef, useEffect, useMemo, useLayoutEffect } from 'react';
import { useStore } from '../store';

const ROW_HEIGHT = 48;
const LABEL_WIDTH = 240;
const BTN_COL_WIDTH = 140;
const MIN_PX_PER_YEAR = 2;
const MAX_PX_PER_YEAR = 20;
const GAP_DYNASTY_ID = '__gap__';
const TRANSITION_LABELS = {
  marriage: 'Marriage',
  usurpation: 'Usurpation',
  extinction: 'Extinction',
};

const TIER_FROM_PREFIX = { h_: 'hegemony', e_: 'empire', k_: 'kingdom', d_: 'duchy', c_: 'county', b_: 'barony' };

function titlesToRows(titleIds) {
  return titleIds.map((id) => ({
    id,
    depth: 0,
    tier: TIER_FROM_PREFIX[id.slice(0, 2)] ?? 'unknown',
    is_landed: true,
    has_children: false,
  }));
}

function DynastyBlock({
  sequence, pxPerYear, onResize, onChangeTransition, onChangeDynasty, dynastyOptions,
  onMoveStart, isBeingMoved, isDragTarget, onRemove, index,
}) {
  const startX = (sequence._start_offset || 0) * pxPerYear;
  const widthYears = sequence.duration_type === 'years'
    ? sequence.duration_value
    : sequence.duration_value * 25;
  const width = Math.max(widthYears * pxPerYear, 40);

  const isGap = sequence.dynasty_id === GAP_DYNASTY_ID;

  const [resizing, setResizing] = useState(false);
  const resizeRef = useRef(null);

  const onResizeDown = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setResizing(true);
    resizeRef.current = { x: e.clientX, durationYears: widthYears };
  };

  useEffect(() => {
    if (!resizing) return;
    const onMove = (e) => {
      const dx = e.clientX - resizeRef.current.x;
      const newYears = Math.max(5, Math.round(resizeRef.current.durationYears + dx / pxPerYear));
      const newValue = sequence.duration_type === 'years'
        ? newYears
        : Math.max(1, Math.round(newYears / 25));
      onResize(newValue);
    };
    const onUp = () => setResizing(false);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [resizing, sequence.duration_type, onResize, pxPerYear]);

  return (
    <div
      className={[
        'absolute border flex items-center text-xs',
        isGap
          ? 'bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500 border-gray-400 dark:border-gray-600 border-dashed'
          : 'bg-gray-800 text-white border-gray-700',
        isBeingMoved ? 'opacity-40' : '',
        isDragTarget && !isBeingMoved ? 'ring-2 ring-blue-400' : '',
      ].join(' ')}
      style={{ left: startX, top: 8, width, height: ROW_HEIGHT - 16 }}
    >
      <div
        onMouseDown={(e) => { e.preventDefault(); e.stopPropagation(); onMoveStart(e); }}
        className="shrink-0 flex items-center justify-center w-4 self-stretch cursor-grab active:cursor-grabbing select-none text-[10px] opacity-50 hover:opacity-100"
        title="Drag to reorder or move to another title"
      >
        ⠿
      </div>

      {isGap ? (
        <>
          <div className="flex-1 text-center text-[10px] italic truncate">vacant</div>
          <div className="text-gray-400 dark:text-gray-500 ml-1 text-[10px] shrink-0">
            {sequence.duration_value}{sequence.duration_type === 'years' ? 'y' : 'g'}
          </div>
        </>
      ) : (
        <>
          {dynastyOptions && dynastyOptions.length > 0 ? (
            <select
              value={sequence.dynasty_id}
              onChange={(e) => { e.stopPropagation(); onChangeDynasty(e.target.value); }}
              onMouseDown={(e) => e.stopPropagation()}
              onClick={(e) => e.stopPropagation()}
              className="flex-1 min-w-0 bg-gray-700 text-white text-xs border-0 focus:outline-none truncate cursor-pointer"
              style={{ maxWidth: width - 60 }}
            >
              <option value={GAP_DYNASTY_ID}>— No Holder —</option>
              {!dynastyOptions.find((o) => o.id === sequence.dynasty_id) && (
                <option value={sequence.dynasty_id}>{sequence.dynasty_id}</option>
              )}
              {dynastyOptions.map((d) => (
                <option key={d.id} value={d.id}>{d.name || d.id}</option>
              ))}
            </select>
          ) : (
            <div className="truncate font-extrabold flex-1">{sequence.dynasty_id}</div>
          )}
          <div className="text-gray-300 ml-2 text-[10px] shrink-0">
            {sequence.duration_value}{sequence.duration_type === 'years' ? 'y' : 'g'}
          </div>
        </>
      )}
      <button
        onMouseDown={(e) => e.stopPropagation()}
        onClick={(e) => { e.stopPropagation(); onRemove(); }}
        className="shrink-0 flex items-center justify-center w-5 self-stretch mr-2 text-gray-400 hover:text-red-400 text-[13px] leading-none cursor-pointer relative z-10"
        title="Remove block"
      >×</button>
      <div
        onMouseDown={onResizeDown}
        className={[
          'absolute right-0 top-0 bottom-0 w-2 cursor-ew-resize',
          isGap ? 'bg-gray-300 dark:bg-gray-600 hover:bg-gray-400 dark:hover:bg-gray-500' : 'bg-gray-600 hover:bg-gray-500',
        ].join(' ')}
      />
      {index >= 0 && !isGap && (
        <button
          onMouseDown={(e) => e.stopPropagation()}
          onClick={(e) => { e.stopPropagation(); onChangeTransition(); }}
          className="absolute -right-3 top-1/2 -translate-y-1/2 w-3 h-3 bg-white dark:bg-gray-800 border-2 border-gray-600 dark:border-gray-500 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700"
          title={`Transition: ${TRANSITION_LABELS[sequence.transition_method] ?? 'None'}`}
        />
      )}
    </div>
  );
}

function GanttRow({
  row, sequences, pxPerYear, totalYears, laneRefMap,
  onResize, onChangeTransition, onChangeDynasty, onRemoveBlock, onStartMove,
  dragState, dragPreview, dynastyOptions,
}) {
  const positioned = useMemo(() => {
    if (!sequences) return [];
    let offset = 0;
    return sequences.map((seq) => {
      const yrs = seq.duration_type === 'years' ? seq.duration_value : seq.duration_value * 25;
      const placed = { ...seq, _start_offset: offset };
      offset += yrs;
      return placed;
    });
  }, [sequences]);

  const laneRef = useRef(null);
  useLayoutEffect(() => {
    laneRefMap.current.set(row.id, laneRef);
    return () => { laneRefMap.current.delete(row.id); };
  }, [row.id, laneRefMap]);

  const isTargetRow = dragState && dragState.toTitleId === row.id;
  const isSourceRow = dragState && dragState.fromTitleId === row.id;

  return (
    <div
      className={[
        'flex border-b border-gray-300 dark:border-gray-700',
        isTargetRow && !isSourceRow ? 'bg-blue-50 dark:bg-blue-950/30' : 'hover:bg-gray-50 dark:hover:bg-gray-800',
      ].join(' ')}
      style={{ height: ROW_HEIGHT }}
    >
      <div
        className="sticky left-0 z-10 shrink-0 flex items-center pr-3 border-r border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 text-xs"
        style={{ width: LABEL_WIDTH, paddingLeft: 12 + row.depth * 16 }}
      >
        <span className="w-5" />
        <span className={['truncate', row.is_landed ? 'text-black dark:text-white' : 'text-gray-600 dark:text-gray-400 italic'].join(' ')}>
          {row.id}
        </span>
        <span className="ml-2 text-[10px] text-gray-500 dark:text-gray-500 uppercase">{row.tier[0]}</span>
      </div>

      <div
        ref={laneRef}
        data-title-id={row.id}
        className="relative bg-white dark:bg-gray-900"
        style={{ width: totalYears * pxPerYear, minWidth: totalYears * pxPerYear, flexShrink: 0 }}
      >
        {Array.from({ length: Math.floor(totalYears / 10) + 1 }, (_, i) => (
          <div
            key={`${row.id}-grid-${i}`}
            className="absolute top-0 bottom-0 border-l border-gray-100 dark:border-gray-800"
            style={{ left: i * 10 * pxPerYear }}
          />
        ))}

        {positioned.map((seq, i) => {
          const isBeingMoved = dragState && dragState.fromTitleId === row.id && dragState.fromIdx === i;
          return (
            <DynastyBlock
              key={i}
              sequence={seq}
              index={i}
              pxPerYear={pxPerYear}
              onResize={(newVal) => onResize(row.id, i, newVal)}
              onChangeTransition={() => onChangeTransition(row.id, i)}
              onChangeDynasty={(newId) => onChangeDynasty(row.id, i, newId)}
              onRemove={() => onRemoveBlock(row.id, i)}
              onMoveStart={(e) => onStartMove(row.id, i, e)}
              isBeingMoved={isBeingMoved}
              isDragTarget={false}
              dynastyOptions={dynastyOptions}
            />
          );
        })}

        {dragPreview && dragPreview.titleId === row.id && (
          <div
            className="absolute border-2 border-dashed border-blue-400 bg-blue-200/40 dark:bg-blue-500/20 pointer-events-none"
            style={{
              left: dragPreview.offsetYears * pxPerYear,
              top: 8,
              width: Math.max(dragPreview.widthYears * pxPerYear, 40),
              height: ROW_HEIGHT - 16,
            }}
            data-testid="drag-preview"
          />
        )}
      </div>
    </div>
  );
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
      <div
        className="relative"
        style={{ width: totalYears * pxPerYear, minWidth: totalYears * pxPerYear, flexShrink: 0 }}
      >
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
      <div
        className="sticky right-0 z-30 shrink-0 border-l border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800"
        style={{ width: BTN_COL_WIDTH }}
      />
    </div>
  );
}

function TransitionPopover({ open, onClose, current, onSelect }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 p-5 min-w-[280px]" onClick={(e) => e.stopPropagation()}>
        <div className="text-xs font-extrabold uppercase tracking-wider text-gray-600 dark:text-gray-400 mb-3">Transition Type</div>
        {Object.entries(TRANSITION_LABELS).map(([key, label]) => (
          <button
            key={key}
            onClick={() => { onSelect(key); onClose(); }}
            className={[
              'block w-full text-left px-3 py-2 mb-1 text-sm border',
              current === key
                ? 'bg-black dark:bg-white text-white dark:text-black border-black dark:border-white'
                : 'bg-white dark:bg-gray-700 text-black dark:text-white border-gray-300 dark:border-gray-600 hover:border-black dark:hover:border-white',
            ].join(' ')}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function GanttChart() {
  const {
    parsed_files, global_settings, title_sequences,
    setSequences, reorderBlock, moveBlockToTitle, dynasty_definitions,
  } = useStore();
  const [popover, setPopover] = useState(null);
  const [dragState, setDragState] = useState(null);
  const [pxPerYear, setPxPerYear] = useState(6);
  const [filter, setFilter] = useState('');

  const titles = parsed_files.titles;
  const rows = useMemo(() => titlesToRows(titles || []), [titles]);
  const visibleRows = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return q ? rows.filter((r) => r.id.toLowerCase().includes(q)) : rows;
  }, [rows, filter]);
  const totalYears = Math.max(1, global_settings.end_year - global_settings.start_year);

  // Predicted drop position for the drag-ghost. Declared with the other hooks
  // (before any early return) so hook order stays stable when titles clear.
  const dragPreview = useMemo(() => {
    if (!dragState) return null;
    const { fromTitleId, fromIdx, toTitleId, toIdx } = dragState;
    const draggedBlock = (title_sequences[fromTitleId] || [])[fromIdx];
    if (!draggedBlock) return null;
    let targetBlocks = [...(title_sequences[toTitleId] || [])];
    if (fromTitleId === toTitleId) {
      targetBlocks.splice(fromIdx, 1);
    }
    const insertAt = Math.max(0, Math.min(toIdx, targetBlocks.length));
    let offsetYears = 0;
    for (let i = 0; i < insertAt; i++) {
      offsetYears += targetBlocks[i].duration_type === 'years'
        ? targetBlocks[i].duration_value
        : targetBlocks[i].duration_value * 25;
    }
    const widthYears = draggedBlock.duration_type === 'years'
      ? draggedBlock.duration_value
      : draggedBlock.duration_value * 25;
    return { titleId: toTitleId, offsetYears, widthYears };
  }, [dragState, title_sequences]);

  const containerRef = useRef(null);
  const laneRefMap = useRef(new Map());

  // Recompute px/year to fit the available chart width.
  useLayoutEffect(() => {
    if (!containerRef.current) return;
    const compute = () => {
      const containerWidth = containerRef.current?.clientWidth ?? 0;
      const available = containerWidth - LABEL_WIDTH - BTN_COL_WIDTH;
      if (available <= 0 || totalYears <= 0) return;
      const next = Math.max(MIN_PX_PER_YEAR, Math.min(MAX_PX_PER_YEAR, available / totalYears));
      setPxPerYear(next);
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
          ? 'Skip Title History is on — no title_history.txt will be generated. Dynasties you define still produce character histories. Upload a title history file only if you want to configure title sequences here.'
          : 'Upload a title history file in the sidebar to start configuring title histories.'}
      </div>
    );
  }

  const addBlock = (titleId) => {
    const existing = title_sequences[titleId] || [];
    const defaultDynastyId = dynasty_definitions.length > 0
      ? dynasty_definitions[0].id
      : `dynasty_${titleId}_${existing.length + 1}`;
    setSequences(titleId, [
      ...existing,
      { dynasty_id: defaultDynastyId, duration_type: 'years', duration_value: 50, transition_method: 'marriage' },
    ]);
  };

  const addGap = (titleId) => {
    const existing = title_sequences[titleId] || [];
    setSequences(titleId, [
      ...existing,
      { dynasty_id: GAP_DYNASTY_ID, duration_type: 'years', duration_value: 25, transition_method: 'extinction' },
    ]);
  };

  const onResize = (titleId, idx, newDuration) => {
    const seqs = [...(title_sequences[titleId] || [])];
    const otherYears = seqs.reduce((sum, s, i) => {
      if (i === idx) return sum;
      return sum + (s.duration_type === 'years' ? s.duration_value : s.duration_value * 25);
    }, 0);
    const maxYears = Math.max(5, totalYears - otherYears);
    const newYears = seqs[idx].duration_type === 'years' ? newDuration : newDuration * 25;
    const clampedYears = Math.min(newYears, maxYears);
    const clampedValue = seqs[idx].duration_type === 'years'
      ? clampedYears
      : Math.max(1, Math.round(clampedYears / 25));
    seqs[idx] = { ...seqs[idx], duration_value: clampedValue };
    setSequences(titleId, seqs);
  };

  const onRemoveBlock = (titleId, idx) => {
    const seqs = [...(title_sequences[titleId] || [])];
    seqs.splice(idx, 1);
    setSequences(titleId, seqs);
  };

  const onChangeDynasty = (titleId, idx, newDynastyId) => {
    const seqs = [...(title_sequences[titleId] || [])];
    seqs[idx] = { ...seqs[idx], dynasty_id: newDynastyId };
    setSequences(titleId, seqs);
  };

  const onChangeTransition = (titleId, idx) => setPopover({ titleId, idx });

  const applyTransition = (method) => {
    if (!popover) return;
    const { titleId, idx } = popover;
    const seqs = [...(title_sequences[titleId] || [])];
    seqs[idx] = { ...seqs[idx], transition_method: method };
    setSequences(titleId, seqs);
  };

  // Drag handler — supports both in-row reorder and cross-row move.
  const onStartMove = (fromTitleId, fromIdx) => {
    let current = { fromTitleId, fromIdx, toTitleId: fromTitleId, toIdx: fromIdx };
    setDragState(current);

    const computeTarget = (clientX, clientY) => {
      // Find the row whose lane contains clientY.
      let targetTitleId = null;
      let targetLaneRect = null;
      for (const [tid, ref] of laneRefMap.current.entries()) {
        const el = ref.current;
        if (!el) continue;
        const r = el.getBoundingClientRect();
        if (clientY >= r.top && clientY <= r.bottom) {
          targetTitleId = tid;
          targetLaneRect = r;
          break;
        }
      }
      if (!targetTitleId || !targetLaneRect) return;

      const blocks = title_sequences[targetTitleId] || [];
      const isSameRow = targetTitleId === fromTitleId;
      const blocksForCalc = isSameRow ? blocks : blocks;
      const relX = clientX - targetLaneRect.left;

      let toIdx = blocksForCalc.length;
      let cum = 0;
      for (let i = 0; i < blocksForCalc.length; i++) {
        if (isSameRow && i === fromIdx) {
          cum += blocksForCalc[i].duration_type === 'years' ? blocksForCalc[i].duration_value : blocksForCalc[i].duration_value * 25;
          continue;
        }
        const dur = blocksForCalc[i].duration_type === 'years'
          ? blocksForCalc[i].duration_value
          : blocksForCalc[i].duration_value * 25;
        const midPx = (cum + dur / 2) * pxPerYear;
        if (relX < midPx) { toIdx = i; break; }
        cum += dur;
      }

      if (targetTitleId !== current.toTitleId || toIdx !== current.toIdx) {
        current = { ...current, toTitleId: targetTitleId, toIdx };
        setDragState(current);
      }
    };

    const onMove = (e) => computeTarget(e.clientX, e.clientY);
    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      const { fromTitleId: ft, fromIdx: fi, toTitleId: tt, toIdx: ti } = current;
      setDragState(null);
      if (ft === tt) {
        if (fi !== ti) reorderBlock(ft, fi, ti);
      } else {
        moveBlockToTitle(ft, fi, tt, ti);
      }
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };

  const popoverSeq = popover && (title_sequences[popover.titleId] || [])[popover.idx];
  const contentWidth = LABEL_WIDTH + totalYears * pxPerYear + BTN_COL_WIDTH;

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
      </div>
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
          <div key={row.id} className="flex">
            <GanttRow
              row={row}
              sequences={title_sequences[row.id]}
              pxPerYear={pxPerYear}
              totalYears={totalYears}
              laneRefMap={laneRefMap}
              onResize={onResize}
              onChangeTransition={onChangeTransition}
              onChangeDynasty={onChangeDynasty}
              onRemoveBlock={onRemoveBlock}
              onStartMove={onStartMove}
              dragState={dragState}
              dragPreview={dragPreview}
              dynastyOptions={dynasty_definitions}
            />
            <div
              className="sticky right-0 z-10 shrink-0 flex items-center justify-center gap-1 border-b border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-1"
              style={{ width: BTN_COL_WIDTH, height: ROW_HEIGHT }}
            >
              <button
                onClick={() => addBlock(row.id)}
                className="text-xs text-gray-600 dark:text-gray-400 hover:text-black dark:hover:text-white border border-gray-300 dark:border-gray-700 hover:border-black dark:hover:border-white px-2 py-1 whitespace-nowrap"
                title="Add dynasty block"
              >
                + Block
              </button>
              <button
                onClick={() => addGap(row.id)}
                className="text-xs text-gray-500 dark:text-gray-500 hover:text-black dark:hover:text-white border border-dashed border-gray-300 dark:border-gray-700 hover:border-black dark:hover:border-white px-2 py-1 whitespace-nowrap"
                title="Add vacant period (no holder)"
              >
                + Gap
              </button>
            </div>
          </div>
          ))}
        </div>
      </div>

      <TransitionPopover
        open={Boolean(popover)}
        onClose={() => setPopover(null)}
        current={popoverSeq?.transition_method}
        onSelect={applyTransition}
      />
    </div>
  );
}

