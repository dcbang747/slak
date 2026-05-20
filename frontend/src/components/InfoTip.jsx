import { useState } from 'react';

export default function InfoTip({ text, up = false }) {
  const [show, setShow] = useState(false);
  const tipPos = up ? 'bottom-full mb-1' : 'top-full mt-1';
  return (
    <span
      className="relative inline-flex items-center"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      onClick={(e) => e.stopPropagation()}
    >
      <span className="w-4 h-4 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-300 text-[10px] font-bold inline-flex items-center justify-center cursor-default select-none leading-none">
        i
      </span>
      {show && (
        <span className={`absolute right-0 ${tipPos} w-52 text-xs bg-gray-800 dark:bg-gray-950 text-white px-2 py-1.5 rounded z-50 whitespace-normal shadow-lg pointer-events-none`}>
          {text}
        </span>
      )}
    </span>
  );
}
