"""
CSV loader for 17Lands SOS CSV exports.
Canonical parser used by diff_report.py and quiz_updater.py.
Matches the JS parser in generate-card-data.js exactly.
"""

import re
from pathlib import Path


def load_sos_csv(csv_path: Path, min_gih: int = 0) -> list[dict]:
    """Parse a 17Lands SOS CSV. Returns list of card dicts (sorted by name) with keys:
        name (str), color (str), rarity (str),
        gih_wr (float, percent-stripped, e.g. 54.2),
        gih_count (int), alsa (float)
    Cards skipped if: name empty, gih_wr invalid/<=0, OR (min_gih > 0 AND gih_count < min_gih).
    Note: min_gih=0 (default) means "include all cards with valid GIH WR" — matches the JS generator.
          min_gih=500 is the threshold analyze_archetypes.py uses.
    """
    csv_path = Path(csv_path)
    with open(csv_path, 'rb') as f:
        content = f.read().decode('utf-8-sig')

    lines = [line for line in content.split('\n') if line.strip()]
    if not lines:
        return []

    # Parse header
    headers = lines[0].split(',')
    headers = [h.strip().strip('"') for h in headers]

    # Find column indices
    try:
        name_idx = headers.index('Name')
        color_idx = headers.index('Color')
        rarity_idx = headers.index('Rarity')
        alsa_idx = headers.index('ALSA')
        gih_wr_idx = headers.index('GIH WR')
        gih_count_idx = headers.index('# GIH')
    except ValueError as e:
        raise ValueError(f"Missing required CSV column: {e}")

    cards = []

    # Parse data rows
    for line in lines[1:]:
        # Parse CSV line with quoted field support (state machine)
        fields = []
        field = ''
        in_quotes = False
        for ch in line:
            if ch == '"':
                in_quotes = not in_quotes
                continue
            if ch == ',' and not in_quotes:
                fields.append(field)
                field = ''
                continue
            field += ch
        fields.append(field)

        # Extract fields
        name = fields[name_idx].strip() if name_idx < len(fields) else ''
        color = fields[color_idx].strip() if color_idx < len(fields) else ''
        rarity = fields[rarity_idx].strip() if rarity_idx < len(fields) else ''
        alsa_str = fields[alsa_idx].strip() if alsa_idx < len(fields) else ''
        gih_wr_str = fields[gih_wr_idx].strip() if gih_wr_idx < len(fields) else ''
        gih_count_str = fields[gih_count_idx].strip() if gih_count_idx < len(fields) else ''

        # Skip if no name
        if not name:
            continue

        # Parse GIH WR (strip %, parseFloat)
        gih_wr_str_clean = gih_wr_str.replace('%', '')
        try:
            gih_wr = float(gih_wr_str_clean)
        except ValueError:
            gih_wr = float('nan')

        # Skip if GIH WR invalid or <= 0
        if not (-1 < gih_wr) or gih_wr <= 0:  # nan check and <= 0
            continue

        # Parse GIH count
        try:
            gih_count = int(gih_count_str)
        except ValueError:
            gih_count = 0

        # Skip if min_gih threshold not met
        if min_gih > 0 and gih_count < min_gih:
            continue

        # Parse ALSA (default to 0 if NaN, matching JS behavior)
        try:
            alsa = float(alsa_str)
        except ValueError:
            alsa = float('nan')

        if not (-1 < alsa):  # nan check
            alsa = 0.0

        cards.append({
            'name': name,
            'color': color,
            'rarity': rarity,
            'gih_wr': gih_wr,
            'gih_count': gih_count,
            'alsa': alsa,
        })

    # Sort alphabetically by name
    cards.sort(key=lambda c: c['name'])

    return cards


def find_newest_sos_csv(exports_dir: Path) -> Path:
    """Return the most recent file matching 'SOS card-ratings-*.csv' in exports_dir, by mtime.
    Raises FileNotFoundError if none exist."""
    exports_dir = Path(exports_dir)
    pattern = 'SOS card-ratings-*.csv'

    files = list(exports_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(
            f"No files matching '{pattern}' found in {exports_dir}"
        )

    # Sort by mtime descending, return most recent
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


def find_active_sos_csv(sos_beta_html: Path, exports_dir: Path) -> Path:
    """Read sos-beta.html, locate the inline SET_CONFIG, extract data_paths.lands_csv,
    and return the resolved absolute Path within exports_dir.
    The lands_csv value in the HTML is like '../../shared-data/17lands exports/SOS card-ratings-2026-04-27 1245 .csv'.
    Strip the directory prefix (everything before and including the last '/') and join with exports_dir.
    Raises ValueError if SET_CONFIG can't be located or lands_csv missing."""
    sos_beta_html = Path(sos_beta_html)

    with open(sos_beta_html, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find SET_CONFIG = { ... }
    # We search for "const SET_CONFIG = {" and then extract lands_csv from the next ~3000 chars
    match = re.search(r'const SET_CONFIG\s*=\s*\{', content)
    if not match:
        raise ValueError('SET_CONFIG not found in HTML')

    # Extract around SET_CONFIG to find lands_csv
    start = match.start()
    search_space = content[start:start + 5000]  # generous search space

    # Find "lands_csv": "..."
    lands_match = re.search(r'"lands_csv"\s*:\s*"([^"]+)"', search_space)
    if not lands_match:
        raise ValueError('lands_csv not found in SET_CONFIG')

    lands_csv_relative = lands_match.group(1)

    # Strip directory prefix (everything before and including last '/')
    filename = lands_csv_relative.split('/')[-1]

    return exports_dir / filename
