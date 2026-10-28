#!/usr/bin/env python3
"""Refresh the 17Lands quiz data file (17lands-quiz/data/quiz-data.js).

The beta quiz pages (quiz-beta.html, pack-beta.html) read their cards from that
file instead of embedding them (see sos_refresh/quiz_data.py). This script is
the only thing that writes it. Each run:

  1. --discover: asks 17Lands which expansions it has data for and adds any new
     draft set (Premier Draft data started within the last
     config.QUIZ_DISCOVER_MAX_AGE_DAYS days, a real set on Scryfall, the 12-day
     17Lands embargo over, 150+ scored cards). The set goes first in the
     selector, with its Scryfall name and icon. Nothing else is needed for the
     pages to show it.
  2. Refreshes the config.QUIZ_REFRESH_NEWEST newest sets (by 17Lands start
     date) from a 17Lands CSV: one fetched earlier today when there is one (the
     per-set scripts in the same workflow fetch SOS/MSH/HOB/FRA first), else a
     fresh one with --fetch.

Without --apply nothing is written. The production page (index.html) still
embeds its data until the beta is promoted; the per-set refresh_*.py scripts
keep that up to date as before.

Usage:
    python refresh_quiz_data.py                          # dry run, newest CSVs on disk
    python refresh_quiz_data.py --discover --fetch       # dry run with live data
    python refresh_quiz_data.py --discover --fetch --apply   # what the Action runs
    python refresh_quiz_data.py --sets ECL,TMT --fetch --apply   # refresh older sets too
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from sos_refresh import config, csv_loader, fetch_17lands, quiz_data


def _csv_date(csv_path: Path) -> str:
    m = re.search(r"card-ratings-(\d{4}-\d{2}-\d{2})", csv_path.name)
    if not m:
        raise ValueError(f"no YYYY-MM-DD in CSV filename {csv_path.name}")
    return f"{m.group(1)} UTC"


def _todays_csv(code: str) -> Path | None:
    """A CSV for this set fetched today (fetch_17lands names files by the local
    date, which is UTC on the Action runner). File dates, not mtimes: a fresh
    checkout gives every committed CSV a new mtime."""
    today = datetime.now().strftime("%Y-%m-%d")
    hits = sorted(config.LANDS_EXPORTS_DIR.glob(f"{code} card-ratings-{today} T*.csv"))
    return hits[-1] if hits else None


def _csv_for(data: dict, code: str, fetch: bool) -> Path:
    path = _todays_csv(code)
    if path:
        return path
    if fetch:
        s = data["sets"][code]
        return fetch_17lands.fetch_and_save(start_date=s["released"],
                                            expansion=s["expansion"], fmt=s["format"])
    return csv_loader.find_newest_csv(config.LANDS_EXPORTS_DIR, f"{code} card-ratings-*.csv")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--discover", action="store_true", help="look for new 17Lands sets and add them")
    ap.add_argument("--fetch", action="store_true", help="download a CSV when none was fetched today")
    ap.add_argument("--apply", action="store_true", help="write the data file (default: dry run)")
    ap.add_argument("--force", action="store_true", help="skip the 90%% scored-card collapse guard")
    ap.add_argument("--sets", help="comma list to refresh instead of the newest "
                                   f"{config.QUIZ_REFRESH_NEWEST}")
    ap.add_argument("--data", type=Path, default=None, help=f"data file (default {config.QUIZ_DATA_JS})")
    args = ap.parse_args(argv)

    path = args.data or config.QUIZ_DATA_JS
    data = quiz_data.load(path)
    print(f"Data file: {path}  ({len(data['sets'])} sets, updated {data['updated']})")
    failures = 0
    changed = False

    # --- 1. New sets ---
    if args.discover:
        try:
            candidates, notes = quiz_data.discover_candidates(data)
        except Exception as exc:  # noqa: BLE001 - discovery must never block the refresh
            print(f"[DISCOVER FAILED] {exc}", file=sys.stderr)
            candidates, notes = [], []
            failures += 1
        for note in notes:
            print(f"  [discover] {note}")
        if not candidates:
            print("  [discover] no new sets")
        for cand in candidates:
            code = cand["code"]
            if not args.fetch:
                print(f"  [discover] {code} ({cand['name']}) is new - re-run with --fetch to add it")
                continue
            try:
                csv_path = _todays_csv(code) or fetch_17lands.fetch_and_save(
                    start_date=cand["start"], expansion=code, fmt="PremierDraft")
                r = quiz_data.add_set(data, cand, csv_path, _csv_date(csv_path))
            except ValueError as exc:
                print(f"  [discover] {code}: not ready yet ({exc})")
                continue
            except Exception as exc:  # noqa: BLE001
                print(f"[ADD FAILED] {code}: {exc}", file=sys.stderr)
                failures += 1
                continue
            changed = True
            print(f"[ADDED]   {code} ({cand['name']}): {r['new']} cards, {r['new_scored']} scored, "
                  f"icon {'from Scryfall' if r['icon'] else 'missing (generic one shown)'}, "
                  f"visible from {cand['visible_from']}")

    # --- 2. Refresh ---
    codes = [c.strip().upper() for c in args.sets.split(",")] if args.sets else quiz_data.sets_to_refresh(data)
    unknown = [c for c in codes if c not in data["sets"]]
    if unknown:
        print(f"Unknown set(s): {', '.join(unknown)}", file=sys.stderr)
        return 2
    print(f"Refreshing: {', '.join(codes)}")
    for code in codes:
        try:
            csv_path = _csv_for(data, code, args.fetch)
            r = quiz_data.refresh_set(data, code, csv_path, _csv_date(csv_path), force=args.force)
        except Exception as exc:  # noqa: BLE001 - one set must not block the others
            print(f"[FAILED]  {code}: {exc}", file=sys.stderr)
            failures += 1
            continue
        changed = changed or r["changed"]
        tag = "[OK]" if r["changed"] else "[SAME]"
        print(f"{tag:<10}{code}: {r['old']} -> {r['new']} cards "
              f"({r['old_scored']} -> {r['new_scored']} scored)  from {csv_path.name}")
        for label in ("added", "removed"):
            if r[label]:
                print(f"          {label}: {', '.join(r[label][:15])}" + (" ..." if len(r[label]) > 15 else ""))

    # --- 3. Write ---
    if not args.apply:
        print("\nDry run - nothing written. Re-run with --apply to write the data file.")
    elif changed:
        quiz_data.touch(data)
        quiz_data.save(data, path)
        print(f"\nWrote {path}")
    else:
        print("\nNothing changed - data file left as it was.")
    return 2 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
