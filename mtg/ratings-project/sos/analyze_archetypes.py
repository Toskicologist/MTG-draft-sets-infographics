#!/usr/bin/env python3
"""
SOS color/archetype analysis.

For each card, compute consensus error (avg-of-all-reviewer percentile minus
actual GIH WR percentile). Then aggregate by:
- Color identity (mono vs multi)
- Specific colors and color pairs
- 5 SOS archetypes: WB Silverquill, UR Prismari, BG Witherbloom,
  RW Lorehold, GU Quandrix

Goal: find which colors / color pairs / archetypes were systematically
under- or over-rated by the reviewer panel.
"""

import argparse
import csv
import math
import re
from pathlib import Path
from collections import defaultdict

MIN_GIH = 500
EXPERTS = ['cgb', 'ds', 'cs', 'llu_a', 'llu_m', 'cfb']

ARCHETYPES = {
    'WB': ('Silverquill', 'Repartee/Aggro'),
    'UR': ('Prismari', 'Opus/Spellcasting'),
    'BG': ('Witherbloom', 'Infusion/Swarm'),
    'RW': ('Lorehold', 'Flashback/Excavation'),
    'GU': ('Quandrix', 'Increment/Value'),
}

ROOT = Path(__file__).resolve().parents[3]


def parse_csv(path):
    with open(path, 'r', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def normalize_name(s):
    return s.lower().strip().strip('"')


def to_float(v):
    if v is None or v == '' or v == 'N/A':
        return None
    try:
        return float(str(v).replace('%', '').replace(',', ''))
    except ValueError:
        return None


def to_int(v):
    f = to_float(v)
    return int(f) if f is not None else None


def rankdata(values):
    n = len(values)
    indexed = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1
    return ranks


def color_pair_canonical(colors):
    """Return canonical 2-letter color pair or None."""
    if not colors or len(colors) != 2:
        return None
    # Map to archetype canonical order
    for k in ARCHETYPES:
        if set(colors) == set(k):
            return k
    return ''.join(sorted(colors))


def archetypes_for_card(colors):
    """Return list of archetype keys this card could fit into.

    Mono-color: card fits any archetype that includes that color (e.g. W fits WB and RW).
    2-color matching: fits exactly one archetype.
    Off-archetype 2-color: returns 'OFF_ARCHETYPE'.
    Multi: returns 'MULTI'.
    Colorless: returns 'COLORLESS'.
    """
    if not colors:
        return ['COLORLESS']
    if len(colors) == 1:
        c = colors
        return [k for k in ARCHETYPES if c in k]
    if len(colors) == 2:
        canonical = color_pair_canonical(colors)
        if canonical in ARCHETYPES:
            return [canonical]
        return ['OFF_ARCHETYPE']
    return ['MULTI']


def main(args=None):
    parser = argparse.ArgumentParser(
        description='Analyze SOS archetype consensus vs actual performance.'
    )
    parser.add_argument(
        '--csv',
        type=str,
        default=None,
        help='Path to 17Lands CSV file (absolute or relative to project root). '
             'Defaults to mtg/shared-data/17lands exports/SOS card-ratings-2026-04-27 1245 .csv'
    )
    parsed = parser.parse_args(args)

    expert_path = ROOT / 'mtg' / 'shared-data' / 'data' / 'sos' / 'sos-expert-ratings-normalized-FINAL.csv'

    if parsed.csv:
        lands_path = Path(parsed.csv)
        if not lands_path.is_absolute():
            lands_path = ROOT / lands_path
    else:
        lands_path = ROOT / 'mtg' / 'shared-data' / '17lands exports' / 'SOS card-ratings-2026-04-27 1245 .csv'

    expert_rows = parse_csv(expert_path)
    lands_rows = parse_csv(lands_path)

    lands_lookup = {}
    for row in lands_rows:
        name = normalize_name(row['Name'])
        gih_wr = to_float(row.get('GIH WR'))
        gih_count = to_int(row.get('# GIH'))
        if gih_wr is None or gih_count is None:
            continue
        lands_lookup[name] = {
            'gih_wr': gih_wr, 'gih_count': gih_count,
            'lands_color': row.get('Color', '').strip(),
        }

    cards = []
    for row in expert_rows:
        card_name = row['card_name'].strip('"')
        normalized = normalize_name(card_name)
        lands = lands_lookup.get(normalized)
        if not lands:
            continue
        colors = row.get('colors', '').strip().upper()
        # Some cards have things like "WUBRG" or hybrid markers - keep as-is
        record = {
            'name': card_name,
            'rarity': row.get('rarity', '').strip().lower(),
            'colors': colors,
            'gih_wr': lands['gih_wr'],
            'gih_count': lands['gih_count'],
            'expert_zscore_avg': to_float(row.get('average_zscore')),
            'expert_count': to_int(row.get('expert_count')) or 0,
        }
        if record['expert_zscore_avg'] is None or record['expert_count'] < 3:
            # Skip cards with too few expert ratings
            continue
        cards.append(record)

    cards = [c for c in cards if c['gih_count'] >= MIN_GIH]
    print(f"Cards in analysis: {len(cards)}")

    # Compute percentile ranks for both consensus expert and actual
    expert_zs = [c['expert_zscore_avg'] for c in cards]
    actual_wrs = [c['gih_wr'] for c in cards]

    expert_pct = [(r - 0.5) / len(expert_zs) for r in rankdata(expert_zs)]
    actual_pct = [(r - 0.5) / len(actual_wrs) for r in rankdata(actual_wrs)]

    for i, c in enumerate(cards):
        c['expert_pct'] = expert_pct[i]
        c['actual_pct'] = actual_pct[i]
        c['discrepancy'] = expert_pct[i] - actual_pct[i]  # +ve = overrated, -ve = underrated

    # ---- Top 20 underrated and overrated ----
    sorted_under = sorted(cards, key=lambda c: c['discrepancy'])[:20]
    sorted_over = sorted(cards, key=lambda c: c['discrepancy'], reverse=True)[:20]

    print(f"\n=== Top 20 Most UNDERRATED (consensus much lower than actual) ===")
    print(f"{'Card':40} {'Rarity':10} {'Colors':8} {'Exp pct':>8} {'Act pct':>8} {'Diff':>8} {'GIH%':>8}")
    for c in sorted_under:
        print(f"{c['name'][:39]:40} {c['rarity']:10} {c['colors']:8} {c['expert_pct']:>8.2f} {c['actual_pct']:>8.2f} {c['discrepancy']:>+8.2f} {c['gih_wr']:>7.1f}%")

    print(f"\n=== Top 20 Most OVERRATED (consensus much higher than actual) ===")
    print(f"{'Card':40} {'Rarity':10} {'Colors':8} {'Exp pct':>8} {'Act pct':>8} {'Diff':>8} {'GIH%':>8}")
    for c in sorted_over:
        print(f"{c['name'][:39]:40} {c['rarity']:10} {c['colors']:8} {c['expert_pct']:>8.2f} {c['actual_pct']:>8.2f} {c['discrepancy']:>+8.2f} {c['gih_wr']:>7.1f}%")

    # ---- By color identity (mono only) ----
    print(f"\n=== Mono-color cards: avg discrepancy ===")
    print(f"{'Color':10} {'n':>4} {'Mean disc':>10} {'Median':>8} {'Mean GIH%':>10}")
    for col in ['W', 'U', 'B', 'R', 'G']:
        col_cards = [c for c in cards if c['colors'] == col]
        if not col_cards:
            continue
        discs = [c['discrepancy'] for c in col_cards]
        wrs = [c['gih_wr'] for c in col_cards]
        mean = sum(discs) / len(discs)
        sorted_discs = sorted(discs)
        median = sorted_discs[len(sorted_discs) // 2]
        mean_wr = sum(wrs) / len(wrs)
        print(f"{col:10} {len(col_cards):>4} {mean:>+10.3f} {median:>+8.3f} {mean_wr:>9.1f}%")

    # ---- By 2-color pair (archetypes) ----
    print(f"\n=== Color pair / archetype: avg discrepancy ===")
    print(f"{'Pair':6} {'Archetype':25} {'n':>4} {'Mean disc':>10} {'Mean GIH%':>10}")
    for pair, (name, theme) in ARCHETYPES.items():
        # Match either order
        pair_cards = [c for c in cards if len(c['colors']) == 2 and set(c['colors']) == set(pair)]
        if not pair_cards:
            print(f"{pair:6} {name + ' ' + theme:25} {'0':>4}")
            continue
        discs = [c['discrepancy'] for c in pair_cards]
        wrs = [c['gih_wr'] for c in pair_cards]
        mean = sum(discs) / len(discs)
        mean_wr = sum(wrs) / len(wrs)
        print(f"{pair:6} {name + ' (' + theme + ')':35} {len(pair_cards):>4} {mean:>+10.3f} {mean_wr:>9.1f}%")

    # Off-archetype 2-color cards
    off_arch = [c for c in cards if len(c['colors']) == 2 and color_pair_canonical(list(c['colors'])) not in ARCHETYPES]
    if off_arch:
        discs = [c['discrepancy'] for c in off_arch]
        mean = sum(discs) / len(discs)
        mean_wr = sum(c['gih_wr'] for c in off_arch) / len(off_arch)
        print(f"{'OTHER':6} {'Off-archetype 2-color':35} {len(off_arch):>4} {mean:>+10.3f} {mean_wr:>9.1f}%")

    # ---- Color count breakdown ----
    print(f"\n=== Card complexity (color count): avg discrepancy ===")
    buckets = defaultdict(list)
    for c in cards:
        n = len(c['colors']) if c['colors'] else 0
        if n == 0:
            buckets['Colorless'].append(c)
        elif n == 1:
            buckets['Mono'].append(c)
        elif n == 2:
            buckets['2-color'].append(c)
        else:
            buckets['3+ color'].append(c)
    for label in ['Colorless', 'Mono', '2-color', '3+ color']:
        bcards = buckets.get(label, [])
        if not bcards:
            continue
        discs = [c['discrepancy'] for c in bcards]
        wrs = [c['gih_wr'] for c in bcards]
        mean = sum(discs) / len(discs)
        mean_wr = sum(wrs) / len(wrs)
        print(f"{label:12} {len(bcards):>4} cards   mean disc {mean:>+.3f}   mean GIH {mean_wr:.1f}%")

    # ---- Per-archetype top cards ----
    print(f"\n=== Top under/overrated cards per archetype ===")
    for pair, (aname, theme) in ARCHETYPES.items():
        pair_cards = [c for c in cards if len(c['colors']) == 2 and set(c['colors']) == set(pair)]
        if len(pair_cards) < 3:
            continue
        ps = sorted(pair_cards, key=lambda c: c['discrepancy'])
        print(f"\n  {pair} {aname} ({theme}) — {len(pair_cards)} cards")
        print(f"    Most underrated:")
        for c in ps[:3]:
            print(f"      {c['name']:35} ({c['rarity']:8}) disc={c['discrepancy']:+.2f}  GIH={c['gih_wr']:.1f}%")
        print(f"    Most overrated:")
        for c in ps[-3:][::-1]:
            print(f"      {c['name']:35} ({c['rarity']:8}) disc={c['discrepancy']:+.2f}  GIH={c['gih_wr']:.1f}%")

    # ---- Word-frequency in under vs overrated names ----
    def tokens(name):
        return [w.lower() for w in re.findall(r"[A-Za-z']+", name) if len(w) > 3]

    under_words = defaultdict(int)
    over_words = defaultdict(int)
    for c in sorted_under:
        for t in tokens(c['name']):
            under_words[t] += 1
    for c in sorted_over:
        for t in tokens(c['name']):
            over_words[t] += 1

    # Words appearing 3+ times in one but not the other
    print(f"\n=== Recurring words in top-20 lists ===")
    for label, wd in [('UNDERRATED', under_words), ('OVERRATED', over_words)]:
        common = sorted([(w, n) for w, n in wd.items() if n >= 2], key=lambda x: -x[1])
        if common:
            print(f"  {label}: " + ", ".join(f"{w}({n})" for w, n in common))

    # ---- Save CSV outputs ----
    out_dir = ROOT / 'mtg' / 'ratings-project' / 'sos'

    with open(out_dir / 'archetype_discrepancies.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['pair', 'archetype', 'theme', 'n', 'mean_discrepancy', 'mean_gih_wr'])
        for pair, (aname, theme) in ARCHETYPES.items():
            pair_cards = [c for c in cards if len(c['colors']) == 2 and set(c['colors']) == set(pair)]
            if not pair_cards:
                w.writerow([pair, aname, theme, 0, '', ''])
                continue
            discs = [c['discrepancy'] for c in pair_cards]
            wrs = [c['gih_wr'] for c in pair_cards]
            w.writerow([pair, aname, theme, len(pair_cards),
                        f"{sum(discs)/len(discs):.4f}", f"{sum(wrs)/len(wrs):.2f}"])

    with open(out_dir / 'card_discrepancies.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['card', 'rarity', 'colors', 'expert_pct', 'actual_pct', 'discrepancy', 'gih_wr', 'gih_count'])
        for c in sorted(cards, key=lambda c: c['discrepancy']):
            w.writerow([c['name'], c['rarity'], c['colors'],
                        f"{c['expert_pct']:.4f}", f"{c['actual_pct']:.4f}",
                        f"{c['discrepancy']:+.4f}", f"{c['gih_wr']:.2f}", c['gih_count']])

    return cards, sorted_under, sorted_over


if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
