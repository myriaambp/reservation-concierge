"""Resy / OpenTable deep links — the legal-and-actually-works booking primitive.

A deep link pre-fills a Resy URL with date, party size, and (where supported)
time. The user taps the link, lands on the real Resy page with the slot
already loaded, and confirms with a single tap. We do 99% of the work; the
user does the final tap (which doubles as the consent gate Resy's ToS expects).
"""
from __future__ import annotations

from datetime import datetime
from urllib.parse import urlencode


# Known Resy slugs for our seed restaurants. Resy URL pattern is:
#   https://resy.com/cities/new-york-ny/venues/<slug>
# When restaurants migrate slug or platform, edit here only.
_RESY_SLUGS: dict[str, str] = {
    "carbone": "carbone",
    "don-angie": "don-angie",
    "tatiana": "tatiana-by-kwame-onwuachi",
    "4-charles": "4-charles-prime-rib",
    "polo-bar": "the-polo-bar",
    "le-bernardin": "le-bernardin",
    "emp": "eleven-madison-park",
    "sushi-nakazawa": "sushi-nakazawa",
    "i-sodi": "i-sodi",
    "rezdora": "rezdora",
    "lartusi": "lartusi",
    "lilia": "lilia",
    "misi": "misi",
    "atomix": "atomix",
    "cote": "cote-korean-steakhouse",
    "estela": "estela",
    "balthazar": "balthazar",
    "pastis": "pastis",
    "frenchette": "frenchette",
    "the-modern": "the-modern",
    "daniel": "daniel",
    "torrisi": "torrisi",
    "via-carota": "via-carota",
    "saint-julivert": "saint-julivert-fisherie",
    "lodi": "lodi",
    "shukette": "shukette",
}

# Restaurants that don't take Resy reservations.
_NON_RESY: dict[str, dict] = {
    "raos": {"reason": "Rao's tables are owned. No public reservations.", "url": None},
    "lucali": {"reason": "Walk-in only — list opens at 5pm.", "url": None},
    "kjun": {"reason": "Tickets only on Tock.", "url": "https://www.exploretock.com/kjun-nyc"},
    "per-se": {"reason": "OpenTable — try the salon menu.", "url": "https://www.opentable.com/r/per-se-new-york"},
}


def build_booking_url(
    restaurant_id: str,
    *,
    dt: datetime,
    party_size: int,
) -> dict:
    """Returns a dict describing the booking handoff.

    Keys:
      url: str | None — the deep link to tap, if any
      platform: str — "resy" | "tock" | "opentable" | "phone" | "walk-in"
      note: str | None — explanation when no URL is available
    """
    slug = _RESY_SLUGS.get(restaurant_id)
    if slug:
        params = urlencode(
            {
                "date": dt.date().isoformat(),
                "seats": party_size,
            }
        )
        return {
            "url": f"https://resy.com/cities/new-york-ny/venues/{slug}?{params}",
            "platform": "resy",
            "note": None,
        }

    if restaurant_id in _NON_RESY:
        info = _NON_RESY[restaurant_id]
        return {
            "url": info.get("url"),
            "platform": "tock" if "tock.com" in (info.get("url") or "")
                         else "opentable" if "opentable.com" in (info.get("url") or "")
                         else "phone" if info["reason"].startswith("Walk")
                         else "phone",
            "note": info["reason"],
        }

    # Default: assume Resy with id-as-slug. Worst case the link 404s and the
    # user can search; better than no handoff.
    params = urlencode({"date": dt.date().isoformat(), "seats": party_size})
    return {
        "url": f"https://resy.com/cities/new-york-ny/venues/{restaurant_id}?{params}",
        "platform": "resy",
        "note": None,
    }
