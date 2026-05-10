"""Path constants and conventions for the SOS 17Lands refresh orchestrator.

Operates in two modes, auto-detected from where the script lives:

  LOCAL mode  - script is inside C:\\Users\\<user>\\ClaudeProjects\\.
                ClaudeProjects is the source-of-truth; sync-to-github-pages.ps1
                copies the result into a separate MTG-GitHub-Pages folder.

  CI mode     - script is inside the public MTG-GitHub-Pages repo (e.g. when
                a GitHub Action runs `python mtg/scripts/refresh_sos_17lands.py`).
                There is no separate ClaudeProjects folder; everything lives in
                one repo and the modified files get committed back directly.

The LOCAL paths and CI paths diverge in one place: in ClaudeProjects, the
HTML pages live under `mtg/ratings-project/...` (source-tree layout), while in
MTG-GitHub-Pages they're flattened to `mtg/underover-rated/...` (deployed layout).
Everything else (scripts, shared CSVs, JSON references) is identical.
"""

import os
from pathlib import Path

# This file is at <repo>/mtg/scripts/sos_refresh/config.py, so parents[3] = repo root.
_THIS_REPO_ROOT = Path(__file__).resolve().parents[3]

# Detect mode. CI mode if either:
#   1. We're being run by a GitHub Actions runner, OR
#   2. The current repo lacks a ClaudeProjects-style ratings-project tree (i.e.
#      we're inside MTG-GitHub-Pages directly).
_IS_CI = (
    os.environ.get('GITHUB_ACTIONS') == 'true'
    or not (_THIS_REPO_ROOT / 'mtg' / 'ratings-project' / 'underover-rated').exists()
)

if _IS_CI:
    # ----- CI mode: everything lives in MTG-GitHub-Pages -----
    CLAUDE_PROJECTS_ROOT = _THIS_REPO_ROOT
    GITHUB_PAGES_ROOT = _THIS_REPO_ROOT

    LANDS_EXPORTS_DIR = _THIS_REPO_ROOT / "mtg" / "shared-data" / "17lands exports"
    LANDS_EXPORTS_DIR_GH = LANDS_EXPORTS_DIR

    SOS_BETA_HTML = _THIS_REPO_ROOT / "mtg" / "underover-rated" / "sos" / "sos-beta.html"
    SOS_BETA_HTML_GH = SOS_BETA_HTML

    ARCHETYPE_HTML = _THIS_REPO_ROOT / "mtg" / "underover-rated" / "sos" / "ARCHETYPE_ANALYSIS.html"
    ARCHETYPE_HTML_GH = ARCHETYPE_HTML
    ARCHETYPE_PY = _THIS_REPO_ROOT / "mtg" / "ratings-project" / "sos" / "analyze_archetypes.py"

    QUIZ_BETA_HTML = _THIS_REPO_ROOT / "17lands-quiz" / "quiz-beta.html"

    SCRYFALL_REFERENCE_JSON = _THIS_REPO_ROOT / "mtg" / "shared-data" / "data" / "sos" / "scryfall_reference.json"
    SOS_TYPES_MAPPING_JSON = _THIS_REPO_ROOT / "mtg" / "quiz-project" / "sos-types-mapping.json"

    REPORTS_DIR = _THIS_REPO_ROOT / "tmp" / "sos_refresh_reports"

    # CI-only: locations of the "main" promoted pages (auto-promoted by the orchestrator)
    SOS_INDEX_HTML = _THIS_REPO_ROOT / "mtg" / "underover-rated" / "sos" / "sos-index.html"
    QUIZ_INDEX_HTML = _THIS_REPO_ROOT / "17lands-quiz" / "index.html"
else:
    # ----- LOCAL mode: ClaudeProjects + MTG-GitHub-Pages as separate folders -----
    CLAUDE_PROJECTS_ROOT = Path(r"c:\Users\<user>\ClaudeProjects")
    GITHUB_PAGES_ROOT = Path(r"c:\Users\<user>\MTG-GitHub-Pages")

    # Shared 17Lands data folder (CSVs live here)
    LANDS_EXPORTS_DIR = CLAUDE_PROJECTS_ROOT / "mtg" / "shared-data" / "17lands exports"
    LANDS_EXPORTS_DIR_GH = GITHUB_PAGES_ROOT / "mtg" / "shared-data" / "17lands exports"

    # Consumer 1: SOS Over/Under-Rated page
    SOS_BETA_HTML = CLAUDE_PROJECTS_ROOT / "mtg" / "ratings-project" / "underover-rated" / "sos" / "sos-beta.html"
    SOS_BETA_HTML_GH = GITHUB_PAGES_ROOT / "mtg" / "underover-rated" / "sos" / "sos-beta.html"

    # Consumer 2: SOS Archetype Analysis (HTML lives in ClaudeProjects/scripts; the analyser script
    # is in ClaudeProjects/sos)
    ARCHETYPE_HTML = CLAUDE_PROJECTS_ROOT / "mtg" / "ratings-project" / "scripts" / "ARCHETYPE_ANALYSIS.html"
    ARCHETYPE_HTML_GH = GITHUB_PAGES_ROOT / "mtg" / "underover-rated" / "sos" / "ARCHETYPE_ANALYSIS.html"
    ARCHETYPE_PY = CLAUDE_PROJECTS_ROOT / "mtg" / "ratings-project" / "sos" / "analyze_archetypes.py"

    # Consumer 3: SOS Quiz (beta only — promotion to index.html happens via --promote flag)
    QUIZ_BETA_HTML = GITHUB_PAGES_ROOT / "17lands-quiz" / "quiz-beta.html"

    # Quiz generation dependencies
    SCRYFALL_REFERENCE_JSON = CLAUDE_PROJECTS_ROOT / "mtg" / "quiz-project" / "17lands-quiz-root" / "scryfall_reference.json"
    SOS_TYPES_MAPPING_JSON = CLAUDE_PROJECTS_ROOT / "mtg" / "quiz-project" / "sos-types-mapping.json"

    # Reports output
    REPORTS_DIR = CLAUDE_PROJECTS_ROOT / "mtg" / "scripts" / "sos_refresh_reports"

    # Promote targets (used by --promote flag, copy beta -> main)
    SOS_INDEX_HTML = CLAUDE_PROJECTS_ROOT / "mtg" / "ratings-project" / "underover-rated" / "sos" / "sos-index.html"
    QUIZ_INDEX_HTML = GITHUB_PAGES_ROOT / "17lands-quiz" / "index.html"

# Module mode flag — useful for log output and conditional behavior in updaters.
IS_CI = _IS_CI

# Filter threshold matches analyze_archetypes.py default
MIN_GIH = 500

# Glob pattern for SOS 17Lands exports (used to discover newest CSV when --csv omitted)
SOS_CSV_GLOB = "SOS card-ratings-*.csv"

# 17Lands API config for automated CSV fetching
LANDS_API_URL = "https://www.17lands.com/card_ratings/data"
SOS_EXPANSION = "SOS"
SOS_FORMAT = "PremierDraft"
SOS_START_DATE = "2026-04-21"  # SOS Premier Draft release date

# Diff report flag thresholds
DIFF_FLAGS = {
    # GIH WR mean shift in percentage points that should flag for review
    "mean_shift_pp": 0.5,
    # GIH WR SD shift in percentage points
    "sd_shift_pp": 0.2,
    # Z-score change for an individual card to flag
    "card_zscore_shift": 2.0,
    # How many top-N to track for under/overrated reshuffles
    "top_n": 20,
}
