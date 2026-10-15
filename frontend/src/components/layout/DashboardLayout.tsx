import { Menu, RefreshCw, Route as RouteIcon, ServerCrash } from "lucide-react";
import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { useAppData } from "../../context/AppData";
import { Alert, Button, Spinner, cx } from "../ui";
import { NAV_ITEMS, Sidebar } from "./Sidebar";

function RoutingPill() {
  const { health, settings } = useAppData();
  const routing = settings?.routing ?? health?.routing;
  if (!routing) return null;
  const active = routing.providers.find((p) => p.name === routing.active);
  return (
    <div
      className={cx(
        "hidden items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset sm:inline-flex",
        active ? "bg-emerald-50 text-emerald-800 ring-emerald-200" : "bg-red-50 text-red-700 ring-red-200",
      )}
      title={active ? `Road routing via ${active.label}` : routing.error ?? "Routing unavailable"}
    >
      <RouteIcon className="h-3.5 w-3.5" aria-hidden />
      {active ? `Routing: ${active.label.split(" (")[0]}` : "Routing not configured"}
    </div>
  );
}

export function DashboardLayout() {
  const [open, setOpen] = useState(false);
  const { loading, error, reload, health } = useAppData();
  const { pathname } = useLocation();
  const current = NAV_ITEMS.find((n) => (n.end ? pathname === n.to : pathname.startsWith(n.to)));
  const fullBleed = pathname === "/map" || pathname === "/find";

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar open={open} onClose={() => setOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <button className="rounded-md p-2 text-slate-600 hover:bg-slate-100 lg:hidden" onClick={() => setOpen(true)} aria-label="Open navigation">
              <Menu className="h-5 w-5" />
            </button>
            <p className="truncate text-sm font-semibold text-ink">{current?.label ?? "Smart Hub Finder"}</p>
          </div>
          <div className="flex items-center gap-2">
            <RoutingPill />
            <Button variant="ghost" size="sm" icon={RefreshCw} onClick={() => void reload()} aria-label="Reload data" loading={loading}>
              <span className="hidden sm:inline">Refresh</span>
            </Button>
          </div>
        </header>
        <main className={cx("min-h-0 flex-1", fullBleed ? "overflow-hidden" : "overflow-y-auto")}>
          {loading && !health ? (
            <div className="flex h-full items-center justify-center">
              <Spinner label="Connecting to the Smart Hub API…" />
            </div>
          ) : error && !fullBleed ? (
            <div className="mx-auto max-w-2xl p-6">
              <Alert tone="error" title="Data could not be loaded">
                <p>{error}</p>
                <p className="mt-1">
                  Start the backend with <code className="rounded bg-red-100 px-1">uvicorn app.main:app --port 8000</code> from the{" "}
                  <code className="rounded bg-red-100 px-1">backend</code> folder, then press Refresh.
                </p>
              </Alert>
              <div className="mt-4">
                <Button icon={ServerCrash} onClick={() => void reload()}>
                  Retry
                </Button>
              </div>
              {pathname === "/import" || pathname === "/settings" ? <Outlet /> : null}
            </div>
          ) : (
            <Outlet />
          )}
        </main>
      </div>
    </div>
  );
}
