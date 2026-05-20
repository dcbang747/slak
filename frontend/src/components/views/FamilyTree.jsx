import { useEffect, useState, useMemo } from 'react';
import {
  ReactFlow, Background, Controls, MiniMap,
  useNodesState, useEdgesState, Handle, Position,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useStore } from '../../store';
import { fetchTree } from '../../api';
import { toInGameYear } from '../../yearConvert';

// Display a raw simulation year as its in-game era number, falling back to the
// raw value if it predates the conversion range.
const disp = (y) => toInGameYear(y) || (y ? String(y) : '');

const NODE_W = 190;
const NODE_H = 105;
const H_GAP = 44;
const V_GAP = 100;
const JUNCTION_SIZE = 10;
const V_GAP_JUNCTION = 38; // distance from parent bottom to junction center

// ---------------------------------------------------------------------------
// Node components
// ---------------------------------------------------------------------------

function CharacterNode({ data }) {
  const c = data;
  const borderColor = c.is_female ? 'border-rose-500' : 'border-blue-500';
  const borderStyle = c.is_bastard ? 'border-dashed' : 'border-solid';
  const bgColor = c.is_ruler ? 'bg-amber-50 dark:bg-amber-950' : 'bg-white dark:bg-gray-800';
  const birthYear = c.birth_date ? c.birth_date.split('.')[0] : '';
  const deathYear = c.death_date ? c.death_date.split('.')[0] : '';
  const age = birthYear && deathYear ? parseInt(deathYear) - parseInt(birthYear) : null;
  return (
    <div className={`${bgColor} ${borderColor} ${borderStyle} border-2 rounded px-2 py-1.5 text-xs select-none shadow-sm`} style={{ width: NODE_W }}>
      <Handle type="target" position={Position.Top}    id="tgt-top" />
      <Handle type="source" position={Position.Left}   id="src-left"  style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Left}   id="tgt-left"  style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Right}  id="src-right" style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Right}  id="tgt-right" style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} id="src-bottom" />
      <div className="font-bold text-black dark:text-white truncate">{c.is_female ? '♀' : '♂'} {c.name}</div>
      <div className="text-gray-400 dark:text-gray-500 font-mono text-[10px] truncate">{c.id}</div>
      {(birthYear || deathYear) && (
        <div className="text-gray-600 dark:text-gray-300 mt-0.5">
          {disp(birthYear) || '?'} – {disp(deathYear) || '…'}{age !== null ? ` (${age})` : ''}
        </div>
      )}
      {c.is_ruler && (
        <div className="text-amber-600 dark:text-amber-400 font-semibold mt-0.5">
          ★ Ruler{c.ruler_order ? ` #${c.ruler_order}` : ''}
        </div>
      )}
      {c.is_ruler && c.ruler_since && (
        <div className="text-amber-600 dark:text-amber-400 text-[10px]">
          Years ruled: {disp(c.ruler_since)} – {disp(deathYear) || '…'}
        </div>
      )}
    </div>
  );
}

function ExternalNode({ data }) {
  const c = data;
  const birthYear = c.birth_date ? c.birth_date.split('.')[0] : '';
  const deathYear = c.death_date ? c.death_date.split('.')[0] : '';
  return (
    <div className="bg-gray-100 dark:bg-gray-700 border border-dashed border-gray-400 dark:border-gray-500 rounded-full px-2 py-1 text-[10px] text-gray-500 dark:text-gray-400 select-none text-center" style={{ width: 140 }}>
      <Handle type="target" position={Position.Top}    id="tgt-top" />
      <Handle type="source" position={Position.Left}   id="src-left"  style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Left}   id="tgt-left"  style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Right}  id="src-right" style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Right}  id="tgt-right" style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} id="src-bottom" />
      <div className="font-semibold truncate">{c.name}</div>
      {(birthYear || deathYear) && <div className="font-mono">{disp(birthYear) || '?'} – {disp(deathYear) || '…'}</div>}
    </div>
  );
}

// Small dot where both parents' lines converge before fanning to children
function JunctionNode() {
  return (
    <div style={{ width: JUNCTION_SIZE, height: JUNCTION_SIZE, borderRadius: '50%', background: '#6b7280', border: '2px solid #4b5563' }}>
      <Handle type="target" position={Position.Left}   id="tgt-left"  style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Right}  id="tgt-right" style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} id="src-bottom" style={{ opacity: 0 }} />
    </div>
  );
}

const NODE_TYPES = { character: CharacterNode, external: ExternalNode, junction: JunctionNode };

// ---------------------------------------------------------------------------
// Generation-based layout
// ---------------------------------------------------------------------------

function assignGenerations(allNodeData) {
  const childrenOf = new Map();
  const inDegree = new Map();
  for (const id of allNodeData.keys()) { childrenOf.set(id, []); inDegree.set(id, 0); }
  for (const [id, c] of allNodeData) {
    for (const pid of [c.father_id, c.mother_id]) {
      if (pid && allNodeData.has(pid)) {
        childrenOf.get(pid).push(id);
        inDegree.set(id, inDegree.get(id) + 1);
      }
    }
  }
  const genMap = new Map();
  const queue = [];
  for (const [id, deg] of inDegree) {
    if (deg === 0) { queue.push(id); genMap.set(id, 0); }
  }
  let head = 0;
  while (head < queue.length) {
    const id = queue[head++];
    const gen = genMap.get(id);
    for (const childId of childrenOf.get(id)) {
      if (!genMap.has(childId) || genMap.get(childId) < gen + 1) genMap.set(childId, gen + 1);
      const rem = inDegree.get(childId) - 1;
      inDegree.set(childId, rem);
      if (rem === 0) queue.push(childId);
    }
  }
  for (const id of allNodeData.keys()) { if (!genMap.has(id)) genMap.set(id, 0); }
  return genMap;
}

function buildLayout(allNodeData, primaryEntries) {
  const genMap = assignGenerations(allNodeData);

  for (let pass = 0; pass < 20; pass++) {
    let changed = false;
    for (const [id, c] of primaryEntries) {
      for (const sid of (c.spouse_ids || [])) {
        if (!allNodeData.has(sid)) continue;
        const ga = genMap.get(id) ?? 0;
        const gb = genMap.get(sid) ?? 0;
        if (ga !== gb) { const mx = Math.max(ga, gb); genMap.set(id, mx); genMap.set(sid, mx); changed = true; }
      }
    }
    for (const [id, c] of allNodeData) {
      let maxPGen = -1;
      for (const pid of [c.father_id, c.mother_id]) {
        if (pid && allNodeData.has(pid)) maxPGen = Math.max(maxPGen, genMap.get(pid) ?? 0);
      }
      if (maxPGen >= 0 && (genMap.get(id) ?? 0) <= maxPGen) { genMap.set(id, maxPGen + 1); changed = true; }
    }
    if (!changed) break;
  }

  const genGroups = new Map();
  for (const [id, gen] of genMap) {
    if (!genGroups.has(gen)) genGroups.set(gen, []);
    genGroups.get(gen).push(id);
  }

  const primaryMap = new Map(primaryEntries);
  const posMap = new Map();

  for (const gen of [...genGroups.keys()].sort((a, b) => a - b)) {
    const ids = genGroups.get(gen);
    const ordered = orderWithSpousePairs(ids, allNodeData, primaryMap);
    const totalWidth = ordered.length * (NODE_W + H_GAP) - H_GAP;
    const startX = -(totalWidth / 2);
    const y = gen * (NODE_H + V_GAP);
    ordered.forEach((id, i) => posMap.set(id, { x: startX + i * (NODE_W + H_GAP), y }));
  }

  return posMap;
}

// Primary nodes first (keeps sibling order intact), each pulling their spouse
// adjacent. External nodes that aren't anyone's spouse go at the end.
function orderWithSpousePairs(ids, allNodeData, primaryMap) {
  const idSet = new Set(ids);
  const used = new Set();
  const result = [];

  // Build bidirectional spouse mapping within this generation row
  const spouseOf = new Map();
  for (const id of ids) {
    const c = primaryMap.get(id) || allNodeData.get(id);
    for (const sid of (c?.spouse_ids || [])) {
      if (idSet.has(sid) && !spouseOf.has(id) && !spouseOf.has(sid)) {
        spouseOf.set(id, sid);
        spouseOf.set(sid, id);
        break;
      }
    }
  }

  const primaryFirst = [...ids.filter(id => primaryMap.has(id)), ...ids.filter(id => !primaryMap.has(id))];

  for (const id of primaryFirst) {
    if (used.has(id)) continue;
    result.push(id);
    used.add(id);
    const spouse = spouseOf.get(id);
    if (spouse && !used.has(spouse)) { result.push(spouse); used.add(spouse); }
  }
  return result;
}

// ---------------------------------------------------------------------------
// Graph builder
// ---------------------------------------------------------------------------

function bastardHomeDynasty(c, allChars) {
  // Bastards attach to the father's dynasty; fall back to the mother's if the father has none.
  const father = c.father_id ? allChars[c.father_id] : null;
  if (father?.dynasty) return father.dynasty;
  const mother = c.mother_id ? allChars[c.mother_id] : null;
  return mother?.dynasty || null;
}

// Map char_id → { order, since } where order is the 1-based accession rank within
// the dynasty and since is the year they took the title, derived from the
// chronological title_holders lists (each entry is [date, char_id]).
function computeRulerInfo(treeData) {
  const chars = treeData?.characters || {};
  const holders = treeData?.title_holders || {};
  const byDynasty = {}; // dynasty_id → [{ when, year, id }]
  for (const list of Object.values(holders)) {
    for (const [date, cid] of list) {
      if (!cid || cid === '0') continue;
      const c = chars[cid];
      if (!c) continue;
      const dyn = c.dynasty || bastardHomeDynasty(c, chars);
      if (!dyn) continue;
      const [y, m, day] = String(date || '0.0.0').split('.').map((n) => parseInt(n, 10) || 0);
      (byDynasty[dyn] ||= []).push({ when: y * 10000 + m * 100 + day, year: y, id: cid });
    }
  }
  const info = {};
  for (const events of Object.values(byDynasty)) {
    events.sort((a, b) => a.when - b.when);
    let n = 0;
    const seen = new Set();
    for (const e of events) {
      if (seen.has(e.id)) continue;
      seen.add(e.id);
      info[e.id] = { order: ++n, since: e.year };
    }
  }
  return info;
}

function buildGraph(selectedDynasty, allChars, rulerInfo = {}) {
  const primaryEntries = Object.entries(allChars).filter(([, c]) => {
    if (c.dynasty === selectedDynasty) return true;
    if (c.is_bastard) return bastardHomeDynasty(c, allChars) === selectedDynasty;
    return false;
  });
  const primaryIds = new Set(primaryEntries.map(([id]) => id));

  const externalIds = new Set();
  for (const [, c] of primaryEntries) {
    for (const pid of [c.father_id, c.mother_id]) {
      if (pid && !primaryIds.has(pid) && allChars[pid]) externalIds.add(pid);
    }
  }

  const allNodeData = new Map();
  for (const [id, c] of primaryEntries) allNodeData.set(id, c);
  for (const id of externalIds) allNodeData.set(id, allChars[id]);

  if (allNodeData.size === 0) return { nodes: [], edges: [] };

  const posMap = buildLayout(allNodeData, primaryEntries);

  // --- Junction nodes: one per couple who share at least one child in view ---
  const junctionMap = new Map(); // coupleKey → { id, pos }
  for (const [, c] of primaryEntries) {
    const fId = c.father_id && allNodeData.has(c.father_id) ? c.father_id : null;
    const mId = c.mother_id && allNodeData.has(c.mother_id) ? c.mother_id : null;
    if (!fId || !mId) continue;
    const key = [fId, mId].sort().join('__');
    if (junctionMap.has(key)) continue;
    const fPos = posMap.get(fId);
    const mPos = posMap.get(mId);
    if (!fPos || !mPos) continue;
    // Centre the junction horizontally between the two parent centres, just below their bottom edge
    const jX = (fPos.x + mPos.x) / 2 + NODE_W / 2 - JUNCTION_SIZE / 2;
    const jY = Math.max(fPos.y, mPos.y) + NODE_H + V_GAP_JUNCTION;
    junctionMap.set(key, { id: `junc_${key}`, pos: { x: jX, y: jY } });
  }

  // --- Build React Flow nodes ---
  const nodes = [
    ...Array.from(allNodeData.entries()).map(([id, c]) => ({
      id,
      position: posMap.get(id) ?? { x: 0, y: 0 },
      data: { ...c, id, ruler_order: rulerInfo[id]?.order, ruler_since: rulerInfo[id]?.since },
      type: primaryIds.has(id) ? 'character' : 'external',
      draggable: true,
    })),
    ...Array.from(junctionMap.values()).map(({ id, pos }) => ({
      id, position: pos, data: {}, type: 'junction', draggable: false,
    })),
  ];

  // --- Build edges ---
  const edges = [];
  const seenSpouse = new Set();
  const seenChild = new Set();

  for (const [id, c] of primaryEntries) {
    const fId = c.father_id && allNodeData.has(c.father_id) ? c.father_id : null;
    const mId = c.mother_id && allNodeData.has(c.mother_id) ? c.mother_id : null;

    if (fId && mId) {
      // Both parents visible — route child through junction
      const jInfo = junctionMap.get([fId, mId].sort().join('__'));
      if (jInfo && !seenChild.has(`${jInfo.id}__${id}`)) {
        seenChild.add(`${jInfo.id}__${id}`);
        edges.push({
          id: `pc_${jInfo.id}_${id}`,
          source: jInfo.id, target: id,
          sourceHandle: 'src-bottom', targetHandle: 'tgt-top',
          type: 'smoothstep',
          style: { stroke: '#6b7280', strokeWidth: 1.5 },
        });
      }
    } else if (fId && !seenChild.has(`${fId}__${id}`)) {
      seenChild.add(`${fId}__${id}`);
      edges.push({
        id: `pc_${fId}_${id}`,
        source: fId, target: id,
        sourceHandle: 'src-bottom', targetHandle: 'tgt-top',
        type: 'smoothstep', style: { stroke: '#6b7280', strokeWidth: 1.5 },
      });
    } else if (mId && !seenChild.has(`${mId}__${id}`)) {
      seenChild.add(`${mId}__${id}`);
      edges.push({
        id: `pc_${mId}_${id}`,
        source: mId, target: id,
        sourceHandle: 'src-bottom', targetHandle: 'tgt-top',
        type: 'smoothstep', style: { stroke: '#6b7280', strokeWidth: 1.5 },
      });
    }

    // Spouse edges — horizontal between side handles
    for (const sid of (c.spouse_ids || [])) {
      if (!allNodeData.has(sid)) continue;
      const key = [id, sid].sort().join('__');
      if (seenSpouse.has(key)) continue;
      seenSpouse.add(key);
      const srcPos = posMap.get(id);
      const tgtPos = posMap.get(sid);
      const srcHandle = srcPos && tgtPos && srcPos.x > tgtPos.x ? 'src-left' : 'src-right';
      const tgtHandle = srcPos && tgtPos && srcPos.x > tgtPos.x ? 'tgt-right' : 'tgt-left';
      edges.push({
        id: `spouse_${key}`,
        source: id, target: sid,
        sourceHandle: srcHandle, targetHandle: tgtHandle,
        type: 'straight',
        style: { stroke: '#f43f5e', strokeWidth: 2.5 },
        markerEnd: undefined,
      });
    }
  }

  // Junction ← parents: two converging lines from parent bottoms to junction sides
  for (const [key, jInfo] of junctionMap) {
    const [id1, id2] = key.split('__');
    const p1 = posMap.get(id1);
    const p2 = posMap.get(id2);
    const leftId  = p1 && p2 && p1.x <= p2.x ? id1 : id2;
    const rightId = p1 && p2 && p1.x <= p2.x ? id2 : id1;
    edges.push({
      id: `junc_L_${key}`,
      source: leftId,  target: jInfo.id,
      sourceHandle: 'src-bottom', targetHandle: 'tgt-left',
      type: 'smoothstep', style: { stroke: '#6b7280', strokeWidth: 1.5 },
    });
    edges.push({
      id: `junc_R_${key}`,
      source: rightId, target: jInfo.id,
      sourceHandle: 'src-bottom', targetHandle: 'tgt-right',
      type: 'smoothstep', style: { stroke: '#6b7280', strokeWidth: 1.5 },
    });
  }

  return { nodes, edges };
}

// ---------------------------------------------------------------------------
// Stats / Legend
// ---------------------------------------------------------------------------

function StatsPanel({ dynasty, allChars }) {
  const members = Object.entries(allChars).filter(([, c]) => {
    if (c.dynasty === dynasty) return true;
    if (c.is_bastard) return bastardHomeDynasty(c, allChars) === dynasty;
    return false;
  }).map(([, c]) => c);
  return (
    <div className="absolute top-3 right-3 z-10 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded shadow-sm px-3 py-2 text-xs text-gray-600 dark:text-gray-400 pointer-events-none">
      <div className="font-extrabold uppercase tracking-wide text-black dark:text-white mb-1">Stats</div>
      <div>Members: <span className="font-semibold text-black dark:text-white">{members.length}</span></div>
      <div>Males: <span className="text-blue-600 dark:text-blue-400 font-semibold">{members.filter(c => !c.is_female).length}</span> / Females: <span className="text-rose-500 font-semibold">{members.filter(c => c.is_female).length}</span></div>
      <div>Rulers: <span className="text-amber-600 dark:text-amber-400 font-semibold">{members.filter(c => c.is_ruler).length}</span></div>
    </div>
  );
}

function Legend() {
  return (
    <div className="absolute top-3 left-3 z-10 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded shadow-sm px-3 py-2 text-[10px] text-gray-500 dark:text-gray-400 pointer-events-none space-y-0.5">
      <div className="font-extrabold uppercase tracking-wide text-black dark:text-white mb-1">Legend</div>
      <div className="flex items-center gap-1.5"><span className="inline-block w-3 h-3 border-2 border-blue-500 border-solid rounded-sm" /> Male</div>
      <div className="flex items-center gap-1.5"><span className="inline-block w-3 h-3 border-2 border-rose-500 border-solid rounded-sm" /> Female</div>
      <div className="flex items-center gap-1.5"><span className="inline-block w-3 h-3 bg-amber-50 dark:bg-amber-950 border border-gray-400 rounded-sm" /> Ruler</div>
      <div className="flex items-center gap-1.5"><span className="inline-block w-3 h-3 border-2 border-gray-400 border-dashed rounded-sm" /> Bastard</div>
      <div className="flex items-center gap-1.5"><span className="inline-block w-3 h-3 border border-dashed border-gray-400 rounded-full" /> External parent</div>
      <div className="flex items-center gap-1.5"><span className="inline-block w-8 border-t-2 border-gray-400" /> Parent→Child</div>
      <div className="flex items-center gap-1.5"><span className="inline-block w-8 border-t-2 border-rose-400" /> Spouse</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Canvas
// ---------------------------------------------------------------------------

function TreeCanvas({ dynasty, allChars, rulerInfo, darkMode }) {
  const { nodes: initialNodes, edges: initialEdges } = useMemo(
    () => buildGraph(dynasty, allChars, rulerInfo), [dynasty, allChars, rulerInfo]
  );
  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);
  return (
    <div className="relative flex-1 min-h-0">
      <StatsPanel dynasty={dynasty} allChars={allChars} />
      <Legend />
      <ReactFlow
        nodes={nodes} edges={edges}
        onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
        nodeTypes={NODE_TYPES}
        fitView fitViewOptions={{ padding: 0.15 }}
        minZoom={0.05} maxZoom={2}
        colorMode={darkMode ? 'dark' : 'light'}
        style={{ background: darkMode ? '#111827' : '#f9fafb' }}
      >
        <Background color={darkMode ? '#374151' : '#d1d5db'} gap={20} />
        <Controls />
        <MiniMap
          nodeColor={(n) => {
            if (n.type === 'external') return '#9ca3af';
            if (n.type === 'junction') return '#6b7280';
            const c = n.data;
            if (c.is_ruler) return '#f59e0b';
            return c.is_female ? '#f43f5e' : '#3b82f6';
          }}
          style={{ background: darkMode ? '#1f2937' : '#f3f4f6' }}
        />
      </ReactFlow>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main view
// ---------------------------------------------------------------------------

export default function FamilyTree() {
  const { task_id, tree_data, setTreeData, dark_mode } = useStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedDynasty, setSelectedDynasty] = useState(null);

  useEffect(() => {
    if (tree_data || !task_id) return;
    setLoading(true);
    fetchTree(task_id)
      .then((data) => { setTreeData(data); setLoading(false); })
      .catch((err) => { setError(err.message); setLoading(false); });
  }, [task_id, tree_data, setTreeData]);

  const dynastyTabs = useMemo(() => {
    if (!tree_data?.characters) return [];
    const seen = new Set();
    const tabs = [];
    for (const c of Object.values(tree_data.characters)) {
      if (c.dynasty && !seen.has(c.dynasty)) { seen.add(c.dynasty); tabs.push(c.dynasty); }
    }
    return tabs.sort();
  }, [tree_data]);

  const rulerInfo = useMemo(() => computeRulerInfo(tree_data), [tree_data]);

  useEffect(() => {
    if (dynastyTabs.length > 0 && !selectedDynasty) setSelectedDynasty(dynastyTabs[0]);
  }, [dynastyTabs, selectedDynasty]);

  if (loading) return <div className="flex items-center justify-center h-full text-gray-500 dark:text-gray-400">Loading family tree…</div>;
  if (error) return <div className="flex items-center justify-center h-full text-red-500 dark:text-red-400">Failed to load tree: {error}</div>;
  if (!tree_data) return <div className="flex items-center justify-center h-full text-gray-400 dark:text-gray-500">No tree data available.</div>;

  return (
    <div className="flex flex-col h-full -m-8">
      <div className="flex gap-0 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-4 pt-3 overflow-x-auto shrink-0">
        {dynastyTabs.map((d) => (
          <button key={d} onClick={() => setSelectedDynasty(d)}
            className={['px-4 py-2 text-xs font-extrabold uppercase tracking-wide border-b-2 whitespace-nowrap transition-colors',
              selectedDynasty === d ? 'border-black dark:border-white text-black dark:text-white'
                : 'border-transparent text-gray-400 dark:text-gray-500 hover:text-black dark:hover:text-white'].join(' ')}>
            {d}
          </button>
        ))}
      </div>
      {selectedDynasty && (
        <TreeCanvas key={selectedDynasty} dynasty={selectedDynasty} allChars={tree_data.characters} rulerInfo={rulerInfo} darkMode={dark_mode} />
      )}
    </div>
  );
}
