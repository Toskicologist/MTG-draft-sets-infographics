"""Fetch SOS card data from 17Lands JSON API and save as CSV.

The 17Lands page at https://www.17lands.com/card_data?expansion=SOS&format=PremierDraft
backs onto a public JSON endpoint. We hit that directly instead of automating a
browser, which is faster, more reliable, and avoids any browser dependencies.

Output CSV matches byte-for-byte the format of CSVs the user manually exported
from the 17Lands "Export Data" button:
  - UTF-8 with BOM
  - LF line endings
  - All fields quoted
  - 19 columns in the documented order
  - Empty cells for cards with insufficient sample size
"""

from __future__ import annotations

import csv
import io
import json
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from . import config


CSV_HEADERS = [
    "Name", "Color", "Rarity", "# Seen", "ALSA", "# Picked", "ATA",
    "# GP", "% GP", "GP WR", "# OH", "OH WR", "# GD", "GD WR",
    "# GIH", "GIH WR", "# GNS", "GNS WR", "IIH",
]

RARITY_MAP = {"mythic": "M", "rare": "R", "uncommon": "U", "common": "C"}


def _fmt_int(v) -> str:
    if v is None:
        return ""
    return str(int(v))


def _fmt_float2(v) -> str:
    """Two decimal places, e.g. 1.75. Empty if None."""
    if v is None:
        return ""
    return f"{v:.2f}"


def _fmt_pct1(v) -> str:
    """Format a 0-1 fraction as 'XX.X%'. Empty if None."""
    if v is None:
        return ""
    return f"{v * 100:.1f}%"


def _fmt_pp1(v) -> str:
    """Format a 0-1 fraction as 'X.Xpp' (percentage points). Empty if None."""
    if v is None:
        return ""
    return f"{v * 100:.1f}pp"


def _row_from_json(card: dict) -> list[str]:
    """Convert one JSON card object into a list of CSV cells (strings)."""
    return [
        card.get("name", ""),
        card.get("color", ""),
        RARITY_MAP.get(card.get("rarity", ""), card.get("rarity", "")),
        _fmt_int(card.get("seen_count")),
        _fmt_float2(card.get("avg_seen")),
        _fmt_int(card.get("pick_count")),
        _fmt_float2(card.get("avg_pick")),
        _fmt_int(card.get("game_count")),
        _fmt_pct1(card.get("play_rate")),
        _fmt_pct1(card.get("win_rate")),
        _fmt_int(card.get("opening_hand_game_count")),
        _fmt_pct1(card.get("opening_hand_win_rate")),
        _fmt_int(card.get("drawn_game_count")),
        _fmt_pct1(card.get("drawn_win_rate")),
        _fmt_int(card.get("ever_drawn_game_count")),
        _fmt_pct1(card.get("ever_drawn_win_rate")),
        _fmt_int(card.get("never_drawn_game_count")),
        _fmt_pct1(card.get("never_drawn_win_rate")),
        _fmt_pp1(card.get("drawn_improvement_win_rate")),
    ]


def _build_url(expansion: str, fmt: str, start_date: str) -> str:
    qs = urllib.parse.urlencode({
        "expansion": expansion,
        "format": fmt,
        "start_date": start_date,
    })
    return f"{config.LANDS_API_URL}?{qs}"


def _fetch_json(url: str, timeout: int = 60) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _build_csv_text(cards: list[dict]) -> str:
    """Render the list of card dicts as a CSV string in the exact 17Lands format."""
    buf = io.StringIO(newline="")
    # csv.QUOTE_ALL makes every field quoted, matching 17Lands export style.
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow(CSV_HEADERS)
    for card in cards:
        writer.writerow(_row_from_json(card))
    return buf.getvalue()


def _make_filename(prefix: str = "SOS", now: datetime | None = None) -> str:
    """Filename pattern matches the user's preferred convention:
        <PREFIX> card-ratings-YYYY-MM-DD THHMM.csv
    e.g. "SOS card-ratings-2026-05-02 T1553.csv" or "MSH card-ratings-...".
    """
    now = now or datetime.now()
    return f"{prefix} card-ratings-{now:%Y-%m-%d} T{now:%H%M}.csv"


def fetch_and_save(
    output_dir: Path | None = None,
    start_date: str | None = None,
    expansion: str | None = None,
    fmt: str | None = None,
) -> Path:
    """Download 17Lands data for one expansion and save as CSV. Returns the saved Path.

    The CSV filename is prefixed with the expansion code (e.g. "MSH card-ratings-..."),
    matching the set-prefixed convention used across mtg/shared-data/17lands exports/.
    """
    output_dir = output_dir or config.LANDS_EXPORTS_DIR
    start_date = start_date or config.SOS_START_DATE
    expansion = expansion or config.SOS_EXPANSION
    fmt = fmt or config.SOS_FORMAT

    output_dir.mkdir(parents=True, exist_ok=True)

    url = _build_url(expansion, fmt, start_date)
    print(f"Fetching: {url}")

    cards = _fetch_json(url)
    print(f"  Got {len(cards)} cards")

    csv_text = _build_csv_text(cards)
    # Match the user's manually-exported format exactly: no trailing newline.
    csv_text = csv_text.rstrip("\n")
    out_path = output_dir / _make_filename(prefix=expansion)

    # UTF-8 BOM + LF line endings to match the user's manually-exported files exactly.
    with open(out_path, "wb") as f:
        f.write(b"\xef\xbb\xbf")
        f.write(csv_text.encode("utf-8"))

    print(f"  Saved: {out_path.name}")
    return out_path


if __name__ == "__main__":
    fetch_and_save()
