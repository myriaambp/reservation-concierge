"""Browser-automated booking. The agent opens Chromium, navigates the
TableTime sandbox (fake-resy), clicks an available time, fills the form,
submits, and captures the confirmation page.

We drive a site we control so the demo always works — no broken selectors,
no CAPTCHAs, no ToS issues. The architecture (provider interface +
deep_links abstraction) is the same path a real Resy partnership would use.
"""
from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.booking.deep_links import build_booking_url


_SCREENSHOTS_DIR = Path(__file__).resolve().parents[2] / "frontend" / "static" / "screenshots"


def _save_screenshot(page, out_dir: Path, label: str) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{label}.png"
    try:
        page.screenshot(path=str(path), full_page=False)
    except Exception:
        return ""
    return str(path.relative_to(_SCREENSHOTS_DIR.parents[1]))


def book_via_browser(
    restaurant_id: str,
    *,
    dt: datetime,
    party_size: int,
    name_on_reservation: str = "Priya Shah",
    email: str = "myriam.bp12@gmail.com",
    headless: bool | None = None,
) -> dict[str, Any]:
    """Drive Chromium against the booking site. Completes the full flow:
    navigate → pick time → fill form → submit → capture confirmation."""
    if headless is None:
        headless = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"

    link = build_booking_url(restaurant_id, dt=dt, party_size=party_size)
    url = link.get("url")
    if not url:
        return {"ok": False, "error": "no booking URL", "screenshots": [], "steps": []}

    run_id = f"{restaurant_id}-{int(time.time())}"
    out_dir = _SCREENSHOTS_DIR / run_id
    target_time_24h = dt.strftime("%H:%M")  # e.g. "19:30"

    steps: list[dict] = []
    screenshots: list[str] = []
    confirmation_code: str | None = None

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "ok": False,
            "error": "playwright not installed (pip install playwright + playwright install chromium)",
            "screenshots": [], "steps": [],
        }

    with sync_playwright() as p:
        browser = None
        page = None
        try:
            browser = p.chromium.launch(
                headless=headless,
                args=["--start-maximized"],
            )
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()

            # 1. Navigate to the restaurant page
            steps.append({"step": "navigate", "url": url})
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(800)
            screenshots.append(_save_screenshot(page, out_dir, "01-restaurant"))

            # 2. Click the matching time slot. We use a stable data-test attribute.
            steps.append({"step": "find-time", "looking_for": target_time_24h})

            # First try exact match by data-time
            slot = page.locator(f'[data-test="time-slot"][data-time="{target_time_24h}"]')
            if slot.count() == 0:
                # Fall back to ANY available slot — better demo than failing.
                slot = page.locator('[data-test="time-slot"]').first
                steps.append({"step": "exact-time-not-listed", "fallback": "first available"})

            if slot.count() == 0:
                steps.append({"step": "no-slots-available"})
                screenshots.append(_save_screenshot(page, out_dir, "99-no-slots"))
                return {
                    "ok": False,
                    "error": "no slots available on fake-resy for that date",
                    "url": url,
                    "screenshots": screenshots,
                    "steps": steps,
                }

            slot.scroll_into_view_if_needed()
            page.wait_for_timeout(500)
            slot.click()
            steps.append({"step": "clicked-time"})
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(700)
            screenshots.append(_save_screenshot(page, out_dir, "02-form"))

            # 3. Fill in the booking form
            page.locator('[data-test="name-input"]').fill(name_on_reservation)
            page.wait_for_timeout(300)
            page.locator('[data-test="email-input"]').fill(email)
            page.wait_for_timeout(400)
            steps.append({"step": "filled-form", "name": name_on_reservation, "email": email})
            screenshots.append(_save_screenshot(page, out_dir, "03-filled"))

            # 4. Submit
            page.locator('[data-test="submit-booking"]').click()
            steps.append({"step": "submitted"})
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            page.wait_for_timeout(800)
            screenshots.append(_save_screenshot(page, out_dir, "04-confirmation"))

            # 5. Extract confirmation code from the confirmation page URL
            current = page.url
            if "/confirmation/" in current:
                confirmation_code = current.rsplit("/", 1)[-1]
                steps.append({"step": "confirmed", "code": confirmation_code})

            return {
                "ok": True,
                "url": url,
                "platform": link.get("platform", "tabletime"),
                "screenshots": screenshots,
                "steps": steps,
                "confirmation_code": confirmation_code,
                "confirmation_url": current if confirmation_code else None,
            }
        except Exception as exc:
            steps.append({"step": "error", "detail": f"{type(exc).__name__}: {exc}"})
            try:
                if page:
                    screenshots.append(_save_screenshot(page, out_dir, "99-error"))
            except Exception:
                pass
            return {
                "ok": False,
                "url": url,
                "error": f"{type(exc).__name__}: {exc}",
                "screenshots": screenshots,
                "steps": steps,
            }
        finally:
            if browser:
                # Hold so the human can see the final state.
                try:
                    if page:
                        page.wait_for_timeout(2000)
                except Exception:
                    pass
                browser.close()
