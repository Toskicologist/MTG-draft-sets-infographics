#!/usr/bin/env node
/**
 * build-tcg-prices.mjs  (v1.0.0)
 *
 * Downloads TCGplayer pricing for all Magic groups from the free TCGcsv
 * mirror and reduces it to a slim { productId -> {mid,market,low} } snapshot
 * that the static deckbuilder page can fetch same-origin (no CORS, no key).
 *
 * TCGcsv refreshes ~20:00 UTC daily; run this after that. Map a card with
 * Scryfall's `tcgplayer_id` (== TCGcsv productId).
 *
 * Run: node scripts/build-tcg-prices.mjs [--max-groups N]
 * Out: data/tcg-prices.json
 *
 * Never substitutes data: a product whose midPrice is 0/null (TCGcsv's
 * "no data" sentinel) is OMITTED, so the page flags it rather than guessing.
 */
import { writeFile, mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const OUT  = join(ROOT, "data", "tcg-prices.json");
const META = join(ROOT, "data", "tcg-prices-meta.json");
const BASE = "https://tcgcsv.com/tcgplayer";
const MTG_CATEGORY = 1;
const SLEEP = ms => new Promise(r => setTimeout(r, ms));

const argMax = process.argv.indexOf("--max-groups");
const MAX_GROUPS = argMax > -1 ? parseInt(process.argv[argMax + 1], 10) : Infinity;

async function getJSON(url, tries = 3) {
  for (let i = 1; i <= tries; i++) {
    try {
      const r = await fetch(url, { headers: {
        Accept: "application/json",
        "User-Agent": "budget-modern-deckbuilder/1.0 (+github-pages static price snapshot)",
      } });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      if (j && j.success === false) throw new Error(`API error: ${JSON.stringify(j.errors)}`);
      return j;
    } catch (e) {
      if (i === tries) throw e;
      await SLEEP(500 * i);
    }
  }
}

const round = n => Math.round(n * 100) / 100;

async function main() {
  const startedAt = new Date().toISOString();
  console.error(`[tcg-prices] start ${startedAt}`);

  const groups = (await getJSON(`${BASE}/${MTG_CATEGORY}/groups`)).results || [];
  console.error(`[tcg-prices] ${groups.length} Magic groups`);

  const prices = Object.create(null);
  let kept = 0, skipped = 0, done = 0;
  const total = Math.min(groups.length, MAX_GROUPS);

  for (const g of groups.slice(0, MAX_GROUPS)) {
    let res;
    try {
      res = (await getJSON(`${BASE}/${MTG_CATEGORY}/${g.groupId}/prices`)).results || [];
    } catch (e) {
      console.error(`[tcg-prices] group ${g.groupId} (${g.name}) failed: ${e.message}`);
      done++; continue;
    }
    for (const p of res) {
      if (p.subTypeName !== "Normal") continue;          // non-foil only
      const mid = Number(p.midPrice);
      if (!mid || mid <= 0) { skipped++; continue; }      // 0 = no data: omit, never guess
      // bare mid (cents), keep the lower if a productId somehow recurs
      const r = round(mid);
      const prev = prices[p.productId];
      if (prev === undefined || r < prev) prices[p.productId] = r;
      kept++;
    }
    done++;
    if (done % 25 === 0 || done === total)
      console.error(`[tcg-prices] ${done}/${total} groups · ${Object.keys(prices).length} products`);
    await SLEEP(80); // courtesy throttle
  }

  const out = {
    generatedAt: new Date().toISOString(), // real finish time, never guessed
    source: "tcgcsv.com (TCGplayer category 1 / Magic), subType=Normal",
    note: "value = TCGplayer Mid USD (median current NM/LP listing), 2dp. No-Mid products omitted (page flags, never guesses). Key = TCGplayer productId == Scryfall tcgplayer_id.",
    groups: done,
    productCount: Object.keys(prices).length,
    prices,
  };
  await mkdir(dirname(OUT), { recursive: true });
  await writeFile(OUT, JSON.stringify(out));
  // tiny meta file so the page can show "prices last updated" without
  // downloading the full ~1 MB snapshot (e.g. when using TCG Market mode)
  await writeFile(META, JSON.stringify({
    generatedAt: out.generatedAt,
    source: out.source,
    productCount: out.productCount,
  }));
  const bytes = Buffer.byteLength(JSON.stringify(out));
  console.error(`[tcg-prices] wrote ${OUT}`);
  console.error(`[tcg-prices] ${out.productCount} products · kept ${kept} · skipped(no-mid) ${skipped} · ${(bytes/1048576).toFixed(2)} MB raw`);
}

main().catch(e => { console.error("[tcg-prices] FATAL", e); process.exit(1); });
