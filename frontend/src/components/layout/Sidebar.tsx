import {
  BarChart3,
  Building2,
  Earth,
  History,
  LayoutDashboard,
  Map as MapIcon,
  Navigation,
  Settings,
  Upload,
  X,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { useAppData } from "../../context/AppData";
import { cx } from "../ui";

export const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/map", label: "Live Map", icon: MapIcon },
  { to: "/find", label: "Find Nearest Hub", icon: Navigation },
  { to: "/clusters", label: "Cluster Analysis", icon: BarChart3 },
  { to: "/hubs", label: "Hub Directory", icon: Building2 },
  { to: "/history", label: "Route History", icon: History },
  { to: "/import", label: "Data Import", icon: Upload },
  { to: "/export", label: "Export to Google Earth", icon: Earth },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { analytics, health } = useAppData();
  return (
    <>
      <div
        className={cx("fixed inset-0 z-[1100] bg-slate-900/40 lg:hidden", open ? "block" : "hidden")}
        onClick={onClose}
        aria-hidden
      />
      <aside
        className={cx(
          "fixed inset-y-0 left-0 z-[1200] flex w-64 flex-col bg-slate-900 text-slate-300 transition-transform lg:static lg:z-auto lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
        aria-label="Main navigation"
      >
        <div className="flex h-16 items-center justify-between gap-2 px-5">
          <div className="flex items-center gap-2.5">
            <img src="/favicon.svg" alt="" className="h-8 w-8" />
            <div className="leading-tight">
              <p className="text-sm font-semibold text-white">Smart Hub Finder</p>
              <p className="text-[11px] text-slate-400">Location &amp; Routing</p>
            </div>
          </div>
          <button className="rounded-md p-1.5 text-slate-400 hover:bg-slate-800 lg:hidden" onClick={onClose} aria-label="Close navigation">
            <X className="h-5 w-5" />
          </button>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={onClose}
              className={({ isActive }) =>
                cx(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive ? "bg-brand-700 text-white" : "text-slate-300 hover:bg-slate-800 hover:text-white",
                )
              }
            >
              <Icon className="h-[18px] w-[18px] shrink-0" aria-hidden />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-800 px-5 py-4 text-[11px] leading-relaxed text-slate-400">
          {analytics ? (
            <>
              <p className="truncate font-medium text-slate-300" title={analytics.dataset.file_name}>
                {analytics.dataset.file_name}
              </p>
              <p>
                {analytics.totals.hubs} hubs · {analytics.totals.clusters} clusters
              </p>
            </>
          ) : (
            <p>No dataset loaded</p>
          )}
          <p className="mt-1">API v{health?.version ?? "–"}</p>
        </div>
      </aside>
    </>
  );
}
