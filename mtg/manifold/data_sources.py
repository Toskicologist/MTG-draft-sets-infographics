"""Read-only data sources for the Manifold bot: 17Lands (set detection, card GIH WR, deck color
win rates) and Scryfall (set names, card names used to repair 17Lands' mangled characters).

17Lands rules kept here (see README, 'What 17Lands allows'):
  - a handful of requests per run, paced, with backoff; HTTP 403 is their rate block, so back off
    in minutes, not seconds
  - GIH WR is null under 500 games in hand - those cards are skipped, never estimated
  - /api/card_data ignores start_date/end_date; only the site's time_period values
    (ALL_TIME, FIRST_WEEK, ...) select a window. /color_ratings/data takes time_period too.
  - /color_ratings/data returns a bare list with no win-rate field: win rate = wins / games
  - names can carry a mangled character (TMT's 'Bespoke Bo' arrived as a literal '?'), so every
    name goes through repair_name() against the set's Scryfall list. Accented names that print as
    a replacement character in a Windows console (HOB's Fili) are usually fine - check with ascii()
"""
import datetime, difflib, json, re, time, unicodedata, urllib.error, urllib.parse, urllib.request

L17 = 'https://www.17lands.com'
SCRYFALL = 'https://api.scryfall.com'
PAIRS = ['WU', 'UB', 'BR', 'RG', 'GW', 'WB', 'UR', 'BG', 'RW', 'GU']      # guild display order
GUILDS = {'WU': 'Azorius', 'UB': 'Dimir', 'BR': 'Rakdos', 'RG': 'Gruul', 'GW': 'Selesnya',
          'WB': 'Orzhov', 'UR': 'Izzet', 'BG': 'Golgari', 'RW': 'Boros', 'GU': 'Simic'}
TIME_PERIOD_LABELS = {'ALL_TIME': 'All Time', 'FIRST_WEEK': 'First Week', 'LAST_WEEK': 'Last Week',
                      'LAST_TWO_WEEKS': 'Last Two Weeks', 'ALL_EXCEPT_FIRST_WEEK': 'All Except First Week'}


def pair_key(colors):
    """'WG' / 'GW' / 'gw' -> 'GW' (guild display order); None if not one of the ten pairs."""
    s = set(colors.upper())
    return next((p for p in PAIRS if set(p) == s), None)


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


def parse_time(s):
    return datetime.datetime.fromisoformat(s.replace('Z', '+00:00'))


class Http:
    def __init__(self, user_agent, pace=1.5):
        self.ua, self.pace, self.last, self.blocked = user_agent, pace, 0.0, set()

    def get_json(self, url, tries=4):
        """GET JSON; None on 404. A rate block (403/429) waits 1, 2, then 3 minutes - about 6 in
        all, well inside the GitHub job's 20 - and if it outlasts that, the host is skipped for the
        rest of the run instead of waiting again per URL. The next scheduled run retries."""
        host = urllib.parse.urlsplit(url).netloc
        if host in self.blocked:
            raise RuntimeError(f'{host} rate-blocked earlier this run - skipping {url}')
        limited = False
        for attempt in range(tries):
            wait = self.last + self.pace - time.time()
            if wait > 0:
                time.sleep(wait)
            try:
                req = urllib.request.Request(url, headers={'User-Agent': self.ua, 'Accept': 'application/json'})
                with urllib.request.urlopen(req, timeout=90) as r:
                    self.last = time.time()
                    return json.loads(r.read().decode('utf-8'))
            except urllib.error.HTTPError as e:
                self.last = time.time()
                if e.code == 404:
                    return None
                limited = e.code in (403, 429)
                backoff = min(60 * (attempt + 1), 180) if limited else 5 * (attempt + 1)
                print(f'    retry {attempt + 1}/{tries}: HTTP {e.code} on {url[:90]}, waiting {backoff}s')
            except Exception as e:                   # 17Lands drops TLS handshakes under bursts
                self.last = time.time()
                limited, backoff = False, 5 * (attempt + 1)
                print(f'    retry {attempt + 1}/{tries}: {e!r}'[:120])
            if attempt + 1 < tries:
                time.sleep(backoff)
        if limited:
            self.blocked.add(host)
        raise RuntimeError(f'failed after {tries} tries: {url}')


# ---------------------------------------------------------------- set detection

def detect_sets(http, event_type, set_types, now=None):
    """Sets 17Lands tracks for event_type, newest 17Lands start date first, each checked against
    Scryfall's set_type. Returns [{code, name, start, set_type}]. Only the newest few are checked on
    Scryfall so a run costs a handful of requests, not one per historical set."""
    now = now or utcnow()
    f = http.get_json(f'{L17}/data/filters')
    fbe, starts = f['formats_by_expansion'], f['start_dates']
    cands = []
    for code in f['expansions']:
        if not re.fullmatch(r'[A-Z0-9]{3}', code or '') or event_type not in fbe.get(code, []):
            continue
        if code not in starts:
            continue
        start = parse_time(starts[code])
        if start <= now:
            cands.append((start, code))
    out = []
    for start, code in sorted(cands, reverse=True)[:4]:
        s = http.get_json(f'{SCRYFALL}/sets/{code.lower()}')
        if s and s.get('set_type') in set_types:
            out.append({'code': code, 'name': s['name'], 'start': start, 'set_type': s['set_type']})
    return out


def set_info(http, code, event_type):
    """One set by code (for --set): 17Lands start date + Scryfall name."""
    f = http.get_json(f'{L17}/data/filters')
    if code not in f['start_dates'] or event_type not in f['formats_by_expansion'].get(code, []):
        raise SystemExit(f'17Lands has no {event_type} for {code}')
    s = http.get_json(f'{SCRYFALL}/sets/{code.lower()}') or {}
    return {'code': code, 'name': s.get('name', code), 'start': parse_time(f['start_dates'][code]),
            'set_type': s.get('set_type')}


# ---------------------------------------------------------------- 17Lands data

def card_ranking(http, code, event_type, time_period, min_gih=500):
    """Cards with a GIH WR, best first. Returns (ranked, total_gih, raw_rows).
    ranked = [{name, rarity, gih_wr (0-1, unrounded), gih}]"""
    q = urllib.parse.urlencode({'expansion': code, 'event_type': event_type, 'time_period': time_period})
    payload = http.get_json(f'{L17}/api/card_data?{q}') or {}
    rows = (payload.get('data') if isinstance(payload, dict) else payload) or []
    total = sum(r.get('ever_drawn_game_count') or 0 for r in rows)
    ranked = [{'name': r['name'], 'rarity': r.get('rarity'), 'gih_wr': r['ever_drawn_win_rate'],
               'gih': r['ever_drawn_game_count']}
              for r in rows
              if r.get('ever_drawn_win_rate') is not None and (r.get('ever_drawn_game_count') or 0) >= min_gih]
    ranked.sort(key=lambda r: (-r['gih_wr'], -r['gih']))
    return ranked, total, rows


def pair_ranking(http, code, event_type, time_period, combine_splash=True, min_games=1000):
    """The ten two-color decks, best win rate first. Returns (ranked, all_games, raw_rows).
    ranked = [{pair, games, wins, win_rate (0-1)}]; pairs under min_games are dropped."""
    q = urllib.parse.urlencode({'expansion': code, 'event_type': event_type, 'time_period': time_period,
                                'combine_splash': str(combine_splash).lower()})
    rows = http.get_json(f'{L17}/color_ratings/data?{q}') or []
    alls = [r for r in rows if r.get('is_summary') and r.get('short_name') == 'All']
    total = alls[0]['games'] if alls else 0
    ranked = []
    for r in rows:
        if r.get('is_summary') or not isinstance(r.get('short_name'), str) or len(r['short_name']) != 2:
            continue
        p = pair_key(r['short_name'])
        if p and r['games'] >= min_games:
            ranked.append({'pair': p, 'games': r['games'], 'wins': r['wins'], 'win_rate': r['wins'] / r['games']})
    ranked.sort(key=lambda r: (-r['win_rate'], -r['games']))
    return ranked, total, rows


def card_data_url(code, event_type, time_period):
    return f'{L17}/card_data?' + urllib.parse.urlencode(
        {'expansion': code, 'format': event_type, 'time_period': time_period})


def deck_color_url(code, event_type, time_period):
    return f'{L17}/deck_color_data?' + urllib.parse.urlencode(
        {'expansion': code, 'format': event_type, 'time_period': time_period})


# ---------------------------------------------------------------- names

def scryfall_names(http, code):
    """Every card name in the set (front faces too), for repairing 17Lands names."""
    names, url = set(), f'{SCRYFALL}/cards/search?' + urllib.parse.urlencode(
        {'q': f'e:{code.lower()}', 'unique': 'cards', 'include_extras': 'true'})
    while url:
        page = http.get_json(url)
        if not page:
            break
        for c in page.get('data', []):
            names.add(c['name'])
            if ' // ' in c['name']:
                names.add(c['name'].split(' // ')[0])
        url = page.get('next_page')
    return names


def scryfall_pool(http, code, rarities):
    """Card names of the given rarities in the set (front face for double-faced cards), sorted -
    the pool a starting answer is drawn from before 17Lands' embargo lifts."""
    clause = ' or '.join(f'r:{r}' for r in sorted(rarities))
    names, url = set(), f'{SCRYFALL}/cards/search?' + urllib.parse.urlencode(
        {'q': f'e:{code.lower()} ({clause}) -t:basic', 'unique': 'cards'})
    while url:
        page = http.get_json(url)
        if not page:
            break
        names.update(c['name'].split(' // ')[0] for c in page.get('data', []))
        url = page.get('next_page')
    return sorted(names)


COLOR_WORDS = {'white': 'W', 'blue': 'U', 'black': 'B', 'red': 'R', 'green': 'G'}
NEGATION = re.compile(r'\b(not|no|non|but|except|without|besides)\b')


def negated(text):
    """True if an answer reads as a negation ('Not UB', 'anything but Rakdos'): it names a pair
    without meaning it, so it is settled by hand rather than read as that pair."""
    return bool(NEGATION.search(text.lower()))


def answer_pair(text, labels):
    """Which of the ten pairs a (possibly trader-written) answer means, or None if it names none
    or several."""
    found = answer_pairs(text, labels)
    return next(iter(found)) if len(found) == 1 else None


def answer_pairs(text, labels):
    """Every pair an answer names. Reads an exact label ('Fatehold (WU)'), a two-letter code in
    any order ('UW'), a guild name ('Azorius'), the set's archetype name ('Fatehold'), or two
    color words ('white-blue'). 'Azorius or Dimir' gives two pairs; 'Esper' gives none, and so
    does a negation ('Not UB' - see negated())."""
    t, low = text.strip(), text.lower()
    for p, label in labels.items():
        if norm(t) == norm(label):
            return {p}
    if negated(t):
        return set()
    found = set()
    for code in re.findall(r'(?<![A-Za-z])([WUBRGwubrg]{2})(?![A-Za-z])', t):
        if code.isupper() or code.islower():
            found.add(pair_key(code))
    for p in PAIRS:
        title = labels.get(p, '').rsplit(' (', 1)[0].lower()
        if re.search(rf'\b{re.escape(GUILDS[p].lower())}\b', low) or (title and re.search(rf'\b{re.escape(title)}\b', low)):
            found.add(p)
    words = {c for w, c in COLOR_WORDS.items() if re.search(rf'\b{w}\b', low)}
    if len(words) == 2:
        found.add(pair_key(''.join(words)))
    found.discard(None)
    return found


def norm(s):
    """Lower-case letters/digits only, accents stripped; a mangled character becomes '?'."""
    s = s.replace('�', '?')
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r'[^a-z0-9?]', '', s)


def names_match(a, b):
    """True if two card names are the same card; '?' in either is a one-character wildcard,
    and a double-faced name matches its front face. For repairing 17Lands names against
    Scryfall's only - never for trader-written answers (see same_card)."""
    na, nb = norm(a), norm(b)
    fa, fb = norm(a.split(' // ')[0]), norm(b.split(' // ')[0])
    for x, y in ((na, nb), (fa, fb), (na, fb), (fa, nb)):
        if x == y:
            return True
        if '?' in x or '?' in y:
            pat_src, target = (x, y) if '?' in x else (y, x)
            if re.fullmatch(re.escape(pat_src).replace(r'\?', '.'), target):
                return True
    return False


def repair_name(name, set_names):
    """17Lands name -> Scryfall spelling when exactly one set card matches; else unchanged."""
    if name in set_names:
        return name
    hits = {n for n in set_names if ' // ' not in n and names_match(name, n)}
    return hits.pop() if len(hits) == 1 else name


def same_card(winner, answer):
    """True if a trader's answer names the winning card: the same letters and digits once case,
    accents, punctuation and spacing are ignored, either name taken whole or as its front face.
    No wildcards: an answer containing '?' or a replacement character never matches, so a row
    of question marks can't claim whichever card has that many letters."""
    if '?' in answer or '�' in answer:
        return False
    w = {norm(winner), norm(winner.split(' // ')[0])}
    a = {norm(answer), norm(answer.split(' // ')[0])} - {''}
    return bool(w & a)


def near_miss(name, texts, cutoff=0.8):
    """Answer texts that look like `name` without matching it (a trader's typo)."""
    n = norm(name)
    return [t for t in texts if not same_card(name, t)
            and difflib.SequenceMatcher(None, n, norm(t)).ratio() >= cutoff]


def safe(text, limit=80):
    """Trader-written text cut down to printable ASCII on one line, for logs and for the state
    file the GitHub job commits publicly."""
    t = unicodedata.normalize('NFKD', str(text))
    t = ' '.join(''.join(c for c in t if 32 <= ord(c) < 127).split())
    return t[:limit] + ('...' if len(t) > limit else '')
