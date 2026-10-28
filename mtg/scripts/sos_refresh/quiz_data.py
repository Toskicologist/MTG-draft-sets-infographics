"""quiz_data.py - the 17Lands quiz's card data, kept outside the pages.

Since 2026-10-24 the beta quiz pages (17lands-quiz/quiz-beta.html and
pack-beta.html) embed no card data. They load data/quiz-data.js first, which
sets window.QUIZ_DATA, and build their set list from it. So the page code never
changes on a data refresh (it can be precompiled and cached), and a new set
needs no code change: discover() adds it to the file.

File shape (schema 1):

    window.QUIZ_DATA = {
      "schema": 1,
      "updated": "2026-10-24T06:12Z",           # last write, UTC
      "order": ["FRA", "HOB", ...],             # set selector order, newest first
      "sets": {
        "FRA": {"name": "FRA (Reality Fracture)", "shortName": "FRA",
                "expansion": "FRA", "format": "PremierDraft",   # 17Lands query
                "draftFormat": "...",                           # optional label
                "ratingsLink": "https://www.17lands.com/card_data?...",
                "released": "2026-09-29",       # 17Lands data start (digital release)
                "visibleFrom": "2026-10-14",    # end of the 17Lands embargo
                "dataDate": "2026-10-24 UTC", "dataTimestamp": "2026-10-24 UTC",
                "icon": {"viewBox": "...", "path": "..."},     # optional
                "cards": [{name, color, type, rarity, gihWr, alsa, gihN?, gpWr?,
                           gpN?, img?, num?, printSet?, altImg?, imgV?, altImgV?,
                           set}, ...]},
        ...},
      "log": [{"date", "set", "event", "cards", "source"}, ...]   # newest first
    };

Cards are a superset: every card 17Lands lists, including ones below its ~500-game
threshold (gihWr null, with gihN/gpWr for the pack page). The card quiz drops
those when it loads, as it always has.

Written as JSON inside a .js file so the pages still work opened from disk
(fetch() is blocked on file://). json.dumps output is a valid JS literal; '<' is
escaped as well so nothing in it can read as markup.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sos_refresh import config, quiz_updater
from sos_refresh.fetch_17lands import _UNSAFE_TEXT_RE

SCHEMA = 1
LOG_LIMIT = 120
_PREFIX = "window.QUIZ_DATA = "
_HEADER = ("// 17Lands quiz card data, loaded by quiz-beta.html and pack-beta.html.\n"
           "// Written by mtg/scripts/refresh_quiz_data.py (daily GitHub Action). Do not edit by hand.\n")
_USER_AGENT = "MTG-draft-sets-quiz-updater/1.0"
SCRYFALL_SET_URL = "https://api.scryfall.com/sets/{code}"


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def load(path: Path | None = None) -> dict:
    path = Path(path or config.QUIZ_DATA_JS)
    text = path.read_text(encoding="utf-8")
    start = text.index(_PREFIX) + len(_PREFIX)
    body = text[start:].rstrip().rstrip(";")
    data = json.loads(body)
    if data.get("schema") != SCHEMA:
        raise ValueError(f"{path.name}: schema {data.get('schema')!r}, expected {SCHEMA}")
    return data


def _js(value) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(", ", ": ")).replace("<", "\\u003c")


def dumps(data: dict) -> str:
    """One card per line, so a daily refresh diffs line by line in git."""
    validate(data)
    out = [_HEADER, _PREFIX, "{\n"]
    out.append(f'"schema": {SCHEMA},\n"updated": {_js(data["updated"])},\n')
    out.append(f'"order": {_js(data["order"])},\n"sets": {{\n')
    codes = list(data["sets"])
    for i, code in enumerate(codes):
        s = data["sets"][code]
        meta = {k: v for k, v in s.items() if k != "cards"}
        out.append(f'{_js(code)}: {_js(meta)[:-1]}, "cards": [\n')
        out.append(",\n".join(_js(c) for c in s["cards"]))
        out.append("\n]}" + ("," if i < len(codes) - 1 else "") + "\n")
    out.append('},\n"log": [\n')
    out.append(",\n".join(_js(e) for e in data.get("log", [])))
    out.append("\n]\n};\n")
    return "".join(out)


def save(data: dict, path: Path | None = None) -> None:
    path = Path(path or config.QUIZ_DATA_JS)
    text = dumps(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    # Round-trip check: what the pages will read is what we meant to write.
    if load(path) != json.loads(json.dumps(data)):
        raise ValueError(f"{path.name}: round-trip check failed after write")


def validate(data: dict) -> None:
    """Refuse to write anything the pages can't use, or that carries text no card
    name should (the same rule fetch_17lands applies to what 17Lands sends)."""
    if set(data["order"]) - set(data["sets"]):
        raise ValueError(f"order lists unknown sets: {sorted(set(data['order']) - set(data['sets']))}")
    for code, s in data["sets"].items():
        if not re.fullmatch(r"[A-Z0-9]{2,6}", code):
            raise ValueError(f"bad set code {code!r}")
        for key in ("name", "shortName", "ratingsLink", "dataDate", "cards"):
            if key not in s:
                raise ValueError(f"{code}: missing {key}")
        if not s["ratingsLink"].startswith("https://www.17lands.com/"):
            raise ValueError(f"{code}: ratingsLink is not a 17lands.com URL")
        if not isinstance(s["cards"], list) or not s["cards"]:
            raise ValueError(f"{code}: no cards")
        for c in s["cards"]:
            for field in ("name", "color", "rarity"):
                v = c.get(field)
                if not isinstance(v, str) or _UNSAFE_TEXT_RE.search(v):
                    raise ValueError(f"{code}: card {c.get('name')!r} has a bad {field}: {v!r}")
            if c.get("gihWr") is not None and not isinstance(c["gihWr"], (int, float)):
                raise ValueError(f"{code}: card {c['name']!r} has a non-numeric gihWr")


# ---------------------------------------------------------------------------
# Card records
# ---------------------------------------------------------------------------

# Field order of a card record in the file (quiz_updater._format_card_js order).
CARD_FIELDS = ("name", "color", "type", "rarity", "gihWr", "alsa", "gihN", "gpWr", "gpN",
               "img") + quiz_updater._EXTRA_FIELDS + ("set",)


def ordered(card: dict) -> dict:
    """The card with its fields in CARD_FIELDS order (unknown fields last), so
    every writer produces the same line for the same card."""
    rec = {k: card[k] for k in CARD_FIELDS if k in card}
    rec.update({k: v for k, v in card.items() if k not in rec})
    return rec


def card_record(card: dict, code: str) -> dict:
    """quiz_updater.build_cards output -> the page's card object, with the
    fields the embedded arrays had (quiz_updater._format_card_js, extended)."""
    rec = {k: card[k] for k in ("name", "color", "type", "rarity", "gihWr", "alsa")}
    if "gihN" in card:
        rec["gihN"] = int(card.get("gihN") or 0)
        if card["gihWr"] is None and card.get("gpWr") is not None:
            rec["gpWr"] = card["gpWr"]
            rec["gpN"] = int(card.get("gpN") or 0)
    if card.get("img"):
        rec["img"] = card["img"]
    for field in quiz_updater._EXTRA_FIELDS:
        if card.get(field):
            rec[field] = card[field]
    rec["set"] = code
    return ordered(rec)


def _known(cards: list[dict]) -> tuple[dict, dict, dict]:
    """What the current file knows per card: types, image ids, extra fields."""
    types = {c["name"]: c.get("type", "") for c in cards}
    imgs = {c["name"]: c["img"] for c in cards if c.get("img")}
    extras = {}
    for c in cards:
        found = {f: c[f] for f in quiz_updater._EXTRA_FIELDS if c.get(f)}
        if found:
            extras[c["name"]] = found
    return types, imgs, extras


def scored(cards: list[dict]) -> int:
    return sum(1 for c in cards if isinstance(c.get("gihWr"), (int, float)) and c["gihWr"] > 0)


def refresh_set(data: dict, code: str, csv_path: Path, data_date: str,
                force: bool = False) -> dict:
    """Rebuild one set's cards from a 17Lands CSV, in place in `data`.

    Refuses (ValueError) when the scored-card count falls below 90% of what the
    file has: 17Lands' all-time counts only grow, so a drop that size is a bad
    export, not news. force=True skips that check (build_cards' own 150-card
    floor still applies)."""
    s = data["sets"][code]
    types, imgs, extras = _known(s["cards"])
    cards = quiz_updater.build_cards(csv_path, code, types, imgs, extras, include_no_data=True)
    new = [card_record(c, code) for c in cards]
    old_scored, new_scored = scored(s["cards"]), scored(new)
    if not force and new_scored < 0.9 * old_scored:
        raise ValueError(f"{code}: scored cards would fall {old_scored} -> {new_scored}; "
                         f"refusing (re-run with --force if 17Lands really dropped them)")
    old_names, new_names = {c["name"] for c in s["cards"]}, {c["name"] for c in new}
    result = {"set": code, "old": len(s["cards"]), "new": len(new),
              "old_scored": old_scored, "new_scored": new_scored,
              "added": sorted(new_names - old_names), "removed": sorted(old_names - new_names),
              "changed": new != s["cards"] or s["dataDate"] != data_date}
    s["cards"] = new
    s["dataDate"] = s["dataTimestamp"] = data_date
    _log(data, code, "refresh", len(new), Path(csv_path).name)
    return result


def _log(data: dict, code: str, event: str, cards: int, source: str) -> None:
    entry = {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "set": code,
             "event": event, "cards": cards, "source": source}
    data["log"] = ([entry] + data.get("log", []))[:LOG_LIMIT]


def touch(data: dict) -> None:
    data["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def sets_to_refresh(data: dict, newest: int | None = None) -> list[str]:
    """The `newest` sets by 17Lands start date (sets without one never refresh)."""
    newest = config.QUIZ_REFRESH_NEWEST if newest is None else newest
    dated = [c for c, s in data["sets"].items() if s.get("released")]
    return sorted(dated, key=lambda c: data["sets"][c]["released"], reverse=True)[:newest]


# ---------------------------------------------------------------------------
# New-set discovery
# ---------------------------------------------------------------------------

def _get(url: str, accept: str = "application/json", attempts: int = 3) -> bytes:
    last: Exception | None = None
    for attempt in range(attempts):
        if attempt:
            time.sleep(5 * 3 ** (attempt - 1))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": accept})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise
            last = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
    raise RuntimeError(f"GET {url} failed after {attempts} attempts: {last}")


def scryfall_set(code: str) -> dict | None:
    try:
        return json.loads(_get(SCRYFALL_SET_URL.format(code=code.lower())))
    except urllib.error.HTTPError:
        return None


def scryfall_icon(svg_url: str) -> dict | None:
    """{viewBox, path} from a Scryfall set icon, when it is plain paths (no
    transforms, groups or other shapes - the pages draw a single <path>)."""
    try:
        svg = _get(svg_url, accept="image/svg+xml").decode("utf-8")
    except Exception:  # noqa: BLE001 - an icon is optional
        return None
    tags = set(re.findall(r"<([a-zA-Z]+)[\s>/]", svg))
    vb = re.search(r'viewBox="([0-9.\s-]+)"', svg)
    paths = re.findall(r'<path[^>]*\sd="([^"]+)"', svg)
    if tags - {"svg", "path"} or "transform" in svg or not vb or not paths:
        return None
    return {"viewBox": vb.group(1).strip(), "path": " ".join(paths)}


def discover_candidates(data: dict, today: date | None = None) -> tuple[list[dict], list[str]]:
    """New sets worth adding. Returns (candidates, notes): each candidate has
    code/start/name/released_at/visible_from/icon_url; notes say why near misses
    were skipped (embargo, not on Scryfall...)."""
    today = today or datetime.now(timezone.utc).date()
    filters = json.loads(_get(config.LANDS_FILTERS_URL))
    starts = filters.get("start_dates", {})
    formats = filters.get("formats_by_expansion", {})
    candidates, notes = [], []
    for code in filters.get("expansions", []):
        if code in data["sets"] or code in config.QUIZ_DISCOVER_IGNORE:
            continue
        if not re.fullmatch(r"[A-Z0-9]{3}", code):   # Alchemy (Y26FRA), cubes, events
            continue
        start = starts.get(code)
        if not start or "PremierDraft" not in formats.get(code, []):
            continue
        start_d = date.fromisoformat(start[:10])
        if (today - start_d).days > config.QUIZ_DISCOVER_MAX_AGE_DAYS:
            continue
        time.sleep(0.1)  # Scryfall asks for 50-100 ms between requests
        sc = scryfall_set(code)
        if not sc:
            notes.append(f"{code}: not on Scryfall as '{code.lower()}' - add it by hand")
            continue
        if sc.get("set_type") not in config.QUIZ_DISCOVER_SET_TYPES:
            notes.append(f"{code}: Scryfall set_type {sc.get('set_type')!r} is not a draft set")
            continue
        released = max(start_d, date.fromisoformat(sc["released_at"]))
        visible = released + timedelta(days=config.QUIZ_EMBARGO_DAYS)
        if today < visible:
            notes.append(f"{code} ({sc['name']}): waiting for the 17Lands embargo to end on {visible}")
            continue
        candidates.append({"code": code, "start": start_d.isoformat(), "name": sc["name"],
                           "visible_from": visible.isoformat(), "icon_url": sc.get("icon_svg_uri")})
    return candidates, notes


def add_set(data: dict, cand: dict, csv_path: Path, data_date: str) -> dict:
    """Add a discovered set (newest first in the selector). Raises ValueError,
    via build_cards, while 17Lands has fewer than 150 scored cards for it."""
    code = cand["code"]
    cards = quiz_updater.build_cards(csv_path, code, {}, {}, {}, include_no_data=True)
    entry = {
        "name": f"{code} ({cand['name']})",
        "shortName": code,
        "expansion": code,
        "format": "PremierDraft",
        "ratingsLink": f"https://www.17lands.com/card_data?expansion={code}&format=PremierDraft",
        "released": cand["start"],
        "visibleFrom": cand["visible_from"],
        "dataDate": data_date,
        "dataTimestamp": data_date,
    }
    icon = scryfall_icon(cand["icon_url"]) if cand.get("icon_url") else None
    if icon:
        entry["icon"] = icon
    entry["cards"] = [card_record(c, code) for c in cards]
    data["sets"][code] = entry
    data["order"] = [code] + [c for c in data["order"] if c != code]
    _log(data, code, "added", len(entry["cards"]), Path(csv_path).name)
    return {"set": code, "new": len(entry["cards"]), "new_scored": scored(entry["cards"]),
            "icon": bool(icon)}
