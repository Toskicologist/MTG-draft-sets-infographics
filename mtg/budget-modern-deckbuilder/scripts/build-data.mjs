#!/usr/bin/env node
/**
 * build-data.mjs  (v1.0.0)
 *
 * Builds the two data files the deckbuilder fetches from the jsDelivr CDN
 * (orphan `price-data` branch), so Mid mode needs ZERO Scryfall calls:
 *
 *   tcg-prices.json   { productId -> Mid USD }            (TCGcsv, ~daily)
 *   cards-index.json  { lowercased name -> {p,l,i} }      (Scryfall bulk)
 *       p = [[tcgplayer_id, setCode, collectorNo], ...]   paper EN printings
 *       l = legality string, 1 char/format in FMT order   l/n/b/r/-
 *       i = a Scryfall card id  -> image via API redirect
 *   data-meta.json    { generatedAt, counts, sizes }      (banner + freshness)
 *
 * Scryfall `default_cards` is a single ~514 MB JSON array; we stream it with
 * a dependency-free, string/escape-aware brace scanner (bounded RAM).
 *
 * Usage:
 *   node scripts/build-data.mjs                 # prices + index (download bulk)
 *   node scripts/build-data.mjs --no-prices     # index only
 *   node scripts/build-data.mjs --sample f.json # use a local card-array file
 *                                                 instead of the 514MB bulk
 * Out: data/tcg-prices.json, data/cards-index.json, data/data-meta.json
 *
 * Never substitutes data: products with no Mid are omitted; the page flags
 * them rather than guessing.
 */
import { writeFile, mkdir, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const DATA = join(ROOT, "data");
const SLEEP = ms => new Promise(r => setTimeout(r, ms));
const argv = process.argv.slice(2);
const has = f => argv.includes(f);
const opt = f => { const i = argv.indexOf(f); return i > -1 ? argv[i + 1] : null; };

// Formats the page offers a legality toggle for (order is the `l` string order)
const FMT = ["standard","pioneer","modern","legacy","vintage","pauper","premodern","commander"];
const LEG = { legal:"l", not_legal:"n", banned:"b", restricted:"r" };

const round = n => Math.round(n * 100) / 100;

/* ---- TCGcsv prices (unchanged logic) ------------------------------- */
async function getJSON(url, tries = 3) {
  for (let i = 1; i <= tries; i++) {
    try {
      const r = await fetch(url, { headers: {
        Accept: "application/json",
        "User-Agent": "budget-modern-deckbuilder/2 (+github-pages static price snapshot)",
      } });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      if (j && j.success === false) throw new Error(`API error: ${JSON.stringify(j.errors)}`);
      return j;
    } catch (e) { if (i === tries) throw e; await SLEEP(500 * i); }
  }
}
async function buildPrices() {
  const groups = (await getJSON("https://tcgcsv.com/tcgplayer/1/groups")).results || [];
  console.error(`[prices] ${groups.length} Magic groups`);
  const prices = Object.create(null);
  let kept = 0, done = 0;
  for (const g of groups) {
    let res;
    try { res = (await getJSON(`https://tcgcsv.com/tcgplayer/1/${g.groupId}/prices`)).results || []; }
    catch (e) { console.error(`[prices] group ${g.groupId} failed: ${e.message}`); done++; continue; }
    for (const p of res) {
      if (p.subTypeName !== "Normal") continue;
      const mid = Number(p.midPrice);
      if (!mid || mid <= 0) continue;            // no Mid: omit, never guess
      const r = round(mid), prev = prices[p.productId];
      if (prev === undefined || r < prev) prices[p.productId] = r;
      kept++;
    }
    if (++done % 50 === 0 || done === groups.length)
      console.error(`[prices] ${done}/${groups.length} · ${Object.keys(prices).length} products`);
    await SLEEP(80);
  }
  console.error(`[prices] kept ${kept}`);
  return prices;
}

/* ---- streaming splitter for the Scryfall bulk JSON array ----------- */
// Emits each top-level object's text. String/escape/bracket aware; the only
// growing state is `buf` (one card object) -> bounded RAM.
function makeSplitter(onObj) {
  let buf = "", depth = 0, inStr = false, esc = false;
  return chunk => {
    for (let i = 0; i < chunk.length; i++) {
      const ch = chunk[i];
      if (depth === 0) { if (ch === "{") { depth = 1; buf = "{"; inStr = false; esc = false; } continue; }
      buf += ch;
      if (inStr) {
        if (esc) esc = false;
        else if (ch === "\\") esc = true;
        else if (ch === '"') inStr = false;
      } else if (ch === '"') inStr = true;
      else if (ch === "{" || ch === "[") depth++;
      else if (ch === "}" || ch === "]") { if (--depth === 0) { onObj(buf); buf = ""; } }
    }
  };
}

function legString(legalities) {
  let s = "";
  for (const f of FMT) s += LEG[(legalities && legalities[f])] || "-";
  return s;
}

/* ---- build the slim card index ------------------------------------- */
async function buildIndex() {
  const cards = Object.create(null);
  let scanned = 0, printings = 0;

  const handle = txt => {
    scanned++;
    let c; try { c = JSON.parse(txt); } catch { return; }
    if (c.object !== "card" || c.lang !== "en") return;
    if (!Array.isArray(c.games) || !c.games.includes("paper")) return;
    if (typeof c.tcgplayer_id !== "number") return;
    if (c.set_type === "token" || c.set_type === "memorabilia" || c.set_type === "minigame") return;

    const key = String(c.name || "").toLowerCase();
    if (!key) return;
    let e = cards[key];
    if (!e) {
      e = cards[key] = { p: [], l: legString(c.legalities), i: c.id };
      // alias the front-face name for DFC / split / adventure ("A // B")
      const slash = key.indexOf(" // ");
      if (slash > 0) { const front = key.slice(0, slash); if (!cards[front]) cards[front] = e; }
    }
    if (!e.p.some(x => x[0] === c.tcgplayer_id)) {
      e.p.push([c.tcgplayer_id, (c.set || "").toLowerCase(), c.collector_number || ""]);
      printings++;
    }
    if (scanned % 50000 === 0) console.error(`[index] scanned ${scanned} · ${Object.keys(cards).length} names`);
  };

  const split = makeSplitter(handle);
  const sample = opt("--sample");
  if (sample) {
    console.error(`[index] sample file ${sample}`);
    split(await readFile(sample, "utf8"));
  } else {
    const bd = (await getJSON("https://api.scryfall.com/bulk-data")).data
      .find(b => b.type === "default_cards");
    console.error(`[index] downloading default_cards (~${(bd.size/1048576).toFixed(0)} MB)…`);
    const r = await fetch(bd.download_uri, { headers: { "User-Agent": "budget-modern-deckbuilder/2" } });
    if (!r.ok || !r.body) throw new Error("bulk download HTTP " + r.status);
    const dec = new TextDecoder();
    for await (const chunk of r.body) split(dec.decode(chunk, { stream: true }));
  }
  console.error(`[index] done: ${Object.keys(cards).length} names · ${printings} printings · ${scanned} scanned`);
  return cards;
}

async function readJSON(p){ try { return JSON.parse(await readFile(p, "utf8")); } catch { return null; } }

/* ---- main ----------------------------------------------------------
   --no-prices : skip the TCGcsv price rebuild (index only)
   --no-index  : skip the heavy Scryfall index rebuild AND carry forward an
                 existing data/cards-index.json (the workflow restores the
                 prior one from the price-data branch). The card index only
                 changes on set releases / B&R, so it is rebuilt monthly /
                 on demand, while prices rebuild daily. If no prior index is
                 present (first run), it is built regardless.            */
async function main() {
  await mkdir(DATA, { recursive: true });
  const now = new Date().toISOString();          // price build time
  const idxPath = join(DATA, "cards-index.json");
  const meta = { generatedAt: now, fmt: FMT };

  if (!has("--no-prices")) {
    const prices = await buildPrices();
    const out = { generatedAt: now, source: "tcgcsv.com TCGplayer cat 1, subType=Normal, Mid USD", prices };
    await writeFile(join(DATA, "tcg-prices.json"), JSON.stringify(out));
    meta.priceCount = Object.keys(prices).length;
    meta.pricesBytes = Buffer.byteLength(JSON.stringify(out));
  }

  const carried = has("--no-index") ? await readJSON(idxPath) : null;
  if (carried && carried.cards) {
    // Reuse the existing index untouched (daily price-only run).
    meta.cardCount = Object.keys(carried.cards).length;
    meta.indexGeneratedAt = carried.generatedAt || null;
    meta.indexBytes = Buffer.byteLength(JSON.stringify(carried));
    console.error(`[index] carried forward (built ${meta.indexGeneratedAt}) · ${meta.cardCount} names`);
  } else {
    if (has("--no-index")) console.error("[index] --no-index but no prior index found -> building anyway");
    const cards = await buildIndex();
    const idx = { generatedAt: now, source: "Scryfall default_cards (EN paper)", fmt: FMT, cards };
    await writeFile(idxPath, JSON.stringify(idx));
    meta.cardCount = Object.keys(cards).length;
    meta.indexGeneratedAt = now;
    meta.indexBytes = Buffer.byteLength(JSON.stringify(idx));
  }

  await writeFile(join(DATA, "data-meta.json"), JSON.stringify(meta));
  console.error(`[meta] ${JSON.stringify({
    priceGeneratedAt: meta.generatedAt, indexGeneratedAt: meta.indexGeneratedAt,
    cardCount: meta.cardCount, priceCount: meta.priceCount,
    indexMB: meta.indexBytes && (meta.indexBytes/1048576).toFixed(2),
    pricesMB: meta.pricesBytes && (meta.pricesBytes/1048576).toFixed(2) })}`);
}
main().catch(e => { console.error("[build-data] FATAL", e); process.exit(1); });
