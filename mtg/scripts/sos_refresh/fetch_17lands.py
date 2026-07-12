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
import re
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
    # 17Lands' new /api/card_data endpoint (2026-07) takes event_type +
    # time_period instead of format + start_date. start_date is kept in the
    # signature so callers/config stay unchanged, but ALL_TIME supersedes it
    # (our start dates were the sets' release dates, i.e. all-time anyway).
    del start_date
    qs = urllib.parse.urlencode({
        "expansion": expansion,
        "event_type": fmt,
        "time_period": "ALL_TIME",
    })
    return f"{config.LANDS_API_URL}?{qs}"


def _fetch_json(url: str, timeout: int = 60) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read())
    # New endpoint wraps the card list: {"data": [...]}. Old endpoint returned
    # a bare list; accept both so a rollback of LANDS_API_URL keeps working.
    if isinstance(payload, dict):
        return payload["data"]
    return payload


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


def images_sidecar_filename(csv_filename: str) -> str:
    """Derive the images-sidecar filename from a card-ratings CSV filename.

    Same basename, "card-ratings" -> "card-images", ".csv" -> ".json", e.g.
        "SOS card-ratings-2026-07-11 T1200.csv" -> "SOS card-images-2026-07-11 T1200.json"

    Exposed (no leading underscore) because quiz_updater.py also uses this
    transform to locate the sidecar for an arbitrary CSV path.
    Raises ValueError if csv_filename doesn't match the expected pattern
    (e.g. a user-downloaded CSV with a different name).
    """
    if not csv_filename.endswith('.csv'):
        raise ValueError(f"Expected a .csv filename, got: {csv_filename!r}")
    stem = csv_filename[:-4]
    if 'card-ratings' not in stem:
        raise ValueError(f"Expected 'card-ratings' in filename, got: {csv_filename!r}")
    return stem.replace('card-ratings', 'card-images', 1) + '.json'


# Matches the Scryfall image UUID out of a cards.scryfall.io URL, e.g.
#   https://cards.scryfall.io/normal/front/7/5/75961d36-acf6-425f-9698-0bf52af74f31.jpg?1775937223
_IMAGE_UUID_RE = re.compile(
    r'/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\.jpg'
)


def _extract_images(cards: list[dict]) -> dict[str, str]:
    """Map card name -> bare Scryfall image UUID, parsed from each card's 'url'.
    Skips cards with a missing/empty url or a url that doesn't match the expected
    cards.scryfall.io pattern."""
    images: dict[str, str] = {}
    for card in cards:
        name = card.get("name")
        url = card.get("url")
        if not name or not url:
            continue
        m = _IMAGE_UUID_RE.search(url)
        if not m:
            continue
        images[name] = m.group(1)
    return images


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

    # Sidecar: name -> bare Scryfall image UUID, same timestamp/name base as the CSV.
    images = _extract_images(cards)
    images_path = output_dir / images_sidecar_filename(out_path.name)
    images_json = json.dumps(images, ensure_ascii=False, sort_keys=True)
    images_path.write_text(images_json, encoding="utf-8")
    print(f"  Saved images sidecar: {images_path.name} ({len(images)} cards)")

    return out_path


if __name__ == "__main__":
    fetch_and_save()
