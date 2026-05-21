import { useEffect, useState } from 'react';
import { useStore } from '../store';

// Each step points at a `data-tour="..."` anchor somewhere in the app. Steps with
// a `view` switch the center workspace to that view first. `optional` steps still
// show their popup (centered) when the anchor isn't on screen yet.
const STEPS = [
  {
    sel: '[data-tour="namelist"]',
    title: 'Add a Name List',
    body: 'Upload a CK3 name_list file here. Generated characters draw their first names from these pools. This (plus a dynasty) is the minimum needed to generate.',
  },
  {
    sel: '[data-tour="culture"]',
    title: 'Add Cultures',
    body: 'Optional. Upload culture files to populate the culture dropdown shown on each dynasty card.',
  },
  {
    sel: '[data-tour="religion"]',
    title: 'Add Religions',
    body: 'Optional. Upload religion files so faiths (and their marital doctrines) are selectable per dynasty.',
  },
  {
    sel: '[data-tour="skip-title"]',
    title: 'Title History',
    body: 'Upload a title-history file to drive succession on real titles — or tick “Skip Title History” to generate characters under placeholder titles only.',
    view: 'global',
  },
  {
    sel: '[data-tour="add-dynasty"]',
    title: 'Create a Dynasty',
    body: 'Add at least one dynasty, then set its culture, faith, succession, and other properties. Its ID is referenced by the Title Histories Gantt chart.',
    view: 'global',
  },
  {
    sel: '[data-tour="generate"]',
    title: 'Generate Simulation',
    body: 'With a name list and a dynasty ready, click here to run the simulation. Progress streams in the right drawer and a download appears when it finishes.',
  },
  {
    sel: '[data-tour="family-tree"]',
    title: 'Family Tree',
    body: 'After a successful run, a Family Tree view appears in the nav — explore the generated characters, rulers, reigns, and relationships visually.',
    optional: true,
  },
];

const PW = 280; // popup width

export default function TutorialOverlay() {
  const enabled = useStore((s) => s.tutorial_enabled);
  const step = useStore((s) => s.tutorial_step);
  const setStep = useStore((s) => s.setTutorialStep);
  const setEnabled = useStore((s) => s.setTutorialEnabled);
  const active_view = useStore((s) => s.active_view);
  const setView = useStore((s) => s.setView);

  const [rect, setRect] = useState(null);
  const current = enabled ? STEPS[step] : null;

  // Switch the center workspace to the view a step needs.
  useEffect(() => {
    if (current?.view && active_view !== current.view) setView(current.view);
  }, [current, active_view, setView]);

  // Track the anchor element's position (re-poll to survive view switches / async layout).
  useEffect(() => {
    if (!current) { setRect(null); return undefined; }
    const update = () => {
      const el = document.querySelector(current.sel);
      if (!el) { setRect(null); return; }
      const r = el.getBoundingClientRect();
      setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
    };
    update();
    const id = setInterval(update, 200);
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => {
      clearInterval(id);
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
    };
  }, [current]);

  if (!current) return null;

  const isLast = step >= STEPS.length - 1;
  const next = () => (isLast ? setEnabled(false) : setStep(step + 1));
  const back = () => setStep(Math.max(0, step - 1));
  const skip = () => setEnabled(false);

  // Place the popup beside the anchor (right → left → below), else centre it.
  let popupStyle;
  let arrow = null;
  const EST_H = 230; // approx popup height for on-screen clamping
  if (rect) {
    const spaceRight = window.innerWidth - (rect.left + rect.width);
    if (spaceRight > PW + 24) {
      popupStyle = { top: rect.top, left: rect.left + rect.width + 16 };
      arrow = { left: -8, borderRight: '8px solid rgb(17,24,39)', borderTop: '8px solid transparent', borderBottom: '8px solid transparent' };
    } else if (rect.left > PW + 24) {
      popupStyle = { top: rect.top, left: rect.left - PW - 16 };
      arrow = { right: -8, borderLeft: '8px solid rgb(17,24,39)', borderTop: '8px solid transparent', borderBottom: '8px solid transparent' };
    } else {
      popupStyle = { top: rect.top + rect.height + 16, left: Math.max(8, Math.min(rect.left, window.innerWidth - PW - 8)) };
      arrow = { top: -8, left: 24, borderBottom: '8px solid rgb(17,24,39)', borderLeft: '8px solid transparent', borderRight: '8px solid transparent' };
    }
    // Keep the popup fully on screen — clamp its top so it never runs off the
    // bottom (e.g. the Generate button near the sidebar's base).
    const unclamped = popupStyle.top;
    popupStyle.top = Math.max(8, Math.min(unclamped, window.innerHeight - EST_H));
    // For side placements, re-aim the arrow at the anchor's vertical centre
    // after any vertical shift so it still points at the highlighted element.
    if (arrow && arrow.top === undefined) {
      arrow.top = Math.max(8, Math.min((rect.top + rect.height / 2) - popupStyle.top - 8, EST_H - 24));
    }
  } else {
    popupStyle = { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' };
  }

  return (
    <div className="fixed inset-0 z-[1000] pointer-events-none">
      {/* Glowing highlight ring around the anchor */}
      {rect && (
        <div
          className="absolute rounded-md animate-pulse"
          style={{
            top: rect.top - 6,
            left: rect.left - 6,
            width: rect.width + 12,
            height: rect.height + 12,
            boxShadow: '0 0 0 3px rgba(245,158,11,0.95), 0 0 20px 6px rgba(245,158,11,0.55)',
          }}
        />
      )}

      {/* Coachmark popup */}
      <div
        className="absolute pointer-events-auto bg-gray-900 text-white rounded-lg shadow-2xl border border-amber-500/40 p-4"
        style={{ width: PW, ...popupStyle }}
      >
        {arrow && <div className="absolute" style={{ width: 0, height: 0, ...arrow }} />}
        <div className="text-[10px] uppercase tracking-wider text-amber-400 font-bold mb-1">
          Step {step + 1} of {STEPS.length}
        </div>
        <div className="text-sm font-extrabold mb-1">{current.title}</div>
        <div className="text-xs text-gray-300 leading-snug mb-3">{current.body}</div>
        <div className="flex items-center justify-between gap-2">
          <button onClick={skip} className="text-[11px] text-gray-400 hover:text-white">
            Skip tour
          </button>
          <div className="flex gap-2">
            {step > 0 && (
              <button
                onClick={back}
                className="text-xs px-2 py-1 border border-gray-600 hover:border-white rounded"
              >
                Back
              </button>
            )}
            <button
              onClick={next}
              className="text-xs px-3 py-1 bg-amber-500 text-black font-bold rounded hover:bg-amber-400"
            >
              {isLast ? 'Finish' : 'Next'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
