#!/usr/bin/env python3
"""Capture full-page UI screenshots and mobile metrics for mobile-first work.

Requires a running local app with seed_ui_demo data, plus Playwright:

    pip install -r requirements-dev.txt
    playwright install chromium

Examples:

    python scripts/ui_snapshots.py --name baseline
    python scripts/ui_snapshots.py --name stage1 --compare baseline --locale en
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "ui"

VIEWPORTS = {
    "mobile": {"width": 390, "height": 844, "is_mobile": True, "has_touch": True, "device_scale_factor": 2},
    "desktop": {"width": 1366, "height": 900, "is_mobile": False, "has_touch": False, "device_scale_factor": 1},
}

INTERACTIVE = "a, button, input, select, textarea, summary, label:has(input[type=checkbox]), label:has(input[type=radio])"


def _die(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def _ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        _die(
            "Playwright is not installed. Run:\n"
            "  pip install -r requirements-dev.txt\n"
            "  playwright install chromium"
        )
    return __import__("playwright.sync_api", fromlist=["sync_playwright"]).sync_playwright


def _git_branch() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out or "unknown"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _safe_name(value: str) -> str:
    return re.sub(r"[^\w.\-]+", "_", value).strip("_") or "run"


@dataclass
class PageResult:
    key: str
    path: str
    user: str
    viewport: str
    scroll_width: int = 0
    inner_width: int = 0
    configured_width: int = 0
    has_hscroll: bool = False
    small_tap_count: int = 0
    small_taps: list[dict[str, Any]] = field(default_factory=list)
    small_font_inputs: int = 0
    console_errors: list[str] = field(default_factory=list)
    failed_requests: list[str] = field(default_factory=list)
    external_requests: list[str] = field(default_factory=list)
    screenshot: str = ""
    error: str | None = None


class SnapshotRunner:
    def __init__(
        self,
        *,
        base_url: str,
        out_dir: Path,
        locale: str,
        password: str,
        staff_user: str,
        plain_user: str,
    ):
        self.base_url = base_url.rstrip("/")
        self.out_dir = out_dir
        self.locale = locale
        self.password = password
        self.staff_user = staff_user
        self.plain_user = plain_user
        self.results: list[PageResult] = []
        self._ids: dict[str, Any] = {}

    def run(self) -> dict[str, Any]:
        sync_playwright = _ensure_playwright()
        self.out_dir.mkdir(parents=True, exist_ok=True)
        (self.out_dir / "screenshots").mkdir(exist_ok=True)

        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as exc:  # noqa: BLE001
                _die(
                    f"Chromium launch failed ({exc}).\n"
                    "Install the browser with:\n"
                    "  playwright install chromium"
                )

            # Discover entity IDs while logged in as staff (desktop is enough).
            context = browser.new_context(
                viewport={"width": 1366, "height": 900},
                locale="ru-RU" if self.locale == "ru" else "en-US",
            )
            page = context.new_page()
            self._login(page, self.staff_user)
            self._set_locale(page)
            self._discover_ids(page)
            context.close()

            jobs = self._jobs()
            for user in (self.staff_user, self.plain_user):
                for vp_name, vp in VIEWPORTS.items():
                    context = browser.new_context(
                        viewport={"width": vp["width"], "height": vp["height"]},
                        is_mobile=vp["is_mobile"],
                        has_touch=vp["has_touch"],
                        device_scale_factor=vp["device_scale_factor"],
                        locale="ru-RU" if self.locale == "ru" else "en-US",
                    )
                    page = context.new_page()
                    console_errors: list[str] = []
                    failed: list[str] = []
                    external: list[str] = []
                    host = urlparse(self.base_url).hostname or "localhost"

                    def on_console(msg, bucket=console_errors):
                        if msg.type == "error":
                            bucket.append(msg.text)

                    def on_fail(req, bucket=failed):
                        bucket.append(f"{req.failure} {req.url}")

                    def on_request(req, bucket=external, local_host=host):
                        try:
                            parsed = urlparse(req.url)
                            h = parsed.hostname or ""
                        except Exception:  # noqa: BLE001
                            return
                        if not h or h in (local_host, "127.0.0.1", "::1"):
                            return
                        if parsed.scheme in ("data", "blob"):
                            return
                        bucket.append(req.url)

                    page.on("console", on_console)
                    page.on("requestfailed", on_fail)
                    page.on("request", on_request)

                    self._login(page, user)
                    self._set_locale(page)

                    for job in jobs:
                        if job.get("staff_only") and user != self.staff_user:
                            continue
                        console_errors.clear()
                        failed.clear()
                        external.clear()
                        self._capture(
                            page,
                            user=user,
                            viewport=vp_name,
                            job=job,
                            console_errors=console_errors,
                            failed_requests=failed,
                            external_requests=list(dict.fromkeys(external)),
                        )
                    context.close()
            browser.close()

        report = {
            "name": self.out_dir.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "base_url": self.base_url,
            "locale": self.locale,
            "ids": self._ids,
            "pages": [self._result_dict(r) for r in self.results],
        }
        (self.out_dir / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return report

    def _result_dict(self, r: PageResult) -> dict[str, Any]:
        return {
            "key": r.key,
            "path": r.path,
            "user": r.user,
            "viewport": r.viewport,
            "scrollWidth": r.scroll_width,
            "innerWidth": r.inner_width,
            "configuredWidth": r.configured_width,
            "hasHorizontalScroll": r.has_hscroll,
            "smallTapCount": r.small_tap_count,
            "smallTaps": r.small_taps,
            "smallFontInputs": r.small_font_inputs,
            "consoleErrors": r.console_errors,
            "failedRequests": r.failed_requests,
            "externalRequests": r.external_requests,
            "screenshot": r.screenshot,
            "error": r.error,
        }

    def _url(self, path: str) -> str:
        return urljoin(self.base_url + "/", path.lstrip("/"))

    def _login(self, page, username: str) -> None:
        page.goto(self._url("/accounts/login/"), wait_until="networkidle")
        page.fill('input[name="username"]', username)
        page.fill('input[name="password"]', self.password)
        page.click('button[type="submit"], input[type="submit"]')
        page.wait_for_load_state("networkidle")
        if "/accounts/login" in page.url:
            _die(f"Login failed for {username}. Is seed_ui_demo applied and the app running?")

    def _set_locale(self, page) -> None:
        # Prefer the language form on the current page; fall back to POST setlang.
        page.goto(self._url("/"), wait_until="networkidle")
        lang = page.locator("select#language")
        if lang.count():
            current = lang.input_value()
            if current != self.locale:
                lang.select_option(self.locale)
                page.wait_for_load_state("networkidle")
            return
        page.evaluate(
            """async ([url, locale]) => {
                const token = document.querySelector('input[name=csrfmiddlewaretoken]')?.value;
                const body = new URLSearchParams({language: locale, next: '/'});
                await fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        ...(token ? {'X-CSRFToken': token} : {}),
                    },
                    body,
                    credentials: 'same-origin',
                });
            }""",
            [self._url("/i18n/setlang/"), self.locale],
        )
        page.goto(self._url("/"), wait_until="networkidle")

    def _discover_ids(self, page) -> None:
        ids: dict[str, Any] = {}

        page.goto(self._url("/sales/?group_by=receipt"), wait_until="networkidle")
        href = page.locator('a[href*="/sales/orders/"]').first.get_attribute("href") if page.locator('a[href*="/sales/orders/"]').count() else None
        if href:
            m = re.search(r"/sales/orders/(\d+)/", href)
            if m:
                ids["receipt_id"] = int(m.group(1))

        page.goto(self._url("/sales/matrix/"), wait_until="networkidle")
        sg = page.locator('a[href*="/sales/matrix/sg/"]').first
        if sg.count():
            href = sg.get_attribute("href") or ""
            m = re.search(r"/sales/matrix/sg/(\d+)/", href)
            if m:
                ids["sg_id"] = int(m.group(1))
        # Group links live on the super-group detail page, not the matrix summary.
        if ids.get("sg_id"):
            page.goto(self._url(f"/sales/matrix/sg/{ids['sg_id']}/"), wait_until="networkidle")
            grp = page.locator('a[href*="/sales/matrix/group/"]').first
            if grp.count():
                href = grp.get_attribute("href") or ""
                m = re.search(r"/sales/matrix/group/(-?\d+)/", href)
                if m:
                    ids["group_id"] = int(m.group(1))

        page.goto(self._url("/sales/reconcile/"), wait_until="networkidle")
        month_link = page.locator('a[href*="/sales/reconcile/2"]').first
        if month_link.count():
            href = month_link.get_attribute("href") or ""
            m = re.search(r"/sales/reconcile/(\d{4}-\d{2})/", href)
            if m:
                ids["reconcile_month"] = m.group(1)
        if ids.get("reconcile_month"):
            page.goto(self._url(f"/sales/reconcile/{ids['reconcile_month']}/"), wait_until="networkidle")
            docs = page.locator('a[href*="/store/"]').first
            if docs.count():
                href = docs.get_attribute("href") or ""
                m = re.search(r"/store/(\d+)/", href)
                if m:
                    ids["reconcile_store"] = int(m.group(1))

        page.goto(self._url("/campaigns/"), wait_until="networkidle")
        camp = page.locator('a[href*="/campaigns/"]').filter(has_not_text="new").first
        # Prefer detail links /campaigns/<pk>/
        for el in page.locator('a[href*="/campaigns/"]').all():
            href = el.get_attribute("href") or ""
            m = re.search(r"/campaigns/(\d+)/?$", href)
            if m:
                ids["campaign_id"] = int(m.group(1))
                break
        if ids.get("campaign_id"):
            page.goto(self._url(f"/campaigns/{ids['campaign_id']}/"), wait_until="networkidle")
            row = page.locator('a[href*="/clients/"]').first
            if row.count():
                href = row.get_attribute("href") or ""
                m = re.search(r"/clients/(\d+)/", href)
                if m:
                    ids["campaign_client_row"] = int(m.group(1))

        page.goto(self._url("/promos/"), wait_until="networkidle")
        for el in page.locator('a[href*="/promos/"]').all():
            href = el.get_attribute("href") or ""
            m = re.search(r"/promos/(\d+)/?$", href)
            if m:
                ids.setdefault("promo_ids", []).append(int(m.group(1)))
                if "promo_id" not in ids:
                    ids["promo_id"] = int(m.group(1))
        # Prefer active promo with charts if several exist: open each detail briefly.
        for pk in ids.get("promo_ids", [])[:5]:
            page.goto(self._url(f"/promos/{pk}/"), wait_until="networkidle")
            if page.locator(f'a[href*="/promos/{pk}/charts"]').count():
                ids["promo_id"] = pk
                ids["promo_with_charts"] = pk
                break

        self._ids = ids
        print(f"Discovered ids: {json.dumps(ids)}")

    def _jobs(self) -> list[dict[str, Any]]:
        ids = self._ids
        jobs: list[dict[str, Any]] = [
            {"key": "login", "path": "/accounts/login/", "anonymous": True},
            {"key": "register", "path": "/accounts/register/", "anonymous": True},
            {"key": "home", "path": "/"},
            {"key": "sales_default", "path": "/sales/"},
            {"key": "sales_by_receipt", "path": "/sales/?group_by=receipt"},
            {"key": "sales_scope_all", "path": "/sales/?scope=all"},
            {"key": "matrix", "path": "/sales/matrix/"},
            {"key": "matrix_edit", "path": "/sales/matrix/edit/"},
            {"key": "reconcile", "path": "/sales/reconcile/"},
            {"key": "campaigns", "path": "/campaigns/"},
            {"key": "campaign_new", "path": "/campaigns/new/"},
            {"key": "promos", "path": "/promos/"},
            {"key": "promo_new", "path": "/promos/new/"},
            {"key": "promo_picker", "path": "/promos/new/", "picker": True},
        ]
        if ids.get("receipt_id"):
            jobs.append({"key": "receipt", "path": f"/sales/orders/{ids['receipt_id']}/"})
        if ids.get("sg_id"):
            jobs.append({"key": "matrix_sg", "path": f"/sales/matrix/sg/{ids['sg_id']}/"})
        if ids.get("group_id") is not None:
            jobs.append({"key": "matrix_group", "path": f"/sales/matrix/group/{ids['group_id']}/"})
        if ids.get("reconcile_month"):
            jobs.append(
                {"key": "reconcile_month", "path": f"/sales/reconcile/{ids['reconcile_month']}/"}
            )
        if ids.get("reconcile_month") and ids.get("reconcile_store"):
            jobs.append(
                {
                    "key": "reconcile_docs",
                    "path": f"/sales/reconcile/{ids['reconcile_month']}/store/{ids['reconcile_store']}/",
                }
            )
        if ids.get("campaign_id"):
            cid = ids["campaign_id"]
            jobs.append({"key": "campaign_detail", "path": f"/campaigns/{cid}/"})
            jobs.append({"key": "campaign_purchases", "path": f"/campaigns/{cid}/purchases/"})
            if ids.get("campaign_client_row"):
                jobs.append(
                    {
                        "key": "campaign_client",
                        "path": f"/campaigns/{cid}/clients/{ids['campaign_client_row']}/",
                    }
                )
        if ids.get("promo_id"):
            pid = ids["promo_id"]
            jobs.append({"key": "promo_detail", "path": f"/promos/{pid}/"})
            jobs.append({"key": "promo_edit", "path": f"/promos/{pid}/edit/"})
        if ids.get("promo_with_charts"):
            jobs.append(
                {
                    "key": "promo_charts",
                    "path": f"/promos/{ids['promo_with_charts']}/charts/",
                }
            )
        return jobs

    def _capture(
        self,
        page,
        *,
        user: str,
        viewport: str,
        job: dict[str, Any],
        console_errors: list[str],
        failed_requests: list[str],
        external_requests: list[str],
    ) -> None:
        key = f"{job['key']}__{user}__{viewport}"
        path = job["path"]
        result = PageResult(key=key, path=path, user=user, viewport=viewport)
        try:
            if job.get("anonymous"):
                # Open in a throwaway context would be cleaner; for simplicity navigate and
                # accept redirect-back after. Anonymous pages: use storage without login cookie
                # only for login/register — open URL directly (session may still exist).
                page.goto(self._url(path), wait_until="networkidle")
            else:
                page.goto(self._url(path), wait_until="networkidle")

            if job.get("picker"):
                # Mobile layout can stack fields over the button; open dialog via API.
                opened = page.evaluate(
                    """() => {
                        const dlg = document.getElementById('picker-granit');
                        if (!dlg) return false;
                        dlg.showModal();
                        return true;
                    }"""
                )
                if opened:
                    page.wait_for_timeout(400)
                    toggle = page.locator("#picker-granit .tree-toggle").first
                    if toggle.count():
                        toggle.click(force=True)
                        page.wait_for_timeout(800)

            configured_width = VIEWPORTS[viewport]["width"]
            metrics = page.evaluate(
                """([interactive, configuredWidth]) => {
                    const iw = window.innerWidth;
                    const sw = Math.max(
                        document.documentElement.scrollWidth,
                        document.body ? document.body.scrollWidth : 0
                    );
                    // Mobile Chromium may grow layout viewport with content; compare to
                    // the configured device width (Playwright viewport) as well.
                    const ref = Math.min(iw, configuredWidth);
                    const smallTaps = [];
                    for (const el of document.querySelectorAll(interactive)) {
                        const r = el.getBoundingClientRect();
                        if (r.width === 0 && r.height === 0) continue;
                        if (r.height < 44 || r.width < 44) {
                            let sel = el.tagName.toLowerCase();
                            if (el.id) sel += '#' + el.id;
                            else if (el.className && typeof el.className === 'string')
                                sel += '.' + el.className.trim().split(/\\s+/).slice(0, 2).join('.');
                            smallTaps.push({
                                selector: sel.slice(0, 120),
                                width: Math.round(r.width),
                                height: Math.round(r.height),
                                text: (el.innerText || el.value || '').trim().slice(0, 40),
                            });
                        }
                    }
                    let smallFonts = 0;
                    for (const el of document.querySelectorAll('input, select, textarea')) {
                        const fs = parseFloat(getComputedStyle(el).fontSize || '0');
                        if (fs && fs < 16) smallFonts += 1;
                    }
                    return {
                        innerWidth: iw,
                        configuredWidth,
                        scrollWidth: sw,
                        hasHorizontalScroll: sw > ref + 1,
                        smallTapCount: smallTaps.length,
                        smallTaps: smallTaps.slice(0, 10),
                        smallFontInputs: smallFonts,
                    };
                }""",
                [INTERACTIVE, configured_width],
            )
            result.inner_width = int(metrics["innerWidth"])
            result.scroll_width = int(metrics["scrollWidth"])
            result.configured_width = int(metrics["configuredWidth"])
            result.has_hscroll = bool(metrics["hasHorizontalScroll"])
            result.small_tap_count = int(metrics["smallTapCount"])
            result.small_taps = metrics["smallTaps"]
            result.small_font_inputs = int(metrics["smallFontInputs"])
            result.console_errors = list(console_errors)
            result.failed_requests = list(failed_requests)
            result.external_requests = sorted(set(external_requests))[:30]

            shot_name = f"{_safe_name(key)}.png"
            shot_path = self.out_dir / "screenshots" / shot_name
            page.screenshot(path=str(shot_path), full_page=True)
            result.screenshot = f"screenshots/{shot_name}"
        except Exception as exc:  # noqa: BLE001
            result.error = str(exc)
            print(f"ERROR {key}: {exc}", file=sys.stderr)
        self.results.append(result)
        flag = "HSCROLL" if result.has_hscroll else "ok"
        print(
            f"[{flag}] {key} scroll={result.scroll_width}/{result.inner_width} "
            f"tap<{44}={result.small_tap_count} font<{16}={result.small_font_inputs}"
        )


def _load_report(name: str) -> dict[str, Any]:
    path = ARTIFACTS / name / "report.json"
    if not path.exists():
        _die(f"Compare target not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _build_compare(current: dict[str, Any], other_name: str, out_dir: Path) -> Path:
    other = _load_report(other_name)
    other_dir = ARTIFACTS / other_name

    def index(report: dict[str, Any]) -> dict[str, dict]:
        return {p["key"]: p for p in report.get("pages", [])}

    cur_idx = index(current)
    old_idx = index(other)
    keys = sorted(set(cur_idx) | set(old_idx))

    rows_html = []
    cards_html = []
    for key in keys:
        a = old_idx.get(key)
        b = cur_idx.get(key)
        if not a or not b:
            continue
        if a.get("viewport") != "mobile" and b.get("viewport") != "mobile":
            # Still show all; highlight mobile worsenings in table.
            pass

        def worse(old_v, new_v, higher_is_worse=True):
            if old_v is None or new_v is None:
                return False
            return (new_v > old_v) if higher_is_worse else (new_v < old_v)

        hs_bad = worse(
            1 if a.get("hasHorizontalScroll") else 0,
            1 if b.get("hasHorizontalScroll") else 0,
        )
        tap_bad = worse(a.get("smallTapCount", 0), b.get("smallTapCount", 0))
        font_bad = worse(a.get("smallFontInputs", 0), b.get("smallFontInputs", 0))
        cls = "bad" if (hs_bad or tap_bad or font_bad) else ""
        rows_html.append(
            "<tr class='{cls}'><td>{key}</td>"
            "<td>{ah} → {bh}</td><td>{at} → {bt}</td><td>{af} → {bf}</td></tr>".format(
                cls=cls,
                key=key,
                ah=a.get("scrollWidth"),
                bh=b.get("scrollWidth"),
                at=a.get("smallTapCount"),
                bt=b.get("smallTapCount"),
                af=a.get("smallFontInputs"),
                bf=b.get("smallFontInputs"),
            )
        )
        if a.get("screenshot") and b.get("screenshot"):
            left = (other_dir / a["screenshot"]).as_posix()
            right = (out_dir / b["screenshot"]).as_posix()
            # Relative paths from compare.html location.
            left_rel = Path("..") / other_name / a["screenshot"]
            right_rel = Path(b["screenshot"])
            cards_html.append(
                f"<section><h3>{key}</h3><div class='pair'>"
                f"<figure><figcaption>before ({other_name})</figcaption>"
                f"<img src='{left_rel.as_posix()}' loading='lazy'></figure>"
                f"<figure><figcaption>after ({current.get('name')})</figcaption>"
                f"<img src='{right_rel.as_posix()}' loading='lazy'></figure>"
                f"</div></section>"
            )

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>UI compare {other_name} → {current.get('name')}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 1rem 1.5rem; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
th, td {{ border: 1px solid #ccc; padding: 0.35rem 0.5rem; font-size: 13px; }}
tr.bad {{ background: #ffe8e8; }}
.pair {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }}
img {{ max-width: 100%; border: 1px solid #ddd; }}
section {{ margin-bottom: 1.5rem; }}
</style></head><body>
<h1>Compare {other_name} → {current.get('name')}</h1>
<p>Red rows: horizontal scroll / small taps / small fonts got worse.</p>
<table><thead><tr>
<th>Page</th><th>scrollWidth</th><th>taps &lt; 44px</th><th>inputs font &lt; 16px</th>
</tr></thead><tbody>
{''.join(rows_html)}
</tbody></table>
{''.join(cards_html)}
</body></html>"""
    out = out_dir / "compare.html"
    out.write_text(html, encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--name", default=_git_branch(), help="Run folder under artifacts/ui/")
    parser.add_argument("--compare", default=None, help="Another run name to build compare.html")
    parser.add_argument("--locale", default="ru", choices=["ru", "en"])
    parser.add_argument("--password", default="demo-pass-123")
    parser.add_argument("--staff-user", default="demo_staff")
    parser.add_argument("--user", dest="plain_user", default="demo_user")
    args = parser.parse_args(argv)

    out_dir = ARTIFACTS / _safe_name(args.name)
    runner = SnapshotRunner(
        base_url=args.base_url,
        out_dir=out_dir,
        locale=args.locale,
        password=args.password,
        staff_user=args.staff_user,
        plain_user=args.plain_user,
    )
    report = runner.run()
    print(f"Wrote {out_dir / 'report.json'} ({len(report['pages'])} pages)")

    if args.compare:
        compare_path = _build_compare(report, args.compare, out_dir)
        print(f"Wrote {compare_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
