import { useState, useRef, useLayoutEffect, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';

const WIDTH = 208; // matches the previous w-52
const MARGIN = 8;  // keep this far from the viewport edges

export default function InfoTip({ text, up = false }) {
  const [show, setShow] = useState(false);
  const [pos, setPos] = useState({ left: 0, top: 0 });
  const iconRef = useRef(null);

  // Position the tooltip relative to the icon's viewport rect, centered over the
  // icon and clamped so it never spills past (and gets clipped at) a screen edge.
  // Rendered in a portal with position:fixed so the parent's overflow-y-auto
  // container can't clip it or push it behind sibling content.
  const updatePos = useCallback(() => {
    const el = iconRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const left = Math.max(
      MARGIN,
      Math.min(r.left + r.width / 2 - WIDTH / 2, window.innerWidth - WIDTH - MARGIN),
    );
    const top = up ? r.top - 6 : r.bottom + 6;
    setPos({ left, top });
  }, [up]);

  useLayoutEffect(() => {
    if (show) updatePos();
  }, [show, updatePos]);

  // Keep the tooltip glued to the icon if the page scrolls/resizes while shown.
  useEffect(() => {
    if (!show) return undefined;
    window.addEventListener('scroll', updatePos, true); // capture: catch nested scrollers
    window.addEventListener('resize', updatePos);
    return () => {
      window.removeEventListener('scroll', updatePos, true);
      window.removeEventListener('resize', updatePos);
    };
  }, [show, updatePos]);

  return (
    <span
      ref={iconRef}
      className="relative inline-flex items-center"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      onClick={(e) => e.stopPropagation()}
    >
      <span className="w-4 h-4 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-300 text-[10px] font-bold inline-flex items-center justify-center cursor-default select-none leading-none">
        i
      </span>
      {show && createPortal(
        <span
          style={{
            position: 'fixed',
            left: pos.left,
            top: pos.top,
            width: WIDTH,
            transform: up ? 'translateY(-100%)' : 'none',
          }}
          className="text-xs bg-gray-800 dark:bg-gray-950 text-white px-2 py-1.5 rounded z-[9999] whitespace-normal shadow-lg pointer-events-none"
        >
          {text}
        </span>,
        document.body,
      )}
    </span>
  );
}
