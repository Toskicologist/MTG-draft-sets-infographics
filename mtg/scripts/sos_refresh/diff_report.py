"""
diff_report.py — Compare two SOS 17Lands CSVs and produce a human-review markdown report.

Public API:
    generate_diff_report(old_csv, new_csv, archetype_html, output_path) -> dict
"""

import re
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sos_refresh.config import DIFF_FLAGS


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load(path: Path, min_gih: int = 0) -> list[dict]:
    """Lazy import of csv_loader so the module can be imported even if
    csv_loader isn't built yet (will fail at call time, not import time)."""
    from sos_refresh.csv_loader import load_sos_csv  # noqa: PLC0415
    return load_sos_csv(path, min_gih=min_gih)


def _pop_stats(cards: list[dict]) -> tuple[float, float]:
    """Return population mean and SD of GIH WR for a list of card dicts.

    GIH WR values may be expressed as percentage strings ("57.3%") or floats.
    Normalises to float percentages (0–100 scale).
    """
    values = [_wr_float(c["gih_wr"]) for c in cards]
    if not values:
        return 0.0, 0.0
    mean = statistics.mean(values)
    # Population SD (not sample) — consistent with z-score usage below
    if len(values) < 2:
        return mean, 0.0
    sd = statistics.pstdev(values)
    return mean, sd


def _wr_float(val) -> float:
    """Coerce GIH WR to a plain float (0–100 scale)."""
    if isinstance(val, str):
        val = val.strip().rstrip("%")
        return float(val)
    return float(val)


def _zscore(val: float, mean: float, sd: float) -> Optional[float]:
    if sd == 0:
        return None
    return (val - mean) / sd


def _card_index(cards: list[dict]) -> dict[str, dict]:
    """Build name -> card dict lookup."""
    return {c["name"]: c for c in cards}


def _fmt_wr(val) -> str:
    return f"{_wr_float(val):.1f}%"


def _fmt_z(z: Optional[float]) -> str:
    if z is None:
        return "N/A"
    return f"{z:+.2f}σ"


# ---------------------------------------------------------------------------
# Prose extraction helpers
# ---------------------------------------------------------------------------

_AUTO_REGION_RE = re.compile(
    r"<!--\s*AUTO_REGION:[^>]+START\s*-->.*?<!--\s*AUTO_REGION:[^>]+END\s*-->",
    re.DOTALL | re.IGNORECASE,
)

_TAG_RE = re.compile(r"<[^>]+>")


def _extract_prose_text(html_path: Path) -> str:
    """Strip AUTO_REGION blocks and HTML tags; return plain text for card-name search."""
    text = html_path.read_text(encoding="utf-8", errors="replace")
    # Remove auto-generated regions
    text = _AUTO_REGION_RE.sub(" ", text)
    # Strip remaining tags
    text = _TAG_RE.sub(" ", text)
    return text


def _find_prose_mentions(prose_text: str, card_names: set[str]) -> set[str]:
    """Return subset of card_names that appear in prose_text (word-boundary, case-sensitive)."""
    mentioned = set()
    for name in card_names:
        pattern = r"\b" + re.escape(name) + r"\b"
        if re.search(pattern, prose_text):
            mentioned.add(name)
    return mentioned


# ---------------------------------------------------------------------------
# Diff logic helpers
# ---------------------------------------------------------------------------

def _rank_list(cards: list[dict], mean: float, sd: float, top_n: int, highest: bool) -> list[tuple]:
    """Return top_n cards ranked by GIH WR (highest or lowest).

    Returns list of (rank_1based, name, rarity, gih_wr, z) tuples.
    """
    sorted_cards = sorted(
        cards,
        key=lambda c: _wr_float(c["gih_wr"]),
        reverse=highest,
    )
    result = []
    for i, c in enumerate(sorted_cards[:top_n], start=1):
        z = _zscore(_wr_float(c["gih_wr"]), mean, sd)
        result.append((i, c["name"], c["rarity"], c["gih_wr"], z))
    return result


def _rank_change_symbol(old_rank: Optional[int], new_rank: int) -> str:
    if old_rank is None:
        return "NEW"
    delta = old_rank - new_rank  # positive = moved up in ranking
    if delta > 0:
        return f"▲{delta}"
    elif delta < 0:
        return f"▼{abs(delta)}"
    return "—"


def _reshuffle_section(
    old_ranked: list[tuple],
    new_ranked: list[tuple],
    section_title: str,
    flag_key: str,
    top_n: int,
) -> tuple[str, bool]:
    """Build markdown for a reshuffle section.

    Returns (markdown_str, flag_bool).
    """
    old_names_to_rank = {name: rank for rank, name, *_ in old_ranked}
    new_names = {name for _, name, *_ in new_ranked}
    old_names_set = set(old_names_to_rank.keys())
    changed = (new_names - old_names_set) | (old_names_set - new_names)
    flag = len(changed) >= 3

    lines = [f"### {section_title}", ""]
    lines.append(f"| Rank | Card | Rarity | GIH WR | Rank change |")
    lines.append(f"|------|------|--------|--------|-------------|")
    for rank, name, rarity, gih_wr, _z in new_ranked:
        old_rank = old_names_to_rank.get(name)
        sym = _rank_change_symbol(old_rank, rank)
        lines.append(f"| {rank} | {name} | {rarity} | {_fmt_wr(gih_wr)} | {sym} |")

    changed_count = len(new_names - old_names_set)
    lines.append("")
    lines.append(
        f"**{changed_count} card(s) entered this list vs previous CSV.** "
        f"{'⚑ Flag: ≥3 changes detected.' if flag else 'No flag.'}"
    )
    lines.append("")
    return "\n".join(lines), flag


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def generate_diff_report(
    old_csv: Path,
    new_csv: Path,
    archetype_html: Path,
    output_path: Path,
) -> dict:
    """Compare two SOS 17Lands CSVs and write a markdown review-flag report.

    Returns a dict with 'flags_fired', 'summary', 'report_path', 'flags'.
    """
    old_csv = Path(old_csv)
    new_csv = Path(new_csv)
    archetype_html = Path(archetype_html)
    output_path = Path(output_path)

    top_n: int = DIFF_FLAGS["top_n"]
    mean_shift_pp: float = DIFF_FLAGS["mean_shift_pp"]
    sd_shift_pp: float = DIFF_FLAGS["sd_shift_pp"]
    card_zscore_shift: float = DIFF_FLAGS["card_zscore_shift"]

    # ---- Load cards at both thresholds ----
    old_all = _load(old_csv, min_gih=0)
    new_all = _load(new_csv, min_gih=0)
    old_500 = _load(old_csv, min_gih=500)
    new_500 = _load(new_csv, min_gih=500)

    old_mean, old_sd = _pop_stats(old_500)
    new_mean, new_sd = _pop_stats(new_500)

    # ---- Flags init ----
    flags = {
        "mean_shift_significant": False,
        "sd_shift_significant": False,
        "top20_under_changed": False,
        "top20_over_changed": False,
        "has_big_movers": False,
        "has_prose_mentioned_movers": False,
    }

    # ---- Build name sets ----
    old_names_500 = {c["name"] for c in old_500}
    new_names_500 = {c["name"] for c in new_500}
    added = new_names_500 - old_names_500
    removed = old_names_500 - new_names_500

    # ---- Mean / SD shift flags ----
    mean_shift = abs(new_mean - old_mean)
    sd_shift = abs(new_sd - old_sd)
    flags["mean_shift_significant"] = mean_shift > mean_shift_pp
    flags["sd_shift_significant"] = sd_shift > sd_shift_pp

    # ---- Top-20 rankings ----
    old_top20_over = _rank_list(old_500, old_mean, old_sd, top_n, highest=True)
    new_top20_over = _rank_list(new_500, new_mean, new_sd, top_n, highest=True)
    old_top20_under = _rank_list(old_500, old_mean, old_sd, top_n, highest=False)
    new_top20_under = _rank_list(new_500, new_mean, new_sd, top_n, highest=False)

    over_section_md, top20_over_flag = _reshuffle_section(
        old_top20_over, new_top20_over,
        f"Top {top_n} highest GIH WR (new CSV)",
        "top20_over_changed",
        top_n,
    )
    under_section_md, top20_under_flag = _reshuffle_section(
        old_top20_under, new_top20_under,
        f"Bottom {top_n} lowest GIH WR (new CSV)",
        "top20_under_changed",
        top_n,
    )
    flags["top20_over_changed"] = top20_over_flag
    flags["top20_under_changed"] = top20_under_flag

    # ---- Big movers ----
    # cards present in both old and new at min_gih=500
    old_idx = _card_index(old_500)
    new_idx = _card_index(new_500)
    common_names = old_names_500 & new_names_500

    big_movers = []
    for name in sorted(common_names):
        old_c = old_idx[name]
        new_c = new_idx[name]
        old_wr = _wr_float(old_c["gih_wr"])
        new_wr = _wr_float(new_c["gih_wr"])
        old_z = _zscore(old_wr, old_mean, old_sd)
        new_z = _zscore(new_wr, new_mean, new_sd)
        if old_z is None or new_z is None:
            continue
        delta_z = new_z - old_z
        if abs(delta_z) > card_zscore_shift:
            big_movers.append({
                "name": name,
                "rarity": new_c["rarity"],
                "old_wr": old_wr,
                "new_wr": new_wr,
                "old_z": old_z,
                "new_z": new_z,
                "delta_z": delta_z,
            })

    # Sort by abs(delta_z) descending
    big_movers.sort(key=lambda x: abs(x["delta_z"]), reverse=True)
    flags["has_big_movers"] = len(big_movers) > 0

    # ---- Prose-mentioned movers ----
    big_mover_names = {m["name"] for m in big_movers}

    # Also include names that changed top-20 membership
    old_top_names = {name for _, name, *_ in old_top20_over + old_top20_under}
    new_top_names = {name for _, name, *_ in new_top20_over + new_top20_under}
    top20_changers = (old_top_names ^ new_top_names)  # symmetric difference

    all_candidate_names = big_mover_names | top20_changers
    all_card_names = {c["name"] for c in old_all + new_all}

    prose_mentioned_all: set[str] = set()
    prose_mentioned_movers: set[str] = set()
    if archetype_html.exists():
        prose_text = _extract_prose_text(archetype_html)
        prose_mentioned_all = _find_prose_mentions(prose_text, all_card_names)
        prose_mentioned_movers = _find_prose_mentions(prose_text, all_candidate_names)

    flags["has_prose_mentioned_movers"] = len(prose_mentioned_movers) > 0

    # ---- Build markdown ----
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _flag_str(val: bool) -> str:
        return "YES — review needed" if val else "no"

    lines = []

    # --- Section 1: Header ---
    lines += [
        "# SOS 17Lands Diff Report",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Old CSV | `{old_csv.name}` |",
        f"| New CSV | `{new_csv.name}` |",
        f"| Generated | {ts} |",
        f"| Archetype HTML | `{archetype_html.name}` |",
        "",
    ]

    # --- Section 2: Summary stats ---
    def _cnt(lst): return len(lst)

    lines += [
        "## Summary Stats",
        "",
        f"| | Old CSV | New CSV |",
        f"|--|---------|---------|",
        f"| Cards (all, min_gih=0) | {_cnt(old_all)} | {_cnt(new_all)} |",
        f"| Cards (min_gih=500) | {_cnt(old_500)} | {_cnt(new_500)} |",
        f"| Mean GIH WR (min_gih=500) | {old_mean:.2f}% | {new_mean:.2f}% |",
        f"| SD GIH WR (min_gih=500) | {old_sd:.2f}pp | {new_sd:.2f}pp |",
        f"| Mean shift | {new_mean - old_mean:+.3f}pp | threshold {mean_shift_pp}pp |",
        f"| SD shift | {new_sd - old_sd:+.3f}pp | threshold {sd_shift_pp}pp |",
        "",
        f"**Mean shift significant:** {_flag_str(flags['mean_shift_significant'])}  ",
        f"**SD shift significant:** {_flag_str(flags['sd_shift_significant'])}",
        "",
    ]

    # --- Section 3: Card set delta ---
    lines.append("## Card Set Delta (min_gih=500)")
    lines.append("")

    if added:
        lines.append(f"**Added ({len(added)} cards):**")
        lines.append("")
        lines.append("| Card | Rarity |")
        lines.append("|------|--------|")
        for name in sorted(added):
            rarity = new_idx[name]["rarity"] if name in new_idx else "?"
            lines.append(f"| {name} | {rarity} |")
        lines.append("")
    else:
        lines.append("**Added:** No changes.")
        lines.append("")

    if removed:
        lines.append(f"**Removed ({len(removed)} cards):**")
        lines.append("")
        lines.append("| Card | Rarity |")
        lines.append("|------|--------|")
        for name in sorted(removed):
            rarity = old_idx[name]["rarity"] if name in old_idx else "?"
            lines.append(f"| {name} | {rarity} |")
        lines.append("")
    else:
        lines.append("**Removed:** No changes.")
        lines.append("")

    # --- Section 4: Reshuffle ---
    lines.append("## GIH WR Rank Reshuffles")
    lines.append("")
    lines.append(over_section_md)
    lines.append(under_section_md)

    # --- Section 5: Big movers ---
    lines.append("## Big Movers (>2σ z-score shift)")
    lines.append("")
    if big_movers:
        lines.append(
            f"Cards whose GIH WR z-score (within its CSV's distribution) "
            f"changed by >{card_zscore_shift}σ. "
            f"Threshold: {card_zscore_shift}σ."
        )
        lines.append("")
        lines.append("| Card | Rarity | Old GIH WR | New GIH WR | Old z | New z | Δz |")
        lines.append("|------|--------|------------|------------|-------|-------|----|")
        for m in big_movers:
            lines.append(
                f"| {m['name']} | {m['rarity']} "
                f"| {m['old_wr']:.1f}% | {m['new_wr']:.1f}% "
                f"| {_fmt_z(m['old_z'])} | {_fmt_z(m['new_z'])} "
                f"| {m['delta_z']:+.2f}σ |"
            )
        lines.append("")
    else:
        lines.append("No cards moved by more than the threshold. No flag.")
        lines.append("")

    # --- Section 6: Prose-mentioned movers ---
    lines.append("## Prose-Mentioned Movers")
    lines.append("")
    lines.append(
        "_Cards named in handwritten prose (outside AUTO_REGION blocks) "
        "that are also big movers or changed top-20 membership. "
        "These are the paragraphs most likely to need re-reading._"
    )
    lines.append("")
    if prose_mentioned_movers:
        lines.append("| Card | In big movers? | Changed top-20? | Notes |")
        lines.append("|------|---------------|-----------------|-------|")
        for name in sorted(prose_mentioned_movers):
            in_big = "Yes" if name in big_mover_names else "No"
            in_top = "Yes" if name in top20_changers else "No"
            if name in big_mover_names:
                m = next(x for x in big_movers if x["name"] == name)
                note = f"WR {m['old_wr']:.1f}% → {m['new_wr']:.1f}% (Δz {m['delta_z']:+.2f}σ)"
            elif name in top20_changers:
                in_old_top = name in old_top_names
                in_new_top = name in new_top_names
                note = (
                    "Entered top-20 list" if (in_new_top and not in_old_top) else
                    "Left top-20 list"
                )
            else:
                note = "—"
            lines.append(f"| {name} | {in_big} | {in_top} | {note} |")
        lines.append("")
        lines.append(
            f"**{len(prose_mentioned_movers)} prose-mentioned card(s) need attention.**"
        )
        lines.append("")
    else:
        lines.append(
            "No prose-mentioned cards are big movers or changed top-20 membership. No flag."
        )
        lines.append("")

    # --- Section 7: Per-archetype shifts (placeholder) ---
    lines += [
        "## Per-Archetype Shifts",
        "",
        "_Skipped in this report — would require running analyze_archetypes.py twice._",
        "",
        f"Re-run `analyze_archetypes.py --csv {new_csv.name}` for full archetype shift analysis.",
        "",
    ]

    # ---- Assemble summary ----
    fired = [k for k, v in flags.items() if v]
    if fired:
        summary = (
            f"REVIEW NEEDED — {len(fired)} flag(s) fired: {', '.join(fired)}. "
            f"Mean: {old_mean:.2f}% → {new_mean:.2f}% ({new_mean - old_mean:+.3f}pp), "
            f"SD: {old_sd:.2f} → {new_sd:.2f}pp."
        )
    else:
        summary = (
            f"No flags fired. "
            f"Mean GIH WR: {old_mean:.2f}% → {new_mean:.2f}% ({new_mean - old_mean:+.3f}pp), "
            f"SD: {old_sd:.2f} → {new_sd:.2f}pp. Archetype prose likely still valid."
        )

    # Prepend summary after header
    lines.insert(lines.index("## Summary Stats"), f"> **Summary:** {summary}\n")

    # ---- Write output ----
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "flags_fired": any(flags.values()),
        "summary": summary,
        "report_path": output_path,
        "flags": flags,
    }
