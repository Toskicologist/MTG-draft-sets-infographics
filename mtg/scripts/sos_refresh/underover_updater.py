#!/usr/bin/env python3
"""
underover_updater.py — Update sos-beta.html inline SET_CONFIG with new 17 Lands CSV.

Single responsibility: edit the inline SET_CONFIG inside sos-beta.html to point at a new 17Lands CSV,
update the lands_date, and bump version + timestamp.

Three changes inside the inline SET_CONFIG:
  1. data_paths.lands_csv -> "../../shared-data/17lands exports/<new_csv_filename>"
  2. header.lands_date -> new_lands_date
  3. version -> patch-bumped semver; timestamp -> current UTC ISO 8601

Public API:
  update_sos_beta(html_path, new_csv_filename, new_lands_date, dry_run=False) -> dict
"""

import re
from datetime import datetime, timezone
from pathlib import Path


def parse_version(version_str):
    """
    Parse semantic version string.
    Returns (major, minor, patch, beta_num, is_beta) or raises ValueError.

    Formats:
      - "X.Y.Z" (main release)
      - "X.Y.Z-beta.N" (beta release)
    """
    if '-beta.' in version_str:
        # Format: X.Y.Z-beta.N
        base, beta_part = version_str.split('-beta.')
        try:
            major, minor, patch = map(int, base.split('.'))
            beta_num = int(beta_part)
            return (major, minor, patch, beta_num, True)
        except ValueError as e:
            raise ValueError(f"Invalid version format: {version_str}") from e
    else:
        # Format: X.Y.Z
        parts = version_str.split('.')
        if len(parts) != 3:
            raise ValueError(f"Invalid version format: {version_str}")
        try:
            return (int(parts[0]), int(parts[1]), int(parts[2]), 0, False)
        except ValueError as e:
            raise ValueError(f"Invalid version format: {version_str}") from e


def increment_version(version_str):
    """
    Increment version: beta.N -> beta.N+1, or X.Y.Z -> X.Y.(Z+1).

    Args:
        version_str: Semantic version string (e.g., "1.2.3" or "1.2.3-beta.5")

    Returns:
        Incremented version string.
    """
    major, minor, patch, beta_num, is_beta = parse_version(version_str)

    if is_beta:
        # Increment beta number
        new_version = f"{major}.{minor}.{patch}-beta.{beta_num + 1}"
    else:
        # Increment patch version
        new_version = f"{major}.{minor}.{patch + 1}"

    return new_version


def update_sos_beta(
    html_path: Path,
    new_csv_filename: str,
    new_lands_date: str,
    dry_run: bool = False,
) -> dict:
    """
    Edit sos-beta.html inline SET_CONFIG to point to new 17 Lands CSV.

    Three changes:
      1. data_paths.lands_csv -> "../../shared-data/17lands exports/<new_csv_filename>"
      2. header.lands_date -> new_lands_date
      3. version -> patch-bumped semver; timestamp -> current UTC ISO 8601

    Args:
        html_path: Path to sos-beta.html
        new_csv_filename: Bare filename (e.g., "SOS card-ratings-2026-05-02 T1553.csv")
        new_lands_date: Human-readable date (e.g., "May 2, 2026")
        dry_run: If True, don't write; return what would change.

    Returns:
        {
            'old_csv': str,         # bare filename only
            'new_csv': str,
            'old_lands_date': str,
            'new_lands_date': str,
            'old_version': str,
            'new_version': str,
            'old_timestamp': str,
            'new_timestamp': str,
            'changes_applied': bool,
        }

    Raises:
        ValueError: If SET_CONFIG not found or fields missing.
    """
    html_path = Path(html_path)

    # Read the HTML file
    try:
        text = html_path.read_text(encoding='utf-8')
    except FileNotFoundError as e:
        raise ValueError(f"File not found: {html_path}") from e

    # Find SET_CONFIG by regex anchor
    set_config_match = re.search(r'const SET_CONFIG\s*=\s*\{', text)
    if not set_config_match:
        raise ValueError(
            f"Could not find 'const SET_CONFIG = {{' anchor in {html_path}"
        )

    # Extract old CSV filename (bare, no path)
    lands_csv_match = re.search(
        r'"lands_csv"\s*:\s*"([^"]*)"',
        text,
    )
    if not lands_csv_match:
        raise ValueError("Could not find lands_csv field in SET_CONFIG")
    old_csv_path = lands_csv_match.group(1)
    # Extract bare filename from path (after last /)
    old_csv = old_csv_path.split('/')[-1]

    # Extract old lands_date
    lands_date_match = re.search(
        r'"lands_date"\s*:\s*"([^"]*)"',
        text,
    )
    if not lands_date_match:
        raise ValueError("Could not find lands_date field in SET_CONFIG")
    old_lands_date = lands_date_match.group(1)

    # Extract old version
    version_match = re.search(
        r'"version"\s*:\s*"([^"]*)"',
        text,
    )
    if not version_match:
        raise ValueError("Could not find version field in SET_CONFIG")
    old_version = version_match.group(1)

    # Extract old timestamp
    timestamp_match = re.search(
        r'"timestamp"\s*:\s*"([^"]*)"',
        text,
    )
    if not timestamp_match:
        raise ValueError("Could not find timestamp field in SET_CONFIG")
    old_timestamp = timestamp_match.group(1)

    # Compute new values
    new_csv_path = f"../../shared-data/17lands exports/{new_csv_filename}"
    new_version = increment_version(old_version)
    new_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    # Build result dict (even for dry_run)
    result = {
        'old_csv': old_csv,
        'new_csv': new_csv_filename,
        'old_lands_date': old_lands_date,
        'new_lands_date': new_lands_date,
        'old_version': old_version,
        'new_version': new_version,
        'old_timestamp': old_timestamp,
        'new_timestamp': new_timestamp,
        'changes_applied': False,
    }

    if dry_run:
        return result

    # Apply all substitutions in order
    new_text = text

    # 1. Replace lands_csv path
    new_text = re.sub(
        r'"lands_csv"\s*:\s*"[^"]*"',
        f'"lands_csv": "{new_csv_path}"',
        new_text,
        count=1,
    )

    # 2. Replace lands_date
    new_text = re.sub(
        r'"lands_date"\s*:\s*"[^"]*"',
        f'"lands_date": "{new_lands_date}"',
        new_text,
        count=1,
    )

    # 3. Replace version
    new_text = re.sub(
        r'"version"\s*:\s*"[^"]*"',
        f'"version": "{new_version}"',
        new_text,
        count=1,
    )

    # 4. Replace timestamp
    new_text = re.sub(
        r'"timestamp"\s*:\s*"[^"]*"',
        f'"timestamp": "{new_timestamp}"',
        new_text,
        count=1,
    )

    # Write back to file
    html_path.write_text(new_text, encoding='utf-8', newline='')
    result['changes_applied'] = True

    return result


if __name__ == '__main__':
    import json
    from sys import argv

    if len(argv) < 4:
        print("Usage: python underover_updater.py <html_path> <csv_filename> <lands_date> [--dry-run]")
        print("Example: python underover_updater.py sos-beta.html 'SOS card-ratings-2026-05-02 T1553.csv' 'May 2, 2026'")
        exit(1)

    html_path = Path(argv[1])
    csv_filename = argv[2]
    lands_date = argv[3]
    dry_run = '--dry-run' in argv

    try:
        result = update_sos_beta(html_path, csv_filename, lands_date, dry_run=dry_run)
        print(json.dumps(result, indent=2))
    except ValueError as e:
        print(f"Error: {e}", file=__import__('sys').stderr)
        exit(1)
