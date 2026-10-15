"""End-to-end UI checks with Playwright (uses the installed Microsoft Edge).

Prerequisites: backend on :8000 and frontend dev server on :5173, and
``pip install -r backend/requirements-dev.txt``.

Run from the project root::

    backend/.venv/Scripts/python e2e/ui_checks.py [screenshot_dir]

Each scenario group runs in its own Playwright session: on Windows the
headless Edge driver can drop its connection while tearing down a context that
handled downloads, and isolation keeps that from affecting other groups.
"""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from playwright.sync_api import BrowserContext, Page, expect, sync_playwright

BASE = "http://localhost:5173"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "e2e/screenshots")
OUT.mkdir(parents=True, exist_ok=True)
RESULTS: list[tuple[str, bool, str]] = []
CONSOLE_ERRORS: list[str] = []


def check(name: str, fn: Callable[[], None]) -> None:
    t0 = time.perf_counter()
    try:
        fn()
        RESULTS.append((name, True, f"{time.perf_counter() - t0:.1f}s"))
        print(f"PASS  {name}")
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).splitlines()[0][:300] if str(exc) else repr(exc)
        RESULTS.append((name, False, msg))
        print(f"FAIL  {name}: {msg}")


def shot(page: Page, name: str) -> None:
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)


def wait_map(page: Page) -> None:
    page.wait_for_selector(".leaflet-container", timeout=20000)
    page.wait_for_timeout(1500)


@contextmanager
def session(**context_args) -> Iterator[tuple[BrowserContext, Page]]:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        ctx = browser.new_context(**context_args)
        page = ctx.new_page()
        page.on("pageerror", lambda e: CONSOLE_ERRORS.append(str(e)))
        page.on("console", lambda m: CONSOLE_ERRORS.append(m.text) if m.type == "error" else None)
        try:
            yield ctx, page
        finally:
            try:
                ctx.close()
                browser.close()
            except Exception:  # noqa: BLE001 - driver teardown quirk, results already recorded
                pass


def search(page: Page, lat: str, lng: str) -> None:
    page.fill("#lat", lat)
    page.fill("#lng", lng)
    page.get_by_role("button", name="Find nearest hub").click()


def desktop_group() -> None:
    with session(
        viewport={"width": 1440, "height": 900},
        geolocation={"latitude": 17.4849, "longitude": 78.4138},
        permissions=["geolocation"],
    ) as (ctx, page):

        def dashboard():
            page.goto(BASE + "/")
            expect(page.get_by_text("Hub network overview")).to_be_visible(timeout=20000)
            expect(page.get_by_text("Total hubs")).to_be_visible()
            wait_map(page)
            shot(page, "01_dashboard")
            page.locator("main").evaluate("el => el.scrollTo(0, 1100)")
            page.wait_for_timeout(600)
            shot(page, "01b_dashboard_lower")

        check("Dashboard loads with KPI cards and map", dashboard)

        def manual_search():
            page.goto(BASE + "/find")
            wait_map(page)
            search(page, "17.412498", "78.411452")
            expect(page.get_by_text("Road route & directions")).to_be_visible(timeout=60000)
            expect(page.get_by_text("Guaranteed nearest within the search radius")).to_be_visible()
            expect(page.get_by_text("Turn-by-turn directions")).to_be_visible()
            page.wait_for_timeout(1500)
            shot(page, "02_find_manual_result")

        check("Manual coordinate search shows nearest hub + road route", manual_search)

        def alternative():
            alts = page.get_by_role("list", name="Alternative hubs").get_by_role("button")
            expect(alts).to_have_count(5)
            alts.nth(2).click()
            expect(page.locator("[aria-pressed=true]")).to_have_count(1)
            page.wait_for_timeout(2500)
            expect(page.get_by_text("Turn-by-turn directions")).to_be_visible(timeout=30000)
            shot(page, "03_find_alternative_selected")

        check("Selecting an alternative hub recalculates its route", alternative)

        def reload_restores():
            page.reload()
            expect(page.get_by_text("Road route & directions")).to_be_visible(timeout=20000)

        check("Reloading the page restores the latest search", reload_restores)

        def validation():
            search(page, "95", "abc")
            expect(page.get_by_text("Latitude must be between -90 and 90.")).to_be_visible()
            expect(page.get_by_text("Longitude must be a number")).to_be_visible()
            shot(page, "04_validation_errors")

        check("Coordinate validation rejects invalid input", validation)

        def paste_pair():
            page.fill("#lat", "")
            page.fill("#lng", "")
            page.evaluate(
                """() => {
                const el = document.querySelector('#lat');
                const dt = new DataTransfer(); dt.setData('text', '17.4474, 78.3762');
                el.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
            }"""
            )
            expect(page.locator("#lat")).to_have_value("17.4474")
            expect(page.locator("#lng")).to_have_value("78.3762")

        check("Pasting a 'lat, lng' pair fills both fields", paste_pair)

        def gps():
            page.get_by_role("button", name="Use my current location").click()
            expect(page.locator("#lat")).to_have_value("17.484900", timeout=15000)
            expect(page.get_by_text("Road route & directions")).to_be_visible(timeout=60000)
            expect(page.get_by_text("Kukatpally cluster").first).to_be_visible()
            page.wait_for_timeout(1500)
            shot(page, "05_gps_result")

        check("GPS location (permission granted) finds nearest hub", gps)

        def tracking():
            page.get_by_role("button", name="Track").click()
            expect(page.get_by_text("Live tracking on.")).to_be_visible(timeout=15000)
            ctx.set_geolocation({"latitude": 17.4935, "longitude": 78.3990})
            expect(page.locator("#lat")).to_have_value("17.493500", timeout=20000)
            page.wait_for_timeout(3000)
            shot(page, "06_tracking")
            page.get_by_role("button", name="Stop").click()
            expect(page.get_by_text("Live tracking on.")).to_have_count(0)

        check("Live tracking re-searches on movement and can be stopped", tracking)

        def map_click():
            page.locator(".leaflet-container").click(position={"x": 700, "y": 450})
            expect(page.get_by_text("Selected point").first).to_be_visible(timeout=5000)

        check("Clicking the map picks a search point", map_click)

        def outside():
            search(page, "17.2403", "78.4294")
            expect(page.get_by_text("Outside cluster coverage")).to_be_visible(timeout=60000)
            page.wait_for_timeout(1500)
            shot(page, "07_outside_coverage")

        check("Outside-coverage search shows the fallback explanation", outside)

        def pages():
            for path, text, name in [
                ("/map", "Cluster filters", "08_live_map"),
                ("/clusters", "Cluster analysis", "09_clusters"),
                ("/hubs", "Hub directory", "10_hubs"),
                ("/history", "Route history", "11_history"),
                ("/import", "Data import & quality", "12_import"),
                ("/export", "Export to Google Earth", "13_export"),
                ("/settings", "Settings", "14_settings"),
            ]:
                page.goto(BASE + path)
                expect(page.get_by_text(text).first).to_be_visible(timeout=20000)
                page.wait_for_timeout(1800)
                shot(page, name)

        check("All sidebar pages render", pages)

        def cluster_select():
            page.goto(BASE + "/clusters")
            page.select_option("#analysis-cluster", "kondapur")
            expect(page.get_by_text("28 hubs · 28 live")).to_be_visible(timeout=10000)
            page.wait_for_timeout(1500)
            page.locator("main").evaluate("el => el.scrollTo(0, 380)")
            page.wait_for_timeout(500)
            shot(page, "15_cluster_selected")

        check("Selecting a cluster shows its detail and zooms the map", cluster_select)

        def hub_directory():
            page.goto(BASE + "/hubs")
            page.fill("#hub-q", "lanco")
            expect(page.get_by_text("1 hub · page 1 of 1")).to_be_visible(timeout=10000)
            page.get_by_role("cell", name="Lanco Hills").click()
            expect(page.get_by_role("dialog", name="Hub details")).to_be_visible()
            shot(page, "16_hub_details")

        check("Hub directory search + details drawer", hub_directory)

        def history():
            page.goto(BASE + "/history")
            expect(page.get_by_role("heading", name="Route history")).to_be_visible()
            page.wait_for_timeout(1000)
            assert page.locator("table tbody tr").count() >= 1, "expected saved manual searches"
            sources = page.locator("table tbody td:nth-child(2)").all_inner_texts()
            assert not any("GPS" in s for s in sources), f"GPS searches were saved without consent: {sources}"

        check("History saves manual searches but not GPS without consent", history)


def denied_group() -> None:
    with session(viewport={"width": 1280, "height": 860}) as (_ctx, page):

        def gps_denied():
            page.goto(BASE + "/find")
            wait_map(page)
            page.get_by_role("button", name="Use my current location").click()
            expect(page.get_by_text("Location permission was denied")).to_be_visible(timeout=15000)
            shot(page, "17_gps_denied")

        check("GPS permission denied shows manual fallback message", gps_denied)


def mobile_group() -> None:
    with session(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True) as (_ctx, page):

        def mobile():
            page.goto(BASE + "/")
            expect(page.get_by_text("Hub network overview")).to_be_visible(timeout=20000)
            wait_map(page)
            shot(page, "18_mobile_dashboard")
            page.get_by_role("button", name="Open navigation").click()
            page.wait_for_timeout(400)
            shot(page, "19_mobile_nav")
            page.get_by_role("link", name="Find Nearest Hub").click()
            wait_map(page)
            search(page, "17.4600", "78.3600")
            expect(page.get_by_text("Road route & directions")).to_be_visible(timeout=60000)
            page.wait_for_timeout(1500)
            shot(page, "20_mobile_find")
            page.locator("aside").first.evaluate("el => el.scrollTo(0, 900)")
            page.wait_for_timeout(400)
            shot(page, "21_mobile_find_result")
            overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
            assert not overflow, "horizontal overflow on mobile"

        check("Mobile layout: dashboard, nav drawer, search", mobile)


def downloads_group() -> None:
    with session(viewport={"width": 1440, "height": 900}, accept_downloads=True) as (_ctx, page):

        def downloads():
            page.goto(BASE + "/find")
            wait_map(page)
            search(page, "17.4849", "78.4138")
            expect(page.get_by_text("Road route & directions")).to_be_visible(timeout=60000)
            page.get_by_role("link", name="Export to Google Earth").click()
            expect(page.get_by_text("all_hubs.kml")).to_be_visible(timeout=10000)
            with page.expect_download() as d:
                page.locator("a[href*='type=all_hubs']").first.click()
            data = Path(d.value.path()).read_bytes()
            assert data.startswith(b"<?xml") and b"<kml" in data, "all_hubs download is not KML"
            with page.expect_download() as d2:
                page.locator("a[href*='type=route']").first.click()
            data2 = Path(d2.value.path()).read_bytes()
            assert b"<LineString>" in data2, "route KML has no LineString"
            assert data2.count(b",0\n") > 20, "route KML should contain many road points"

        check("KML downloads (all hubs + route) are valid KML", downloads)


def run() -> int:
    for group in (desktop_group, denied_group, mobile_group, downloads_group):
        group()
    relevant = [e for e in CONSOLE_ERRORS if "tile" not in e.lower() and "favicon" not in e.lower()]
    print("browser console/page errors:", relevant[:10] or "none")
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n{passed}/{len(RESULTS)} UI checks passed")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(run())
