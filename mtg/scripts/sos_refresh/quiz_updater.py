#!/usr/bin/env python3
"""
quiz_updater.py — Regenerate SOS_CARDS array and update metadata in quiz-beta.html.

Single responsibility: given a new 17Lands CSV and a data date string, replace the
SOS_CARDS JS array in quiz-beta.html and patch SET_CONFIG.SOS.dataDate,
dataTimestamp, QUIZ_VERSION, LAST_UPDATE, and the changelog.

Public API:
    update_quiz(quiz_html_path, new_csv_path, new_data_date, dry_run=False) -> dict
"""

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sos_refresh.csv_loader import load_sos_csv
from sos_refresh import config
from sos_refresh.underover_updater import increment_version


# ---------------------------------------------------------------------------
# Type resolution helpers
# ---------------------------------------------------------------------------

def _load_sos_types() -> dict:
    """Load sos-types-mapping.json -> {card_name: type_line}."""
    p = config.SOS_TYPES_MAPPING_JSON
    if p.exists():
        return json.loads(p.read_text(encoding='utf-8'))
    return {}


def _load_scryfall_reference() -> dict:
    """Load scryfall_reference.json -> {card_name: card_obj}."""
    p = config.SCRYFALL_REFERENCE_JSON
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding='utf-8'))
    if isinstance(raw, list):
        return {card['name']: card for card in raw}
    return raw


def _extract_existing_types(html: str) -> dict:
    """
    Parse SOS_CARDS from the HTML to build {name: type} fallback dict.
    Matches both double-quoted and single-quoted object literals.
    """
    # Pattern covers: {name: "Foo", ..., type: "Bar", ...} with any field ordering.
    # We look for the type field specifically.
    types = {}
    # Scan within the SOS_CARDS block for efficiency
    m = re.search(r'const SOS_CARDS\s*=\s*\[', html)
    if not m:
        return types
    start = m.end()
    # Find the end of the array (bracket-balanced)
    depth = 1
    pos = start
    while pos < len(html) and depth > 0:
        ch = html[pos]
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
        pos += 1
    block = html[start:pos]

    # Extract name and type pairs
    # Each card line looks like: {name: "...", color: "...", type: "...", ...}
    name_re = re.compile(r'name:\s*"((?:[^"\\]|\\.)*)"')
    type_re = re.compile(r'type:\s*"((?:[^"\\]|\\.)*)"')

    # Split block by card objects
    for obj_match in re.finditer(r'\{[^{}]*\}', block):
        obj = obj_match.group()
        nm = name_re.search(obj)
        tp = type_re.search(obj)
        if nm:
            types[nm.group(1)] = tp.group(1) if tp else ''

    return types


def _resolve_type(name: str, sos_types: dict, scryfall: dict, existing: dict) -> str:
    """
    Type fallback chain matching generate-card-data.js:
      1. sos-types-mapping.json
      2. scryfall_reference.json (type_line or type)
      3. existing quiz HTML types
      4. empty string (+ warning)
    """
    if name in sos_types:
        return sos_types[name]
    if name in scryfall:
        card = scryfall[name]
        t = card.get('type_line') or card.get('type') or ''
        if t:
            return t
    if name in existing:
        t = existing[name]
        if t:
            return t
    # No type found
    print(f"WARNING: No type found for {name}")
    return ''


# ---------------------------------------------------------------------------
# JS array formatting
# ---------------------------------------------------------------------------

def _format_card_js(card: dict) -> str:
    """
    Format one card dict as a JS object literal matching the existing SOS_CARDS style:
      {name: "...", color: "...", type: "...", rarity: "...", gihWr: X.X, alsa: X.XX, set: "SOS"}

    Field ordering observed in the HTML:
      name, color, type, rarity, gihWr, alsa, set
    """
    def js_str(s: str) -> str:
        # Escape backslash and double-quotes; leave apostrophes as-is (JS double-quoted string)
        return s.replace('\\', '\\\\').replace('"', '\\"')

    name = js_str(card['name'])
    color = js_str(card['color'])
    type_ = js_str(card['type'])
    rarity = js_str(card['rarity'])

    # gihWr: 1 decimal; alsa: 2 decimals — but strip trailing zeros after decimal per observed style
    gih_wr = card['gihWr']
    alsa = card['alsa']

    # Format matching existing: e.g. 51.4, 5.71 — no trailing zeros stripped beyond precision
    gih_str = f"{gih_wr:.1f}"
    # Remove trailing zero only when result is like "59.0" -> keep as "59" to match observed "59"
    if gih_str.endswith('.0'):
        gih_str = gih_str[:-2]

    alsa_str = f"{alsa:.2f}"

    return (
        f'  {{name: "{name}", color: "{color}", type: "{type_}", '
        f'rarity: "{rarity}", gihWr: {gih_str}, alsa: {alsa_str}, set: "SOS"}}'
    )


def _build_sos_cards_block(cards: list[dict]) -> str:
    """Build the full const SOS_CARDS = [...]; block."""
    lines = ['const SOS_CARDS = [']
    for i, card in enumerate(cards):
        suffix = ',' if i < len(cards) - 1 else ''
        lines.append(_format_card_js(card) + suffix)
    lines.append('];')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML splicing helpers
# ---------------------------------------------------------------------------

def _find_sos_cards_span(html: str) -> tuple[int, int]:
    """
    Return (start, end) character offsets for the entire SOS_CARDS declaration,
    from 'const SOS_CARDS = [' through the matching '];'.
    Uses bracket-counting from the opening '['.
    Raises ValueError if not found.
    """
    open_m = re.search(r'const SOS_CARDS\s*=\s*\[', html)
    if not open_m:
        raise ValueError("Cannot find 'const SOS_CARDS = [' in quiz HTML")

    decl_start = open_m.start()
    # The '[' that opens the array
    array_open = open_m.end() - 1  # index of '['

    depth = 0
    pos = array_open
    while pos < len(html):
        ch = html[pos]
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                # closing ']' found; must be followed by ';' optionally with whitespace
                # find the ';'
                semi = html.index(';', pos)
                return decl_start, semi + 1
        pos += 1

    raise ValueError("Could not find closing '];' for SOS_CARDS array")


def _find_sos_config_block_span(html: str) -> tuple[int, int]:
    """Return (start, end) for the SOS: { ... } block within SET_CONFIG.
    Finds the SOS block that contains 'dataDate' (not the SVG icon block)."""
    # There may be multiple 'SOS: {' occurrences (e.g. SVG path data).
    # Find all and pick the one whose block contains 'dataDate'.
    for m in re.finditer(r'\bSOS:\s*\{', html):
        brace_open = html.index('{', m.start())
        depth = 0
        pos = brace_open
        while pos < len(html):
            if html[pos] == '{':
                depth += 1
            elif html[pos] == '}':
                depth -= 1
                if depth == 0:
                    block = html[m.start():pos + 1]
                    if 'dataDate' in block:
                        return m.start(), pos + 1
                    break  # wrong block, try next match
            pos += 1
    raise ValueError("Could not find SET_CONFIG SOS block containing 'dataDate'")


def _patch_set_config_sos(html: str, new_data_date: str, new_timestamp: str) -> str:
    """
    Replace dataDate and dataTimestamp inside the SET_CONFIG.SOS block.
    Matches single-quoted format used in the file.
    """
    start, end = _find_sos_config_block_span(html)
    block = html[start:end]

    block = re.sub(r"dataDate:\s*'[^']*'", f"dataDate: '{new_data_date}'", block, count=1)
    block = re.sub(r"dataTimestamp:\s*'[^']*'", f"dataTimestamp: '{new_timestamp}'", block, count=1)

    return html[:start] + block + html[end:]


def _patch_quiz_version(html: str) -> tuple[str, str, str]:
    """
    Find and patch-bump QUIZ_VERSION. Returns (new_html, old_version, new_version).
    """
    m = re.search(r"const QUIZ_VERSION\s*=\s*'([^']+)';", html)
    if not m:
        raise ValueError("Cannot find 'const QUIZ_VERSION' in quiz HTML")
    old_ver = m.group(1)
    new_ver = increment_version(old_ver)
    new_html = html[:m.start()] + f"const QUIZ_VERSION = '{new_ver}';" + html[m.end():]
    return new_html, old_ver, new_ver


def _patch_last_update(html: str, new_timestamp: str) -> tuple[str, str, str]:
    """
    Find and update LAST_UPDATE. Returns (new_html, old_value, new_value).
    LAST_UPDATE format in file: 'YYYY-MM-DD UTC' (date only).
    """
    m = re.search(r"const LAST_UPDATE\s*=\s*'([^']+)';", html)
    if not m:
        # Not present — skip gracefully
        return html, '', new_timestamp
    old_val = m.group(1)
    new_html = html[:m.start()] + f"const LAST_UPDATE = '{new_timestamp}';" + html[m.end():]
    return new_html, old_val, new_timestamp


def _add_changelog_entry(html: str, new_version: str, csv_path: Path,
                          card_count: int, today: str) -> tuple[str, str]:
    """
    Prepend a one-line entry after 'CHANGELOG:'.
    Entry format matching existing style:
      vX.Y.Z (YYYY-MM-DD UTC): DATA: Refresh SOS to <CSV filename> (<N> cards).
    Returns (new_html, entry_text).
    """
    m = re.search(r'(CHANGELOG:\s*\n)', html)
    if not m:
        raise ValueError("Cannot find 'CHANGELOG:' block in quiz HTML")

    entry = f"  v{new_version} ({today} UTC): DATA: Refresh SOS to {csv_path.name} ({card_count} cards)."
    insert_pos = m.end()
    new_html = html[:insert_pos] + entry + '\n' + html[insert_pos:]
    return new_html, entry


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def update_quiz(
    quiz_html_path: Path,
    new_csv_path: Path,
    new_data_date: str,
    dry_run: bool = False,
) -> dict:
    """
    Regenerate SOS_CARDS and update SOS metadata in quiz-beta.html.

    Returns {
      'cards_old_count': int,
      'cards_new_count': int,
      'cards_added': list[str],
      'cards_removed': list[str],
      'old_data_date': str,
      'new_data_date': str,
      'old_data_timestamp': str,
      'new_data_timestamp': str,
      'old_quiz_version': str,
      'new_quiz_version': str,
      'changelog_entry': str,
      'changes_applied': bool,
    }
    Raises ValueError if SOS_CARDS or SET_CONFIG.SOS or QUIZ_VERSION can't be located.
    """
    quiz_html_path = Path(quiz_html_path)
    new_csv_path = Path(new_csv_path)

    # --- Read HTML ---
    html = quiz_html_path.read_text(encoding='utf-8')

    # --- Load type resolution sources ---
    sos_types = _load_sos_types()
    scryfall = _load_scryfall_reference()
    existing_types = _extract_existing_types(html)

    # --- Parse existing SOS_CARDS for old_count and added/removed diff ---
    old_names: set[str] = set(existing_types.keys())
    cards_old_count = len(old_names)

    # --- Extract old metadata for result dict ---
    try:
        sos_config_start, sos_block_end = _find_sos_config_block_span(html)
    except ValueError as e:
        raise ValueError(f"Cannot find SET_CONFIG.SOS block: {e}") from e
    sos_block = html[sos_config_start:sos_block_end]

    date_m = re.search(r"dataDate:\s*'([^']*)'", sos_block)
    ts_m = re.search(r"dataTimestamp:\s*'([^']*)'", sos_block)
    old_data_date = date_m.group(1) if date_m else ''
    old_data_timestamp = ts_m.group(1) if ts_m else ''

    ver_m = re.search(r"const QUIZ_VERSION\s*=\s*'([^']+)';", html)
    if not ver_m:
        raise ValueError("Cannot find QUIZ_VERSION in quiz HTML")
    old_quiz_version = ver_m.group(1)

    # --- Load CSV ---
    csv_cards = load_sos_csv(new_csv_path, min_gih=0)

    # --- Build card dicts with resolved types ---
    new_cards = []
    for row in csv_cards:
        name = row['name']
        color = row['color']
        type_ = _resolve_type(name, sos_types, scryfall, existing_types)
        rarity = row['rarity']
        gih_wr = round(row['gih_wr'], 1)
        alsa = round(row['alsa'], 2)
        new_cards.append({
            'name': name,
            'color': color,
            'type': type_,
            'rarity': rarity,
            'gihWr': gih_wr,
            'alsa': alsa,
        })

    # Already sorted by csv_loader, but ensure alphabetical
    new_cards.sort(key=lambda c: c['name'])

    new_names: set[str] = {c['name'] for c in new_cards}
    cards_added = sorted(new_names - old_names)
    cards_removed = sorted(old_names - new_names)
    cards_new_count = len(new_cards)

    # --- Compute new metadata ---
    now_utc = datetime.now(timezone.utc)
    today = now_utc.strftime('%Y-%m-%d')
    new_data_timestamp = new_data_date  # use caller-supplied date as timestamp too
    new_version = increment_version(old_quiz_version)

    # Build changelog entry text (needs new_version)
    changelog_entry = (
        f"v{new_version} ({today} UTC): DATA: Refresh SOS to "
        f"{new_csv_path.name} ({cards_new_count} cards)."
    )

    result = {
        'cards_old_count': cards_old_count,
        'cards_new_count': cards_new_count,
        'cards_added': cards_added,
        'cards_removed': cards_removed,
        'old_data_date': old_data_date,
        'new_data_date': new_data_date,
        'old_data_timestamp': old_data_timestamp,
        'new_data_timestamp': new_data_timestamp,
        'old_quiz_version': old_quiz_version,
        'new_quiz_version': new_version,
        'changelog_entry': changelog_entry,
        'changes_applied': False,
    }

    if dry_run:
        return result

    # --- Build new SOS_CARDS JS block ---
    new_block = _build_sos_cards_block(new_cards)

    # --- Splice SOS_CARDS into HTML ---
    span_start, span_end = _find_sos_cards_span(html)
    html = html[:span_start] + new_block + html[span_end:]

    # --- Patch SET_CONFIG.SOS ---
    html = _patch_set_config_sos(html, new_data_date, new_data_timestamp)

    # --- Bump QUIZ_VERSION ---
    html, _old_ver, _new_ver = _patch_quiz_version(html)
    assert _old_ver == old_quiz_version, f"Version mismatch: {_old_ver!r} vs {old_quiz_version!r}"
    assert _new_ver == new_version

    # --- Update LAST_UPDATE ---
    html, _old_lu, _new_lu = _patch_last_update(html, new_data_date)

    # --- Add changelog entry ---
    html, _entry = _add_changelog_entry(html, new_version, new_csv_path, cards_new_count, today)
    assert _entry.strip() == changelog_entry.strip()

    # --- Write to disk ---
    quiz_html_path.write_text(html, encoding='utf-8', newline='')
    result['changes_applied'] = True

    # --- Validate splice integrity (Python-side; node --check rejects .html in Node 24+) ---
    written = quiz_html_path.read_text(encoding='utf-8')
    sos_match = re.search(r'const SOS_CARDS\s*=\s*\[', written)
    if not sos_match:
        raise ValueError("Validation failed: const SOS_CARDS not found after write.")
    # Count card entries inside SOS_CARDS using bracket matching
    start = sos_match.end()
    depth = 1  # we're inside the array's outer [
    i = start
    n = len(written)
    while i < n and depth > 0:
        c = written[i]
        if c == '[':
            depth += 1
        elif c == ']':
            depth -= 1
        i += 1
    if depth != 0:
        raise ValueError(
            "Validation failed: SOS_CARDS array brackets unbalanced after splice."
        )
    sos_block = written[start:i - 1]
    actual_card_count = len(re.findall(r'\{name:', sos_block))
    if actual_card_count != len(new_cards):
        raise ValueError(
            f"Validation failed: expected {len(new_cards)} cards in SOS_CARDS, "
            f"found {actual_card_count}."
        )
    # Sanity-check a few constants are still intact
    for needed in ('const QUIZ_VERSION', 'const SET_CONFIG', 'SOS:'):
        if needed not in written:
            raise ValueError(f"Validation failed: '{needed}' missing after write.")

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    import json as _json

    args = sys.argv[1:]
    if len(args) < 3:
        print(
            "Usage: python -m sos_refresh.quiz_updater <quiz_html> <csv_path> <data_date> [--dry-run]"
        )
        sys.exit(1)

    result = update_quiz(
        quiz_html_path=Path(args[0]),
        new_csv_path=Path(args[1]),
        new_data_date=args[2],
        dry_run='--dry-run' in args,
    )
    print(_json.dumps(result, indent=2))
