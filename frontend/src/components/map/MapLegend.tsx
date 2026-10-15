import { ChevronDown, ChevronUp, Info } from "lucide-react";
import { useState } from "react";

const startOpen = () => typeof window !== "undefined" && window.innerWidth >= 1024 && window.innerHeight >= 760;

export function MapLegend({ showSearch }: { showSearch: boolean }) {
  const [open, setOpen] = useState(startOpen);
  return (
    <div className="absolute bottom-6 left-3 z-[1000] w-48 rounded-lg border border-slate-200 bg-white/95 text-[11px] shadow-pop backdrop-blur">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-3 px-2.5 py-1.5 text-xs font-semibold text-ink"
        aria-expanded={open}
      >
        Legend {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronUp className="h-3.5 w-3.5" />}
      </button>
      {open && (
        <ul className="space-y-1 px-2.5 pb-2.5 text-slate-600">
          {showSearch && (
            <>
              <li className="flex items-center gap-2">
                <span className="inline-block h-3 w-3 rounded-full border-2 border-white bg-blue-600 shadow" /> Search location
              </li>
              <li className="flex items-center gap-2">
                <svg width="12" height="15" viewBox="0 0 34 44" aria-hidden>
                  <path d="M17 1C8.2 1 1 8 1 16.7 1 28.4 17 43 17 43s16-14.6 16-26.3C33 8 25.8 1 17 1Z" fill="#15803d" />
                </svg>
                Nearest hub
              </li>
              <li className="flex items-center gap-2">
                <svg width="12" height="15" viewBox="0 0 34 44" aria-hidden>
                  <path d="M17 1C8.2 1 1 8 1 16.7 1 28.4 17 43 17 43s16-14.6 16-26.3C33 8 25.8 1 17 1Z" fill="#c2410c" />
                </svg>
                Selected alternative
              </li>
              <li className="flex items-center gap-2">
                <span className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full bg-sky-700 text-[8px] font-bold text-white">2</span>
                Ranked hub
              </li>
              <li className="flex items-center gap-2">
                <span className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full border-2 border-red-600 bg-white text-[9px] font-bold leading-none text-red-600">×</span>
                Unreachable hub
              </li>
              <li className="flex items-center gap-2">
                <span className="inline-block h-1.5 w-5 rounded-full bg-[#1a73e8] outline outline-2 outline-white ring-1 ring-slate-600" /> Road route
              </li>
              <li className="flex items-center gap-2">
                <span className="inline-block h-0 w-5 border-t-2 border-dashed border-slate-500" /> Alternative route
              </li>
              <li className="flex items-center gap-2">
                <span className="inline-block h-0 w-5 border-t-2 border-dotted border-slate-400" /> Gap to nearest road
              </li>
            </>
          )}
          <li className="flex items-center gap-2">
            <span className="inline-block h-2.5 w-2.5 rounded-full border border-white bg-indigo-600 shadow" /> Hub (cluster colour)
          </li>
          <li className="flex items-center gap-2">
            <span className="inline-block h-2.5 w-2.5 rounded-full border-2 border-slate-500 bg-white" /> Inactive hub
          </li>
          <li className="flex items-center gap-2">
            <span className="inline-block h-2 w-2 rotate-45 bg-indigo-600" /> Cluster center
          </li>
          <li className="flex items-center gap-2">
            <span className="inline-block h-2.5 w-4 rounded-sm border-2 border-indigo-600 bg-indigo-600/20" /> Cluster boundary
          </li>
          <li className="flex items-start gap-1.5 pt-0.5 text-[10px] leading-snug text-slate-500">
            <Info className="mt-px h-3 w-3 shrink-0" /> Hub points are inferred from service-area polygons.
          </li>
        </ul>
      )}
    </div>
  );
}
