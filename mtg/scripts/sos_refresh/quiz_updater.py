#!/usr/bin/env python3
"""
quiz_updater.py — Regenerate a set's <SET>_CARDS array and metadata in the quiz.

Single responsibility: given a set code, a new 17Lands CSV and a data date string,
replace the <SET>_CARDS JS array in quiz-beta.html and patch
SET_CONFIG.<SET>.dataDate / dataTimestamp, QUIZ_VERSION, LAST_UPDATE, and the changelog.

The module is set-agnostic: pass set_code='SOS' (default) or set_code='MSH'. Per-set
paths (Scryfall snapshot, types mapping) come from config.SET_REFRESH[set_code].

Public API:
    update_quiz(quiz_html_path, new_csv_path, new_data_date, dry_run=False,
                set_code='SOS') -> dict
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from sos_refresh.csv_loader import load_sos_csv
from sos_refresh import config
from sos_refresh.underover_updater import increment_version


# ---------------------------------------------------------------------------
# Type resolution helpers
# ---------------------------------------------------------------------------

def _load_types(set_code: str) -> dict:
    """Load the set's types-mapping.json -> {card_name: type_line}, if configured.
    Returns {} when no mapping file is configured or present (e.g. MSH)."""
    p = config.SET_REFRESH.get(set_code, {}).get('types_mapping')
    if p and Path(p).exists():
        return json.loads(Path(p).read_text(encoding='utf-8'))
    return {}


def _load_scryfall_reference(set_code: str) -> dict:
    """Load the set's Scryfall snapshot -> {card_name: card_obj}.

    Handles the three shapes we store snapshots in:
      - a bare list of card objects,
      - {"cards": [...]} (the fetch-*-cards.js snapshot shape, used by MSH),
      - {name: card_obj} already keyed by name.
    For double-faced cards ("Front // Back") the front-face name is also registered
    as a key, because 17Lands reports DFCs under the front-face name only.
    Returns {} if the snapshot file is absent (CI falls back to embedded types).
    """
    p = config.SET_REFRESH.get(set_code, {}).get('scryfall_reference')
    if not p or not Path(p).exists():
        return {}
    raw = json.loads(Path(p).read_text(encoding='utf-8'))

    if isinstance(raw, dict) and 'cards' in raw:
        cards = raw['cards']
    elif isinstance(raw, list):
        cards = raw
    else:
        # Already a {name: card_obj} dict
        cards = list(raw.values())

    ref: dict = {}
    for card in cards:
        name = card.get('name')
        if not name:
            continue
        ref[name] = card
        # 17Lands uses the front-face name for DFCs; register it too.
        if ' // ' in name:
            ref.setdefault(name.split(' // ')[0], card)
    return ref


def _extract_existing_types(html: str, set_code: str) -> dict:
    """
    Parse <SET>_CARDS from the HTML to build {name: type} fallback dict.
    Matches both double-quoted and single-quoted object literals.
    """
    types = {}
    m = re.search(rf'const {set_code}_CARDS\s*=\s*\[', html)
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

    name_re = re.compile(r'name:\s*"((?:[^"\\]|\\.)*)"')
    type_re = re.compile(r'type:\s*"((?:[^"\\]|\\.)*)"')

    for obj_match in re.finditer(r'\{[^{}]*\}', block):
        obj = obj_match.group()
        nm = name_re.search(obj)
        tp = type_re.search(obj)
        if nm:
            types[nm.group(1)] = tp.group(1) if tp else ''

    return types


def _resolve_type(name: str, types_map: dict, scryfall: dict, existing: dict) -> str:
    """
    Type fallback chain matching generate-card-data.js:
      1. <set>-types-mapping.json
      2. scryfall snapshot (type_line or type)
      3. existing quiz HTML types
      4. empty string (+ warning)
    """
    if name in types_map:
        return types_map[name]
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

def _format_card_js(card: dict, set_code: str) -> str:
    """
    Format one card dict as a JS object literal matching the existing <SET>_CARDS style:
      {name: "...", color: "...", type: "...", rarity: "...", gihWr: X.X, alsa: X.XX, set: "<SET>"}
    """
    def js_str(s: str) -> str:
        # Escape backslash and double-quotes; leave apostrophes as-is (JS double-quoted string)
        return s.replace('\\', '\\\\').replace('"', '\\"')

    name = js_str(card['name'])
    color = js_str(card['color'])
    type_ = js_str(card['type'])
    rarity = js_str(card['rarity'])

    gih_wr = card['gihWr']
    alsa = card['alsa']

    # Format matching existing: e.g. 51.4, 5.71; strip a trailing ".0" like the file does.
    gih_str = f"{gih_wr:.1f}"
    if gih_str.endswith('.0'):
        gih_str = gih_str[:-2]

    alsa_str = f"{alsa:.2f}"

    return (
        f'  {{name: "{name}", color: "{color}", type: "{type_}", '
        f'rarity: "{rarity}", gihWr: {gih_str}, alsa: {alsa_str}, set: "{set_code}"}}'
    )


def _build_cards_block(cards: list[dict], set_code: str) -> str:
    """Build the full const <SET>_CARDS = [...]; block."""
    lines = [f'const {set_code}_CARDS = [']
    for i, card in enumerate(cards):
        suffix = ',' if i < len(cards) - 1 else ''
        lines.append(_format_card_js(card, set_code) + suffix)
    lines.append('];')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML splicing helpers
# ---------------------------------------------------------------------------

def _find_cards_span(html: str, set_code: str) -> tuple[int, int]:
    """
    Return (start, end) character offsets for the entire <SET>_CARDS declaration,
    from 'const <SET>_CARDS = [' through the matching '];'.
    Raises ValueError if not found.
    """
    open_m = re.search(rf'const {set_code}_CARDS\s*=\s*\[', html)
    if not open_m:
        raise ValueError(f"Cannot find 'const {set_code}_CARDS = [' in quiz HTML")

    decl_start = open_m.start()
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
                semi = html.index(';', pos)
                return decl_start, semi + 1
        pos += 1

    raise ValueError(f"Could not find closing '];' for {set_code}_CARDS array")


def _find_config_block_span(html: str, set_code: str) -> tuple[int, int]:
    """Return (start, end) for the <SET>: { ... } block within SET_CONFIG.
    Finds the block that contains 'dataDate' (not e.g. an SVG icon block)."""
    for m in re.finditer(rf'\b{set_code}:\s*\{{', html):
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
    raise ValueError(f"Could not find SET_CONFIG {set_code} block containing 'dataDate'")


def _patch_set_config(html: str, set_code: str, new_data_date: str, new_timestamp: str) -> str:
    """Replace dataDate and dataTimestamp inside the SET_CONFIG.<SET> block."""
    start, end = _find_config_block_span(html, set_code)
    block = html[start:end]

    block = re.sub(r"dataDate:\s*'[^']*'", f"dataDate: '{new_data_date}'", block, count=1)
    block = re.sub(r"dataTimestamp:\s*'[^']*'", f"dataTimestamp: '{new_timestamp}'", block, count=1)

    return html[:start] + block + html[end:]


def _patch_quiz_version(html: str) -> tuple[str, str, str]:
    """Find and patch-bump QUIZ_VERSION. Returns (new_html, old_version, new_version)."""
    m = re.search(r"const QUIZ_VERSION\s*=\s*'([^']+)';", html)
    if not m:
        raise ValueError("Cannot find 'const QUIZ_VERSION' in quiz HTML")
    old_ver = m.group(1)
    new_ver = increment_version(old_ver)
    new_html = html[:m.start()] + f"const QUIZ_VERSION = '{new_ver}';" + html[m.end():]
    return new_html, old_ver, new_ver


def _patch_last_update(html: str, new_timestamp: str) -> tuple[str, str, str]:
    """Find and update LAST_UPDATE. Returns (new_html, old_value, new_value)."""
    m = re.search(r"const LAST_UPDATE\s*=\s*'([^']+)';", html)
    if not m:
        return html, '', new_timestamp
    old_val = m.group(1)
    new_html = html[:m.start()] + f"const LAST_UPDATE = '{new_timestamp}';" + html[m.end():]
    return new_html, old_val, new_timestamp


def _add_changelog_entry(html: str, set_code: str, new_version: str, csv_path: Path,
                         card_count: int, today: str) -> tuple[str, str]:
    """
    Prepend a one-line entry after 'CHANGELOG:'.
      vX.Y.Z (YYYY-MM-DD UTC): DATA: Refresh <SET> to <CSV filename> (<N> cards).
    Returns (new_html, entry_text).
    """
    m = re.search(r'(CHANGELOG:\s*\n)', html)
    if not m:
        raise ValueError("Cannot find 'CHANGELOG:' block in quiz HTML")

    entry = (f"  v{new_version} ({today} UTC): DATA: Refresh {set_code} to "
             f"{csv_path.name} ({card_count} cards).")
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
    set_code: str = 'SOS',
) -> dict:
    """
    Regenerate <SET>_CARDS and update <SET> metadata in the quiz HTML.

    Returns a dict with card counts, added/removed, old/new dates, versions, the
    changelog entry, and 'changes_applied'.
    Raises ValueError if <SET>_CARDS or SET_CONFIG.<SET> or QUIZ_VERSION can't be located.
    """
    quiz_html_path = Path(quiz_html_path)
    new_csv_path = Path(new_csv_path)

    # --- Read HTML ---
    html = quiz_html_path.read_text(encoding='utf-8')

    # --- Load type resolution sources ---
    types_map = _load_types(set_code)
    scryfall = _load_scryfall_reference(set_code)
    existing_types = _extract_existing_types(html, set_code)

    # --- Parse existing <SET>_CARDS for old_count and added/removed diff ---
    old_names: set[str] = set(existing_types.keys())
    cards_old_count = len(old_names)

    # --- Extract old metadata for result dict ---
    try:
        config_start, block_end = _find_config_block_span(html, set_code)
    except ValueError as e:
        raise ValueError(f"Cannot find SET_CONFIG.{set_code} block: {e}") from e
    set_block = html[config_start:block_end]

    date_m = re.search(r"dataDate:\s*'([^']*)'", set_block)
    ts_m = re.search(r"dataTimestamp:\s*'([^']*)'", set_block)
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
        type_ = _resolve_type(name, types_map, scryfall, existing_types)
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

    changelog_entry = (
        f"v{new_version} ({today} UTC): DATA: Refresh {set_code} to "
        f"{new_csv_path.name} ({cards_new_count} cards)."
    )

    result = {
        'set_code': set_code,
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

    # --- Build new <SET>_CARDS JS block ---
    new_block = _build_cards_block(new_cards, set_code)

    # --- Splice <SET>_CARDS into HTML ---
    span_start, span_end = _find_cards_span(html, set_code)
    html = html[:span_start] + new_block + html[span_end:]

    # --- Patch SET_CONFIG.<SET> ---
    html = _patch_set_config(html, set_code, new_data_date, new_data_timestamp)

    # --- Bump QUIZ_VERSION ---
    html, _old_ver, _new_ver = _patch_quiz_version(html)
    assert _old_ver == old_quiz_version, f"Version mismatch: {_old_ver!r} vs {old_quiz_version!r}"
    assert _new_ver == new_version

    # --- Update LAST_UPDATE ---
    html, _old_lu, _new_lu = _patch_last_update(html, new_data_date)

    # --- Add changelog entry ---
    html, _entry = _add_changelog_entry(html, set_code, new_version, new_csv_path,
                                        cards_new_count, today)
    assert _entry.strip() == changelog_entry.strip()

    # --- Write to disk ---
    quiz_html_path.write_text(html, encoding='utf-8', newline='')
    result['changes_applied'] = True

    # --- Validate splice integrity (Python-side; node --check rejects .html in Node 24+) ---
    written = quiz_html_path.read_text(encoding='utf-8')
    cards_match = re.search(rf'const {set_code}_CARDS\s*=\s*\[', written)
    if not cards_match:
        raise ValueError(f"Validation failed: const {set_code}_CARDS not found after write.")
    start = cards_match.end()
    depth = 1
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
            f"Validation failed: {set_code}_CARDS array brackets unbalanced after splice."
        )
    cards_block = written[start:i - 1]
    actual_card_count = len(re.findall(r'\{name:', cards_block))
    if actual_card_count != len(new_cards):
        raise ValueError(
            f"Validation failed: expected {len(new_cards)} cards in {set_code}_CARDS, "
            f"found {actual_card_count}."
        )
    for needed in ('const QUIZ_VERSION', 'const SET_CONFIG', f'{set_code}:'):
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
            "Usage: python -m sos_refresh.quiz_updater <quiz_html> <csv_path> "
            "<data_date> [--dry-run] [--set CODE]"
        )
        sys.exit(1)

    set_code = 'SOS'
    if '--set' in args:
        set_code = args[args.index('--set') + 1]

    result = update_quiz(
        quiz_html_path=Path(args[0]),
        new_csv_path=Path(args[1]),
        new_data_date=args[2],
        dry_run='--dry-run' in args,
        set_code=set_code,
    )
    print(_json.dumps(result, indent=2))
