#!/usr/bin/env python3
"""SOS 17Lands data refresh orchestrator.

Runs in two phases:
  1. Default: generate a diff report comparing the currently-active CSV
     against a new one. No writes. Exit 1 if review-needed flags fire.
  2. With --apply: run the consumer updaters. The under/over-rated page and the
     quiz are refreshed INDEPENDENTLY in both their beta and index (production)
     files — each file keeps its own version/changelog — plus
     ARCHETYPE_ANALYSIS.html. Gated by diff flags unless --force is given.

--promote (copy beta over index) is a MANUAL step for shipping code changes;
the daily Action must NOT pass it (that would silently push untested beta code
to production). Data freshness no longer depends on promotion.

Usage:
    python refresh_sos_17lands.py
    python refresh_sos_17lands.py --csv "SOS card-ratings-2026-05-02 T1553.csv"
    python refresh_sos_17lands.py --apply
    python refresh_sos_17lands.py --apply --force

The script never commits to git or pushes anything. Review with `git diff`
after --apply, then sync to GitHub Pages and push manually.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Diff-report summary contains unicode arrows; cp1252 can't encode them.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from sos_refresh import (
    archetype_updater,
    config,
    csv_loader,
    diff_report,
    fetch_17lands,
    quiz_updater,
    underover_updater,
)


def _resolve_new_csv(csv_arg: str | None) -> Path:
    """Turn the --csv argument into an absolute Path within LANDS_EXPORTS_DIR.
    If csv_arg is None, return the newest SOS CSV by mtime.
    """
    if csv_arg is None:
        return csv_loader.find_newest_sos_csv(config.LANDS_EXPORTS_DIR)

    candidate = Path(csv_arg)
    if candidate.is_absolute() and candidate.exists():
        return candidate

    # Treat as bare filename inside the exports folder
    p = config.LANDS_EXPORTS_DIR / csv_arg
    if not p.exists():
        raise FileNotFoundError(
            f"CSV not found: {p}\n"
            f"Provide a filename that exists in {config.LANDS_EXPORTS_DIR}, "
            f"or an absolute path."
        )
    return p


def _extract_csv_date(csv_path: Path) -> tuple[str, str, str]:
    """Pull the ISO date out of a CSV filename and produce the three
    formats consumers expect.

    Returns (iso_date, human_date, quiz_date_str), e.g.
        ("2026-05-02", "May 2, 2026", "2026-05-02 UTC")
    """
    m = re.search(r'card-ratings-(\d{4})-(\d{2})-(\d{2})', csv_path.name)
    if not m:
        raise ValueError(
            f"Could not extract YYYY-MM-DD from CSV filename: {csv_path.name}"
        )
    y, mo, d = m.group(1), m.group(2), m.group(3)
    dt = datetime(int(y), int(mo), int(d))
    iso_date = f"{y}-{mo}-{d}"
    # Avoid %-d (non-portable on Windows). Build human form manually.
    month_name = dt.strftime("%B")
    human_date = f"{month_name} {int(d)}, {y}"
    quiz_date_str = f"{iso_date} UTC"
    return iso_date, human_date, quiz_date_str


def _print_summary_header(active_csv: Path, new_csv: Path) -> None:
    print(f"Active CSV:  {active_csv.name}")
    print(f"Newest CSV:  {new_csv.name}")
    print()


def _run_diff(active_csv: Path, new_csv: Path, iso_date: str) -> dict:
    """Generate the diff report. Return diff_report.generate_diff_report()'s dict."""
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = config.REPORTS_DIR / f"{iso_date}-diff.md"

    print("Generating diff report...")
    print(f"  -> {report_path}")
    print()

    result = diff_report.generate_diff_report(
        old_csv=active_csv,
        new_csv=new_csv,
        archetype_html=config.ARCHETYPE_HTML,
        output_path=report_path,
    )
    return result


def _promote_beta_to_main() -> None:
    """Copy beta versions over their 'main' (index) counterparts.

    MANUAL code-shipping step (--promote). The daily data refresh updates beta
    and index independently, so this is only needed to release beta CODE changes
    to production - never for data freshness.
    """
    import shutil

    promotions = [
        (config.SOS_BETA_HTML, config.SOS_INDEX_HTML),
    ]

    # In CI mode, also promote the quiz directly. In LOCAL mode, the quiz beta
    # lives in MTG-GitHub-Pages directly, so the same path works.
    quiz_main = getattr(config, 'QUIZ_INDEX_HTML', None)
    if quiz_main is not None:
        promotions.append((config.QUIZ_BETA_HTML, quiz_main))

    print()
    print("Promoting beta -> main...")
    for src, dst in promotions:
        if not src.exists():
            print(f"  [SKIP] {src.name} not found")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"  [PROMOTE] {src.name} -> {dst.name}")


def _existing_targets(beta: Path, index: Path | None, label: str) -> list[Path]:
    """Beta always; index (production) when configured and present. Both are
    refreshed independently so beta code changes never reach production via
    the data refresh."""
    targets = [beta]
    if index is not None and index.exists():
        targets.append(index)
    elif index is not None:
        print(f"  [WARN] {label}: {index} not found - refreshing beta only.")
    return targets


def _run_updaters(new_csv: Path, human_date: str, quiz_date_str: str) -> int:
    """Run the consumer updaters in sequence (each beta AND index file
    independently, then the archetype page). Returns exit code; continues past
    per-file failures so one bad file never blocks the others."""
    print()
    print("Applying updates...")
    print()

    sos_targets = _existing_targets(
        config.SOS_BETA_HTML, getattr(config, 'SOS_INDEX_HTML', None), 'under/over-rated')
    quiz_targets = _existing_targets(
        config.QUIZ_BETA_HTML, getattr(config, 'QUIZ_INDEX_HTML', None), 'quiz')
    total = len(sos_targets) + len(quiz_targets) + 1
    step = 0
    failures: list[str] = []

    # 1. SOS Over/Under-Rated (beta + index)
    for target in sos_targets:
        step += 1
        try:
            r1 = underover_updater.update_sos_beta(
                html_path=target,
                new_csv_filename=new_csv.name,
                new_lands_date=human_date,
                dry_run=False,
            )
            print(
                f"[{step}/{total}] {target.name:22s} "
                f"v{r1['old_version']} -> v{r1['new_version']}   "
                f"(date: {r1['old_lands_date']} -> {r1['new_lands_date']})"
            )
        except Exception as exc:
            print(f"[{step}/{total}] {target.name:22s} FAILED: {exc}", file=sys.stderr)
            failures.append(target.name)

    # 2. Quiz (beta + index)
    for target in quiz_targets:
        step += 1
        try:
            r2 = quiz_updater.update_quiz(
                quiz_html_path=target,
                new_csv_path=new_csv,
                new_data_date=quiz_date_str,
                dry_run=False,
            )
            print(
                f"[{step}/{total}] {target.name:22s} "
                f"v{r2['old_quiz_version']} -> v{r2['new_quiz_version']}   "
                f"({r2['cards_old_count']} -> {r2['cards_new_count']} cards)"
            )
            if r2.get('cards_added'):
                print(f"      added: {', '.join(r2['cards_added'])}")
            if r2.get('cards_removed'):
                print(f"      removed: {', '.join(r2['cards_removed'])}")
        except Exception as exc:
            print(f"[{step}/{total}] {target.name:22s} FAILED: {exc}", file=sys.stderr)
            failures.append(target.name)

    # 3. Archetype HTML (no beta/index split)
    step += 1
    try:
        r3 = archetype_updater.update_archetype_html(
            archetype_html_path=config.ARCHETYPE_HTML,
            archetype_py_path=config.ARCHETYPE_PY,
            new_csv_path=new_csv,
            new_lands_date=human_date,
            dry_run=False,
        )
        print(
            f"[{step}/{total}] {'ARCHETYPE_ANALYSIS':22s} "
            f"v{r3['old_version']} -> v{r3['new_version']}   "
            f"regions: {', '.join(r3['regions_updated'])}"
        )
    except Exception as exc:
        print(f"[{step}/{total}] {'ARCHETYPE_ANALYSIS':22s} FAILED: {exc}", file=sys.stderr)
        failures.append('ARCHETYPE_ANALYSIS.html')

    print()
    if failures:
        print(
            f"{len(failures)} update(s) FAILED: {', '.join(failures)}. "
            f"Successful files were still written - inspect with `git diff`.",
            file=sys.stderr,
        )
        return 2
    print("All updates applied. Review with: git diff")
    print(
        "Then: sync to MTG-GitHub-Pages (if any ClaudeProjects files changed), "
        "commit there, push."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Refresh SOS 17Lands data across all consumers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Routine refresh:\n"
            "  1. Save new CSV to mtg/shared-data/17lands exports/\n"
            "  2. Run this script (no args) to get a diff report.\n"
            "  3. Review the report. If satisfied, re-run with --apply.\n"
            "  4. git diff to verify, then sync and push manually.\n"
        ),
    )
    parser.add_argument(
        "--csv",
        metavar="FILENAME",
        default=None,
        help="CSV filename (in mtg/shared-data/17lands exports/) or absolute "
             "path. Default: newest SOS CSV by mtime.",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Download a fresh CSV from the 17Lands JSON API before running "
             "the diff/apply. Ignores --csv when set.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates after generating the diff report. "
             "Gated by review flags unless --force.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="With --apply: skip gating on diff-report flags.",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Copy beta pages over their 'main' (index) counterparts "
             "(sos-beta.html -> sos-index.html, quiz-beta.html -> "
             "17lands-quiz/index.html). Ships beta CODE to production - manual "
             "use only; the daily Action refreshes data in both files and must "
             "not pass this. Works standalone or after --apply.",
    )
    args = parser.parse_args(argv)

    # --- Standalone promote (manual code-shipping, no data refresh) ---
    if args.promote and not args.apply:
        try:
            _promote_beta_to_main()
        except Exception as exc:
            print(f"Promote failed: {exc}", file=sys.stderr)
            return 2
        return 0

    # --- Optional: fetch a fresh CSV from the 17Lands API first ---
    if args.fetch:
        try:
            fetched_path = fetch_17lands.fetch_and_save()
        except Exception as exc:
            print(f"Fetch failed: {exc}", file=sys.stderr)
            return 2
        # Override --csv: always use the freshly downloaded file.
        args.csv = str(fetched_path)
        print()

    # --- Resolve CSVs ---
    try:
        new_csv = _resolve_new_csv(args.csv)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        active_csv = csv_loader.find_active_sos_csv(
            sos_beta_html=config.SOS_BETA_HTML,
            exports_dir=config.LANDS_EXPORTS_DIR,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error reading active CSV from sos-beta.html: {exc}", file=sys.stderr)
        return 2

    _print_summary_header(active_csv, new_csv)

    if active_csv.resolve() == new_csv.resolve():
        print("Already on latest CSV - nothing to do.")
        return 0

    # --- Date formats ---
    try:
        iso_date, human_date, quiz_date_str = _extract_csv_date(new_csv)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    # --- Diff report ---
    try:
        diff_result = _run_diff(active_csv, new_csv, iso_date)
    except Exception as exc:
        print(f"Diff report failed: {exc}", file=sys.stderr)
        return 2

    print(diff_result["summary"])
    print()
    print(f"Report: {diff_result['report_path']}")

    flags_fired = diff_result["flags_fired"]

    if not args.apply:
        if flags_fired:
            print()
            print("To apply: re-run with --apply --force (skips gate) or "
                  "--apply (only if no flags fire after review).")
            return 1
        else:
            print()
            print("No review flags fired. To apply, re-run with --apply.")
            return 0

    # --- Apply mode ---
    if flags_fired and not args.force:
        print()
        print("REVIEW FLAGS FIRED - refusing to apply without --force.")
        print(f"Review the report and re-run with --force if you accept the changes.")
        return 1

    if flags_fired:
        print(f"  ({sum(1 for v in diff_result['flags'].values() if v)} flags - "
              f"applying anyway because --force)")

    rc = _run_updaters(new_csv, human_date, quiz_date_str)
    if rc != 0:
        return rc

    if args.promote:
        try:
            _promote_beta_to_main()
        except Exception as exc:
            print(f"Promote step failed: {exc}", file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
