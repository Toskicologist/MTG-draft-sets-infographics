#!/usr/bin/env python3
"""
archetype_updater.py — Re-run analyze_archetypes.py then regenerate AUTO_REGION table blocks
in ARCHETYPE_ANALYSIS.html.

Single responsibility: given a new 17 Lands CSV, run the analyzer subprocess to produce fresh
card_discrepancies.csv and archetype_discrepancies.csv, then splice new table rows into the
four AUTO_REGION-marked HTML blocks. Prose paragraphs outside markers are preserved verbatim.
Also updates the page-meta version/date/timestamp markers.

Public API:
    update_archetype_html(archetype_html_path, archetype_py_path, new_csv_path,
                          new_lands_date=None, dry_run=False) -> dict
"""

import csv
from datetime import datetime, timezone
import html
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path


# ---------------------------------------------------------------------------
# Page-meta helpers (version / lands_date / timestamp)
# ---------------------------------------------------------------------------

def _read_meta_field(html_text: str, field: str) -> str:
    m = re.search(rf'<!-- ARCHETYPE_{field} -->(.*?)<!-- /ARCHETYPE_{field} -->', html_text)
    if not m:
        raise ValueError(f'ARCHETYPE_{field} marker not found in HTML')
    return m.group(1)


def _write_meta_field(html_text: str, field: str, value: str) -> str:
    pattern = rf'(<!-- ARCHETYPE_{field} -->)(.*?)(<!-- /ARCHETYPE_{field} -->)'
    new_html, n = re.subn(pattern, rf'\g<1>{value}\g<3>', html_text)
    if n == 0:
        raise ValueError(f'ARCHETYPE_{field} marker not found in HTML')
    return new_html


def _increment_version(version_str: str) -> str:
    parts = version_str.strip().split('.')
    if len(parts) != 3:
        raise ValueError(f'Expected X.Y.Z version, got: {version_str!r}')
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    return f'{major}.{minor}.{patch + 1}'


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def _read_csv(path: Path) -> list[dict]:
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Scryfall link helper
# ---------------------------------------------------------------------------

def _scryfall_link(name: str) -> str:
    """Return an <a> tag with the Scryfall hover-link pattern used in the HTML."""
    encoded = urllib.parse.quote(name)
    escaped = html.escape(name, quote=True)
    return (
        f'<a href="https://scryfall.com/search?q=!%22{encoded}%22" '
        f'class="scryfall-link" data-card="{escaped}">{html.escape(name)}</a>'
    )


# ---------------------------------------------------------------------------
# Discrepancy formatting
# ---------------------------------------------------------------------------

def _fmt_disc(val: float) -> str:
    """Format discrepancy value as ±X.XX using a proper minus sign (−)."""
    if val < 0:
        return f'−{abs(val):.2f}'
    return f'+{val:.2f}'


# ---------------------------------------------------------------------------
# Region renderers
# ---------------------------------------------------------------------------

def _render_top20_underrated(card_rows: list[dict]) -> str:
    """
    Sort card_discrepancies rows by discrepancy ASC (most negative first = most underrated).
    Take top 20. Render <tbody> rows matching the existing table structure.
    Returns only the <tbody>...</tbody> block (table/thead chrome preserved by splice logic).
    """
    rows = sorted(card_rows, key=lambda r: float(r['discrepancy']))[:20]
    lines = ['            <tbody>']
    for r in rows:
        disc = float(r['discrepancy'])
        gih = float(r['gih_wr'])
        lines.append('                <tr>')
        lines.append(f'                    <td>{_scryfall_link(r["card"])}</td>')
        lines.append(f'                    <td>{html.escape(r["rarity"])}</td>')
        lines.append(f'                    <td>{html.escape(r["colors"])}</td>')
        lines.append(f'                    <td>{_fmt_disc(disc)}</td>')
        lines.append(f'                    <td>{gih:.1f}%</td>')
        lines.append('                </tr>')
    lines.append('            </tbody>')
    return '\n'.join(lines)


def _render_top20_overrated(card_rows: list[dict]) -> str:
    """
    Sort card_discrepancies rows by discrepancy DESC (most positive first = most overrated).
    Take top 20.
    """
    rows = sorted(card_rows, key=lambda r: float(r['discrepancy']), reverse=True)[:20]
    lines = ['            <tbody>']
    for r in rows:
        disc = float(r['discrepancy'])
        gih = float(r['gih_wr'])
        lines.append('                <tr>')
        lines.append(f'                    <td>{_scryfall_link(r["card"])}</td>')
        lines.append(f'                    <td>{html.escape(r["rarity"])}</td>')
        lines.append(f'                    <td>{html.escape(r["colors"])}</td>')
        lines.append(f'                    <td>{_fmt_disc(disc)}</td>')
        lines.append(f'                    <td>{gih:.1f}%</td>')
        lines.append('                </tr>')
    lines.append('            </tbody>')
    return '\n'.join(lines)


# Color display names and interpretation thresholds
_COLOR_NAMES = {'W': 'White', 'U': 'Blue', 'B': 'Black', 'R': 'Red', 'G': 'Green'}


def _color_interpretation(mean_disc: float) -> str:
    if mean_disc <= -0.08:
        return 'Most underrated (reviewers miss cheap spells)' if False else 'Underrated (reviewers pessimistic)'
    if mean_disc < -0.02:
        return 'Slightly underrated (reviewers pessimistic)'
    if mean_disc <= 0.02:
        return 'Neutral (reviewers calibrated)'
    if mean_disc < 0.06:
        return 'Slightly overrated (reviewers optimistic)'
    return 'Overrated (reviewers optimistic)'


def _render_color_summary(card_rows: list[dict]) -> str:
    """
    Compute mono-color stats from card_discrepancies.csv (colors column).
    Matches analyze_archetypes.py lines 197–211: filter cards where colors == single letter.
    Render rows matching existing color_summary table.
    """
    # Find which color has the most extreme underrated mean (for bold markup)
    color_stats = {}
    for col in ['W', 'U', 'B', 'R', 'G']:
        col_cards = [r for r in card_rows if r['colors'] == col]
        if not col_cards:
            color_stats[col] = None
            continue
        discs = [float(r['discrepancy']) for r in col_cards]
        wrs = [float(r['gih_wr']) for r in col_cards]
        mean_disc = sum(discs) / len(discs)
        mean_wr = sum(wrs) / len(wrs)
        color_stats[col] = {'n': len(col_cards), 'mean_disc': mean_disc, 'mean_wr': mean_wr}

    # Find most underrated color (most negative mean)
    valid = {c: s for c, s in color_stats.items() if s is not None}
    most_underrated = min(valid.keys(), key=lambda c: valid[c]['mean_disc']) if valid else None

    lines = ['            <tbody>']
    for col in ['W', 'U', 'B', 'R', 'G']:
        stats = color_stats.get(col)
        if stats is None:
            continue
        n = stats['n']
        mean_disc = stats['mean_disc']
        mean_wr = stats['mean_wr']

        label = f'<strong>{col}</strong> ({_COLOR_NAMES[col]})'
        disc_str = _fmt_disc(mean_disc)
        interp = _color_interpretation(mean_disc)

        # Bold the most underrated row's discrepancy and interpretation
        if col == most_underrated:
            disc_cell = f'<strong>{disc_str}</strong>'
            interp_cell = f'<strong>{interp}</strong>'
        else:
            disc_cell = disc_str
            interp_cell = interp

        lines.append('                <tr>')
        lines.append(f'                    <td>{label}</td>')
        lines.append(f'                    <td style="text-align: right;">{n}</td>')
        lines.append(f'                    <td style="text-align: right;">{disc_cell}</td>')
        lines.append(f'                    <td style="text-align: right;">{mean_wr:.1f}%</td>')
        lines.append(f'                    <td>{interp_cell}</td>')
        lines.append('                </tr>')
    lines.append('            </tbody>')
    return '\n'.join(lines)


def _archetype_interpretation(pair: str, mean_disc: float, n: int) -> str:
    if n == 0:
        return 'No data'
    if mean_disc <= -0.08:
        return 'Underrated (sleeper archetype)'
    if mean_disc < -0.02:
        return 'Slightly underrated (sleeper archetype)'
    if mean_disc <= 0.02:
        return 'Neutral (reviewers calibrated)'
    if mean_disc < 0.08:
        return 'Neutral-slightly overrated'
    if mean_disc < 0.15:
        return 'Overrated (reviewers expected more)'
    return 'Heavily overrated; theme failed'


def _render_archetype_summary(arch_rows: list[dict]) -> str:
    """
    Render archetype_discrepancies.csv rows.
    Rows with n=0 render with '—' for stats (matching existing behavior where those rows still appear).
    Highlight the most overrated archetype with bold.
    """
    # Find most overrated (highest mean_discrepancy among rows with n>0)
    valid_rows = [r for r in arch_rows if r['n'] != '0' and r['mean_discrepancy'] != '']
    most_overrated_pair = None
    if valid_rows:
        most_overrated_pair = max(valid_rows, key=lambda r: float(r['mean_discrepancy']))['pair']

    lines = ['            <tbody>']
    for r in arch_rows:
        pair = r['pair']
        archetype = r['archetype']
        theme = r['theme']
        n = int(r['n'])
        name_label = f'<strong>{pair} {archetype}</strong>'

        if n == 0 or r['mean_discrepancy'] == '':
            disc_cell = '—'
            wr_cell = '—'
            interp_cell = 'No data'
        else:
            mean_disc = float(r['mean_discrepancy'])
            mean_wr = float(r['mean_gih_wr'])
            disc_str = _fmt_disc(mean_disc)
            interp = _archetype_interpretation(pair, mean_disc, n)

            if pair == most_overrated_pair:
                disc_cell = f'<strong>{disc_str}</strong>'
                wr_cell = f'<strong>{mean_wr:.1f}%</strong>'
                interp_cell = f'<strong>{interp}</strong>'
            else:
                disc_cell = disc_str
                wr_cell = f'{mean_wr:.1f}%'
                interp_cell = interp

        lines.append('                <tr>')
        lines.append(f'                    <td>{name_label}</td>')
        lines.append(f'                    <td>{html.escape(theme)}</td>')
        lines.append(f'                    <td style="text-align: right;">{n}</td>')
        lines.append(f'                    <td style="text-align: right;">{disc_cell}</td>')
        lines.append(f'                    <td style="text-align: right;">{wr_cell}</td>')
        lines.append(f'                    <td>{interp_cell}</td>')
        lines.append('                </tr>')
    lines.append('            </tbody>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML splice helpers
# ---------------------------------------------------------------------------

def _extract_table_chrome(html_text: str, region_name: str) -> tuple[str, str]:
    """
    Extract the table+thead prefix and tbody-close/table-close suffix from an existing region.
    Returns (prefix, suffix) so we can rebuild: prefix + new_tbody + suffix.
    """
    pattern = re.compile(
        rf'<!-- AUTO_REGION:{re.escape(region_name)} START -->(.*?)<!-- AUTO_REGION:{re.escape(region_name)} END -->',
        re.DOTALL,
    )
    m = pattern.search(html_text)
    if not m:
        raise ValueError(f'AUTO_REGION:{region_name} markers not found in HTML')
    inner = m.group(1)

    # Split at <tbody> to separate thead chrome from body
    tbody_start = inner.find('<tbody>')
    if tbody_start == -1:
        raise ValueError(f'No <tbody> found in region {region_name}')
    tbody_end = inner.find('</tbody>', tbody_start)
    if tbody_end == -1:
        raise ValueError(f'No </tbody> found in region {region_name}')

    prefix = inner[:tbody_start]                            # up to (not including) <tbody>
    suffix = inner[tbody_end + len('</tbody>'):]            # after </tbody>
    return prefix, suffix


def _splice_region(html_text: str, region_name: str, new_tbody: str) -> str:
    """Replace the tbody contents of a named AUTO_REGION block."""
    prefix, suffix = _extract_table_chrome(html_text, region_name)
    new_inner = prefix + new_tbody + suffix
    pattern = re.compile(
        rf'(<!-- AUTO_REGION:{re.escape(region_name)} START -->)(.*?)(<!-- AUTO_REGION:{re.escape(region_name)} END -->)',
        re.DOTALL,
    )
    if not pattern.search(html_text):
        raise ValueError(f'AUTO_REGION:{region_name} markers not found')
    return pattern.sub(
        lambda m: m.group(1) + '\n' + new_inner + '\n' + m.group(3),
        html_text,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def update_archetype_html(
    archetype_html_path: Path,
    archetype_py_path: Path,
    new_csv_path: Path,
    new_lands_date: str | None = None,
    dry_run: bool = False,
) -> dict:
    """
    1. Run analyze_archetypes.py --csv <new_csv_path> as a subprocess.
    2. Read card_discrepancies.csv + archetype_discrepancies.csv written by the script.
    3. Regenerate HTML for each AUTO_REGION block from those CSVs.
    4. Update page-meta version (patch bump), lands_date, and timestamp.
    5. Write changes to archetype_html_path (unless dry_run).

    Returns a result dict (see module docstring for schema).
    Raises RuntimeError if subprocess fails, FileNotFoundError if CSVs missing,
    ValueError if any AUTO_REGION marker pair missing.
    """
    archetype_html_path = Path(archetype_html_path)
    archetype_py_path = Path(archetype_py_path)
    new_csv_path = Path(new_csv_path)

    # Resolve where the script writes its outputs (hardcoded in analyze_archetypes.py)
    out_dir = archetype_py_path.parent
    card_csv_path = out_dir / 'card_discrepancies.csv'
    arch_csv_path = out_dir / 'archetype_discrepancies.csv'

    # --- Step 1: Run analyzer ---
    result = subprocess.run(
        [sys.executable, str(archetype_py_path), '--csv', str(new_csv_path)],
        capture_output=True,
        text=True,
    )
    stdout_combined = result.stdout + (('\n--- STDERR ---\n' + result.stderr) if result.stderr.strip() else '')
    if result.returncode != 0:
        raise RuntimeError(
            f'analyze_archetypes.py exited with code {result.returncode}.\n'
            f'stdout: {result.stdout[:800]}\nstderr: {result.stderr[:400]}'
        )

    # --- Step 2: Read CSVs ---
    if not card_csv_path.exists():
        raise FileNotFoundError(f'card_discrepancies.csv not found at {card_csv_path}')
    if not arch_csv_path.exists():
        raise FileNotFoundError(f'archetype_discrepancies.csv not found at {arch_csv_path}')

    card_rows = _read_csv(card_csv_path)
    arch_rows = _read_csv(arch_csv_path)

    # --- Step 3: Generate new HTML chunks ---
    under_sorted = sorted(card_rows, key=lambda r: float(r['discrepancy']))
    over_sorted = sorted(card_rows, key=lambda r: float(r['discrepancy']), reverse=True)
    top_under_first = under_sorted[0]['card'] if under_sorted else ''
    top_over_first = over_sorted[0]['card'] if over_sorted else ''

    region_chunks = {
        'top20_underrated': _render_top20_underrated(card_rows),
        'top20_overrated': _render_top20_overrated(card_rows),
        'color_summary': _render_color_summary(card_rows),
        'archetype_summary': _render_archetype_summary(arch_rows),
    }

    # Capture old first card before any modification
    html_text = archetype_html_path.read_text(encoding='utf-8')

    old_under_pattern = re.compile(
        r'<!-- AUTO_REGION:top20_underrated START -->.*?<tbody>(.*?)</tbody>',
        re.DOTALL,
    )
    old_under_match = old_under_pattern.search(html_text)
    old_first_card_match = re.search(r'data-card="([^"]+)"', old_under_match.group(1)) if old_under_match else None
    old_first_card = old_first_card_match.group(1) if old_first_card_match else ''

    # --- Step 4: Splice table regions ---
    regions_updated = []
    new_html = html_text
    for region_name, new_tbody in region_chunks.items():
        new_html = _splice_region(new_html, region_name, new_tbody)
        regions_updated.append(region_name)

    # --- Step 5: Update page-meta markers ---
    old_version = _read_meta_field(new_html, 'VERSION')
    new_version = _increment_version(old_version)
    new_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    new_html = _write_meta_field(new_html, 'VERSION', new_version)
    new_html = _write_meta_field(new_html, 'TIMESTAMP', new_timestamp)
    if new_lands_date:
        new_html = _write_meta_field(new_html, 'LANDS_DATE', new_lands_date)

    changes_applied = False
    if not dry_run:
        archetype_html_path.write_text(new_html, encoding='utf-8')
        changes_applied = True

    return {
        'subprocess_exit_code': result.returncode,
        'subprocess_stdout_summary': stdout_combined[:500],
        'card_discrepancies_path': card_csv_path,
        'archetype_discrepancies_path': arch_csv_path,
        'regions_updated': regions_updated,
        'old_version': old_version,
        'new_version': new_version,
        'top20_under_old_first': old_first_card,
        'top20_under_new_first': top_under_first,
        'changes_applied': changes_applied,
    }
