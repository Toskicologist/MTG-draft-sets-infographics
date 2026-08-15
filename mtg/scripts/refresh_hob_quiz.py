#!/usr/bin/env python3
"""HOB 17Lands quiz refresh orchestrator (quiz-only).

HOB (The Hobbit) has no under/over-rated or archetype-analysis consumers in this
pipeline, so — like refresh_msh_quiz.py and unlike refresh_sos_17lands.py — this
script touches only the 17Lands quiz. It:

  1. Optionally downloads a fresh HOB CSV from the 17Lands JSON API (--fetch).
  2. Regenerates the HOB_CARDS array + SET_CONFIG.HOB metadata (--apply), reusing
     the shared, set-agnostic quiz_updater. The refresh is applied INDEPENDENTLY to
     quiz-beta.html AND index.html (each file keeps its own QUIZ_VERSION/changelog),
     so production data stays fresh without shipping beta code changes.
  3. Optionally promotes quiz-beta.html -> index.html (--promote). This is a MANUAL
     step for shipping code changes; the daily Action must NOT pass it (that would
     silently push untested beta code to production).

Card types come from the local Scryfall snapshot (mtg/shared-data/data/hob/
hob-scryfall-full.json); if that file is absent (e.g. in CI), quiz_updater falls
back to the types already embedded in the quiz HTML, so ongoing GIH-WR refreshes
keep working. No guessed data: cards without a valid 17Lands GIH WR are skipped.

HOB is a young set (Arena release 2026-08-11), so its scored-card count starts
below the full 188-card list and grows as cards cross 17Lands' ~500-game
suppression threshold. MIN_EXPECTED_CARDS is set accordingly.

The P1P1 pack quiz (pack-beta.html) is refreshed only once it actually carries a
HOB_CARDS array — it needs its own booster spec before HOB can be drafted there,
so until that lands the pack page is skipped instead of failing the daily run.

Usage:
    python refresh_hob_quiz.py                 # dry-run report on newest HOB CSV
    python refresh_hob_quiz.py --fetch         # download fresh CSV, then dry-run
    python refresh_hob_quiz.py --fetch --apply --force   # what the Action runs
    python refresh_hob_quiz.py --promote       # manual: ship beta code to production

The script never commits or pushes. Review with `git diff` after --apply.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

# Diff/summary text may contain unicode; cp1252 can't encode it.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from sos_refresh import config, csv_loader, fetch_17lands, quiz_updater

SET_CODE = "HOB"
# Refuse to apply if the card count would collapse — guards against a bad/empty
# fetch. 179 of 188 cards cleared the GIH threshold on 2026-08-14. 17Lands'
# ALL_TIME counts only grow (a card past ~500 GIH stays past it), so this floor
# sits just under today's count. Do NOT set it to 150: quiz_updater's own
# 150-card guard raises during the dry-run first, which would make it dead code.
MIN_EXPECTED_CARDS = 165


def _resolve_new_csv(csv_arg: str | None) -> Path:
    """Turn --csv into an absolute Path, or return the newest HOB CSV by mtime."""
    if csv_arg is None:
        return csv_loader.find_newest_csv(
            config.LANDS_EXPORTS_DIR, config.HOB_CSV_GLOB
        )
    candidate = Path(csv_arg)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    p = config.LANDS_EXPORTS_DIR / csv_arg
    if not p.exists():
        raise FileNotFoundError(
            f"CSV not found: {p}\nProvide a filename in {config.LANDS_EXPORTS_DIR} "
            f"or an absolute path."
        )
    return p


def _extract_csv_date(csv_path: Path) -> str:
    """Return 'YYYY-MM-DD UTC' pulled from the CSV filename."""
    m = re.search(r'card-ratings-(\d{4})-(\d{2})-(\d{2})', csv_path.name)
    if not m:
        raise ValueError(
            f"Could not extract YYYY-MM-DD from CSV filename: {csv_path.name}"
        )
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)} UTC"


def _quiz_targets() -> list[Path]:
    """Quiz files the data refresh applies to, independently: beta always,
    index (production) when configured and present. Each keeps its own
    QUIZ_VERSION and changelog, so beta code changes never leak to production
    via the data refresh."""
    targets = [config.QUIZ_BETA_HTML]
    index = getattr(config, 'QUIZ_INDEX_HTML', None)
    if index is not None and index.exists():
        targets.append(index)
    elif index is not None:
        print(f"  [WARN] {index} not found - refreshing beta only.")
    # P1P1 pack quiz shares the card-quiz anchors, but HOB also needs a booster
    # spec there before it can be drafted. Only refresh it once the array exists,
    # so a not-yet-wired pack page can't fail the daily run.
    pack_beta = getattr(config, 'PACK_BETA_HTML', None)
    if pack_beta is not None and pack_beta.exists():
        if re.search(rf'const {SET_CODE}_CARDS\s*=\s*\[',
                     pack_beta.read_text(encoding='utf-8')):
            targets.append(pack_beta)
        else:
            print(f"  [SKIP] {pack_beta.name} has no {SET_CODE}_CARDS array yet.")
    return targets


def _promote() -> None:
    src = config.QUIZ_BETA_HTML
    dst = getattr(config, 'QUIZ_INDEX_HTML', None)
    if dst is None:
        print("  [SKIP] no QUIZ_INDEX_HTML configured")
        return
    if not src.exists():
        print(f"  [SKIP] {src.name} not found")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"  [PROMOTE] {src.name} -> {dst.name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Refresh HOB 17Lands data in the quiz (quiz-only).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--csv", metavar="FILENAME", default=None,
                        help="CSV in the exports dir or absolute path. "
                             "Default: newest HOB CSV by mtime.")
    parser.add_argument("--fetch", action="store_true",
                        help="Download a fresh HOB CSV from the 17Lands API first "
                             "(ignores --csv).")
    parser.add_argument("--apply", action="store_true",
                        help="Apply the quiz update (otherwise dry-run report only).")
    parser.add_argument("--force", action="store_true",
                        help="With --apply: proceed even if the card count looks low "
                             "or many cards were removed.")
    parser.add_argument("--promote", action="store_true",
                        help="Copy quiz-beta.html -> index.html (ships beta CODE to "
                             "production). Manual use only - the daily Action refreshes "
                             "data in both files and must not pass this. Works standalone "
                             "or after --apply.")
    args = parser.parse_args(argv)

    # --- Standalone promote (manual code-shipping, no data refresh) ---
    if args.promote and not args.apply:
        print("Promoting beta -> main (no data refresh)...")
        _promote()
        return 0

    # --- Optional fresh fetch ---
    if args.fetch:
        try:
            fetched = fetch_17lands.fetch_and_save(
                start_date=config.HOB_START_DATE,
                expansion=config.HOB_EXPANSION,
                fmt=config.HOB_FORMAT,
            )
        except Exception as exc:
            print(f"Fetch failed: {exc}", file=sys.stderr)
            return 2
        args.csv = str(fetched)
        print()

    try:
        new_csv = _resolve_new_csv(args.csv)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    targets = _quiz_targets()
    print(f"Set:        {SET_CODE}")
    print(f"Quiz files: {', '.join(t.name for t in targets)}")
    print(f"CSV:        {new_csv.name}")
    print()

    try:
        data_date = _extract_csv_date(new_csv)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    # --- Dry-run to preview counts / diff ---
    try:
        preview = quiz_updater.update_quiz(
            quiz_html_path=config.QUIZ_BETA_HTML,
            new_csv_path=new_csv,
            new_data_date=data_date,
            dry_run=True,
            set_code=SET_CODE,
        )
    except ValueError as exc:
        print(f"Cannot prepare HOB update: {exc}", file=sys.stderr)
        print("  (Is the HOB_CARDS array + SET_CONFIG.HOB block present in the quiz?)",
              file=sys.stderr)
        return 2

    print(f"Cards: {preview['cards_old_count']} -> {preview['cards_new_count']}")
    if preview['cards_added']:
        print(f"  added ({len(preview['cards_added'])}): "
              f"{', '.join(preview['cards_added'][:20])}"
              + (" ..." if len(preview['cards_added']) > 20 else ""))
    if preview['cards_removed']:
        print(f"  removed ({len(preview['cards_removed'])}): "
              f"{', '.join(preview['cards_removed'][:20])}"
              + (" ..." if len(preview['cards_removed']) > 20 else ""))
    print(f"Version: v{preview['old_quiz_version']} -> v{preview['new_quiz_version']}")
    print()

    if not args.apply:
        print("Dry-run only. Re-run with --apply to write changes.")
        return 0

    # --- Safety gate ---
    new_count = preview['cards_new_count']
    removed = len(preview['cards_removed'])
    risky = new_count < MIN_EXPECTED_CARDS or removed > 15
    if risky and not args.force:
        print(f"REFUSING to apply: new_count={new_count} "
              f"(min {MIN_EXPECTED_CARDS}), removed={removed}. "
              f"Re-run with --force if this is expected.", file=sys.stderr)
        return 1

    # Apply to each target independently; a failure in one file must not block
    # the other (each file's version/changelog is self-contained).
    failures = 0
    pack_beta = getattr(config, 'PACK_BETA_HTML', None)
    for target in targets:
        try:
            result = quiz_updater.update_quiz(
                quiz_html_path=target,
                new_csv_path=new_csv,
                new_data_date=data_date,
                dry_run=False,
                set_code=SET_CODE,
                # Pack page embeds GIH-suppressed cards too (gihWr: null +
                # gihN/gpWr aux); card-quiz files keep scored cards only.
                include_no_data=(pack_beta is not None and target == pack_beta),
            )
        except Exception as exc:
            print(f"[FAILED]  {target.name}: {exc}", file=sys.stderr)
            failures += 1
            continue

        print(f"[APPLIED] {target.name}  v{result['old_quiz_version']} -> "
              f"v{result['new_quiz_version']}  "
              f"({result['cards_old_count']} -> {result['cards_new_count']} cards)")

    if failures:
        print(f"\n{failures} of {len(targets)} quiz file(s) FAILED to update.",
              file=sys.stderr)
        return 2

    if args.promote:
        print()
        print("Promoting beta -> main...")
        _promote()

    print()
    print("Done. Review with: git diff")
    return 0


if __name__ == "__main__":
    sys.exit(main())
