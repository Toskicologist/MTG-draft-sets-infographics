"""Manifold Markets bot: opens and resolves 17Lands markets for the newest MTG set.

For the newest set 17Lands tracks, each checkpoint in config.json lists the markets it runs, in
priority order (checkpoint 'kinds'): top card, top common, top rare/mythic (GIH WR) and top color
pair (win rate, all ten pairs listed). Wording is in config.json markets.<kind>.question. Card
markets start with one answer plus Other: the current 17Lands leader once the embargo has passed,
before that a random pick. A 'sequential' checkpoint opens a market only once every market before
it in the list is open; 'open_until' stops new markets opening after that time.
The bot never adds answers to a market after creating it (each added answer costs mana); traders
add their own. Every run it
  1. adopts markets it already made (always) and opens new ones the opening rules allow. Market
     ids are fixed (a hash of bot, set, checkpoint and kind), but anyone can create a market at
     an id, so only a market whose creator is this bot is ever adopted; if someone else took the
     id first, the bot finds its own by question or creates one at a random id
  2. resolves markets whose resolve time has passed, from a fresh 17Lands read, posts the top 3
     as a comment and saves the raw data under state/snapshots/. Trader answers must spell the
     winner exactly (case, accents and punctuation aside); if several do, the earliest-added one
     wins. Anything it can't settle unambiguously (winner missing but a near-miss answer exists,
     no data a week late) is left unresolved and written to state/NEEDS_REVIEW.txt; once the
     owner resolves it by hand on Manifold, the next run records that.
One market failing (an API error, a 17Lands outage) is logged and skipped; the rest still run
and the run exits 1 at the end.

Dry run is the default: nothing is written to Manifold or to state/ without --live.

Usage (from the repository root):
  python mtg/manifold/bot.py plan                 what a run would do now
  python mtg/manifold/bot.py run --live           do it
  python mtg/manifold/bot.py status               markets recorded in state/markets.json
Options:
  --set HOB      use this 17Lands code instead of detecting the newest set
  --now ISO      pretend it is this UTC time (dry runs only)
  --rehearse     dry runs only: treat every checkpoint's markets as already open, so --now past
                 a resolve time shows the resolution the bot would make
  --no-key       dry runs only: don't load the API key (public reads only)
  --fail-on-review  exit 3 when a market needs review (GitHub Actions then emails the owner)
Question wording comes from config.json markets.<kind>.question.
"""
import argparse, datetime, json, random, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data_sources import (GUILDS, PAIRS, TIME_PERIOD_LABELS, Http, answer_pair, answer_pairs,  # noqa: E402
                          card_data_url, card_ranking, deck_color_url, detect_sets, near_miss, negated,
                          pair_ranking, parse_time, repair_name, safe, same_card, scryfall_names,
                          scryfall_pool, set_info, utcnow)
from manifold_api import (ANSWER_COST_BY_TIER, Manifold, ManifoldError, idempotency_key,  # noqa: E402
                          load_api_key, market_cost)

HERE = Path(__file__).resolve().parent
STATE = HERE / 'state'
STATE_FILE = STATE / 'markets.json'
REVIEW_FILE = STATE / 'NEEDS_REVIEW.txt'
ARCHETYPES = HERE.parent / 'color-wheel-project' / 'archetypes.json'
CARD_KINDS = ('top_card', 'top_common', 'top_rare')     # GIH WR markets; config 'rarities' filters
DAY = datetime.timedelta(days=1)
HOUR = datetime.timedelta(hours=1)


def iso(t):
    return t.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def ms(t):
    return int(t.timestamp() * 1000)


def pretty(t):
    return t.astimezone(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')


class Bot:
    def __init__(self, cfg, live, now, rehearse=False, no_key=False):
        self.cfg, self.live, self.now, self.rehearse = cfg, live, now, rehearse
        self.mcfg, self.lcfg = cfg['manifold'], cfg['seventeen_lands']
        self.event = self.lcfg['event_type']
        self.http = Http(self.lcfg['user_agent'], self.lcfg['pace_seconds'])
        key = None if no_key else load_api_key(self.mcfg['api_key_env'], self.mcfg['api_key_file'])
        self.mf = Manifold(self.mcfg['api_base'], key, self.lcfg['user_agent'])
        self.tier = self.mcfg['liquidity_tier']
        self.state = json.loads(STATE_FILE.read_text(encoding='utf-8')) if STATE_FILE.exists() else {'sets': {}}
        self._me, self._names, self._groups, self._own = None, {}, None, None
        self.spend, self.reviews, self.errors = 0, [], []

    # ------------------------------------------------------------ plumbing

    def log(self, msg):
        line = f'[{iso(self.now)}] {"" if self.live else "(dry) "}{msg}'
        print(line)
        if self.live:
            STATE.mkdir(exist_ok=True)
            with open(STATE / 'bot.log', 'a', encoding='utf-8') as f:
                f.write(line + '\n')

    def save(self):
        if not self.live:
            return
        STATE.mkdir(exist_ok=True)
        tmp = STATE_FILE.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.state, indent=1, ensure_ascii=False), encoding='utf-8')
        tmp.replace(STATE_FILE)

    def review(self, entry, reason):
        self.log(f'NEEDS REVIEW - {entry.get("question")}: {reason}')
        self.reviews.append(f'{entry.get("url") or entry.get("question")}\n  {reason}')
        if self.live:
            entry['needs_review'] = reason
            self.save()

    def error(self, where, e):
        msg = safe(f'{type(e).__name__}: {e}', 300)
        self.log(f'ERROR {where}: {msg} - skipped; the other markets carry on')
        self.errors.append(f'{where}: {msg}')

    def me(self):
        if self._me is None and self.mf.key:
            self._me = self.mf.me()
        return self._me

    def balance(self):
        m = self.me()
        return None if m is None else m.get('balance')

    def set_names(self, code):
        if code not in self._names:
            self._names[code] = scryfall_names(self.http, code)
        return self._names[code]

    def rarities(self, kind):
        r = self.cfg['markets'][kind].get('rarities')
        return set(r) if r else None

    def noun(self, kind):
        return self.cfg['markets'][kind].get('noun', 'card')

    def ranked_cards(self, code, kind, tp):
        """card_ranking, keeping only the market's rarities (17Lands' own rarity column)."""
        ranked, total, raw = card_ranking(self.http, code, self.event, tp, self.lcfg['min_gih'])
        rar = self.rarities(kind)
        if rar:
            ranked = [r for r in ranked if r.get('rarity') in rar]
        return ranked, total, raw

    def group_ids(self):
        if self._groups is None:
            self._groups = []
            for slug in self.mcfg.get('group_slugs', []):
                try:
                    self._groups.append(self.mf.group(slug)['id'])
                except (ManifoldError, KeyError, TypeError) as e:
                    self.log(f'topic "{slug}" not found ({e}); markets will not be tagged with it')
        return self._groups

    # ------------------------------------------------------------ market text

    def pair_labels(self, code):
        """pair -> answer text: the set's archetype name from the color wheel when it has one.
        Saved in the set's state, because archetypes.json isn't published - the GitHub Actions copy
        reads the names from state so its answers match the ones made locally."""
        saved = self.state['sets'].get(code, {}).get('pair_labels')
        if saved:
            return saved
        titles = {}
        if ARCHETYPES.exists():
            for s in json.loads(ARCHETYPES.read_text(encoding='utf-8'))['sets']:
                if s['code'] == code.lower():
                    titles = {p: ' '.join((v.get('title') or '').split()) for p, v in s['pairs'].items()}
        out = {}
        for p in PAIRS:
            t = titles.get(p)
            out[p] = f'{t} ({p})' if t and t != GUILDS[p] else f'{GUILDS[p]} ({p})'
        if self.live and code in self.state['sets']:
            self.state['sets'][code]['pair_labels'] = out
        return out

    def question(self, s, cp, kind):
        """config markets.<kind>.question with {set} and {label}; a checkpoint label may use {date},
        the day the data is read, US style (e.g. 'on {date}' -> 'on October 13, 2026')."""
        resolve = s['start'] + cp['resolve_day'] * DAY
        label = cp['label'].format(date=f'{resolve:%B} {resolve.day}, {resolve.year}')   # American format
        for name in (s['name'], s['code']):
            q = self.cfg['markets'][kind]['question'].format(set=name, label=label)
            if len(q) <= 120:                       # Manifold's MAX_QUESTION_LENGTH
                return q
        return q[:120]

    def seed_answers(self, s, cp, kind, mkey):
        """The answers a new market starts with: the current 17Lands leader(s) once the embargo has
        passed, otherwise a random pick (pairs from the ten, cards from the set's rares and mythics).
        Seeded by set + market so a dry run and the live run pick the same."""
        n = self.cfg['markets'][kind].get('seed_answers', 1)
        if not n:
            return [], ''
        rng = random.Random(f'{s["code"]}:{mkey}')
        open_data = self.now >= s['start'] + self.lcfg['embargo_days'] * DAY
        if kind == 'top_pair':
            labels = self.pair_labels(s['code'])
            if open_data:
                ranked, total, _ = pair_ranking(self.http, s['code'], self.event, cp['time_period'],
                                                self.lcfg['combine_splash'], self.lcfg['min_pair_games'])
                if total >= self.lcfg['min_total_games'] and ranked:
                    return [labels[r['pair']] for r in ranked[:n]], 'the current 17Lands leader'
            return [labels[p] for p in rng.sample(PAIRS, n)], 'picked at random'
        if open_data:
            ranked, total, _ = self.ranked_cards(s['code'], kind, cp['time_period'])
            if total >= self.lcfg['min_total_gih'] and ranked:
                names = self.set_names(s['code'])
                return [repair_name(r['name'], names) for r in ranked[:n]], 'the current 17Lands leader'
        rar = self.rarities(kind) or {'rare', 'mythic'}       # all-cards market: draw from the bombs
        pool = scryfall_pool(self.http, s['code'], rar)
        what = 'common' if rar == {'common'} else 'rare or mythic' if rar <= {'rare', 'mythic'} else 'card'
        return (rng.sample(pool, min(n, len(pool))), f'a random {what}') if pool else ([], '')

    def description(self, s, cp, kind, close, resolve, seed_how='', independent=False):
        tp, code = cp['time_period'], s['code']
        ev = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', self.event)       # PremierDraft -> Premier Draft
        tp_label = TIME_PERIOD_LABELS.get(tp, tp)
        human = self.mcfg['human_username']
        seed = ''
        if seed_how:
            seed = (f'- The market starts with one answer, {seed_how}' +
                    (' (17Lands asks tools not to re-show a new set\'s data before its 12th day on Arena, '
                     'so nothing is read from it before then).\n' if seed_how.startswith(('picked', 'a random'))
                     else '.\n'))
        if tp == 'ALL_TIME':
            when = (f'**All Time** as 17Lands shows it when the bot reads it, at its first run after '
                    f'{pretty(resolve)} (normally within a day).')
        else:
            when = (f'**{tp_label}** - a fixed window on 17Lands, read by the bot at its first run after '
                    f'{pretty(resolve)} so late-processed games are in.')
        if kind in CARD_KINDS:
            url = card_data_url(code, self.event, tp)
            noun, rar = self.noun(kind), self.rarities(kind)
            rarity_rule = ''
            if rar == {'common'}:
                rarity_rule = '- Only commons count, by the rarity 17Lands lists for each card.\n'
            elif rar == {'rare', 'mythic'}:
                rarity_rule = '- Only rares and mythic rares count, by the rarity 17Lands lists for each card.\n'
            elif rar:
                rarity_rule = f'- Only these rarities count: {", ".join(sorted(rar))}.\n'
            rules = (
                f'Resolves to the {noun} with the highest **Games in Hand Win Rate (GIH WR)** on the '
                f'[17Lands card data page for {s["name"]}]({url}):\n\n'
                f'- Format: **{ev}**, all users, all deck colors\n'
                f'- Time period: {when}\n' + rarity_rule +
                f'- Only cards 17Lands shows a GIH WR for count (it hides it under '
                f'{self.lcfg["min_gih"]} games in hand).\n'
                f'- A tie on 17Lands\' unrounded figure splits the market equally between the tied cards.\n'
                f'- Anyone can add a {noun} as an answer until close. An answer counts if it spells '
                f'the card\'s name (case, accents and punctuation don\'t matter); if several answers '
                f'name the winner, the earliest-added one wins. If the winner isn\'t an answer, '
                f'this resolves **Other**.\n' + seed)
        elif independent:
            url = deck_color_url(code, self.event, tp)
            rules = (
                f'Each answer is its own yes/no question: **is this the two-color deck with the highest win '
                f'rate (wins / games)** on the [17Lands deck color data page for {s["name"]}]({url})?\n\n'
                f'- Format: **{ev}**, all users; splashes counted in their main pair (17Lands\' default, '
                f'"separate splashes" unticked)\n'
                f'- Time period: {when}\n'
                f'- Only the ten two-color pairs count; pairs with fewer than '
                f'{self.lcfg["min_pair_games"]:,} games are skipped.\n'
                f'- Anyone can add a pair as an answer until close - name it with its colors, e.g. '
                f'"{self.pair_labels(code)["WU"]}".\n'
                f'- There is no "Other" answer. At resolution, every answer naming the top pair resolves '
                f'**YES** and every other answer **NO**; if no answer names it, all resolve NO. An exact tie '
                f'resolves each tied pair YES. An answer that names no two-color pair (a mono-color or '
                f'three-color deck, say) resolves NO; one naming several pairs is settled by hand.\n'
                + seed)
        else:
            url = deck_color_url(code, self.event, tp)
            rules = (
                f'Resolves to the two-color deck with the highest win rate (wins / games) on the '
                f'[17Lands deck color data page for {s["name"]}]({url}):\n\n'
                f'- Format: **{ev}**, all users; splashes counted in their main pair (17Lands\' default, '
                f'"separate splashes" unticked)\n'
                f'- Time period: {when}\n'
                f'- Only the ten two-color pairs count; pairs with fewer than '
                f'{self.lcfg["min_pair_games"]:,} games are skipped.\n'
                f'- An exact tie splits the market equally.\n'
                + (f'- Anyone can add a pair as an answer until close - include its colors, e.g. '
                   f'"{self.pair_labels(code)["WU"]}". If several answers name the winner, the '
                   f'earliest-added one wins. If the winner isn\'t an answer, this resolves **Other**.\n'
                   if self.cfg['markets']['top_pair'].get('add_answers_mode', 'DISABLED') != 'DISABLED' else '')
                + seed)
        return (
            f'## Resolution criteria\n\n{rules}'
            f'- If 17Lands publishes no {ev} data for {code}, this resolves N/A.\n\n'
            f'Trading closes {pretty(close)}.' + (f' {cp["note"]}' if cp.get('note') else '') + '\n\n'
            f'## About\n\n'
            f'Created and resolved automatically by a bot{f" run by @{human}" if human else ""}. '
            f'Data from [17Lands](https://www.17lands.com) - this market is not affiliated with or '
            f'endorsed by 17Lands. {s["name"]} opened on 17Lands on {pretty(s["start"])}.\n'
            + (f'\nQuestions, or think it resolved wrongly? Contact {self.mcfg["contact_email"]}.\n'
               if self.mcfg.get('contact_email') else '')
            + (f'\nMore MTG draft set infographics and tools: [{self.mcfg["website"]}]({self.mcfg["website"]})\n'
               if self.mcfg.get('website') else ''))

    # ------------------------------------------------------------ steps

    def ensure_market(self, s, cp, kind, may_open):
        code = s['code']
        sst = self.state['sets'].setdefault(code, {'name': s['name'], 'start': iso(s['start']), 'markets': {}}) \
            if self.live else self.state['sets'].get(code, {'markets': {}})
        mkey = f'{cp["id"]}:{kind}'
        if mkey in sst['markets']:
            return sst['markets'][mkey]
        close, resolve = s['start'] + cp['close_day'] * DAY, s['start'] + cp['resolve_day'] * DAY
        q = self.question(s, cp, kind)
        mcfg = self.cfg['markets'][kind]
        add_mode = mcfg.get('add_answers_mode', 'DISABLED')
        # Independent answers: each answer is its own yes/no market, so traders can add pairs with
        # no catch-all 'Other' (Manifold only adds Other to sum-to-one markets that take new answers).
        independent = kind == 'top_pair' and mcfg.get('independent_answers', False) and add_mode != 'DISABLED'
        phantom = {'id': None, 'url': None, 'question': q, 'kind': kind, 'checkpoint': cp['id'],
                   'time_period': cp['time_period'], 'close': iso(close), 'resolve_after': iso(resolve),
                   'answers': [], 'pair_answers': {}, 'independent': independent}
        if self.rehearse and not self.live:
            return phantom
        labels = self.pair_labels(code)
        mid = None
        if self.live:
            # A market this bot already made (state lost, or made by the other runner) is adopted
            # BEFORE any opening rule - mana, deadlines, sequence - so it can never be orphaned.
            m, mid = self.find_own(code, mkey, idempotency_key(self.me()['id'], code, cp['id'], kind), q)
            if m:
                self.log(f'{code} {mkey}: already on Manifold ({m["url"]}) - recording it')
                return self.record(sst, mkey, phantom, m, labels)
        if not may_open:
            return None
        if self.now > close - self.cfg['min_hours_open'] * HOUR:
            self.log(f'{code} {mkey}: closes {pretty(close)}, under {self.cfg["min_hours_open"]}h away - not opening')
            return None
        if cp.get('open_until') and self.now >= parse_time(cp['open_until']):
            self.log(f'{code} {mkey}: past {cp["open_until"]}, the last time this checkpoint opens markets - '
                     f'not opening')
            return None

        if add_mode == 'DISABLED':                  # fixed list: every pair (cards need adding)
            answers, seed_how = ([labels[p] for p in PAIRS] if kind == 'top_pair' else []), ''
        else:
            answers, seed_how = self.seed_answers(s, cp, kind, mkey)
        has_other = add_mode != 'DISABLED' and not independent
        cost = market_cost('MULTIPLE_CHOICE', len(answers), has_other, self.tier)
        bal = self.balance()
        if bal is not None:
            if bal - self.spend < cost:
                self.log(f'{code} {mkey}: not opening yet - balance M${bal - self.spend:.0f}, needs M${cost}. '
                         f'Retried every run until {pretty(self.open_deadline(cp, close))}.')
                return None
        body = {'outcomeType': 'MULTIPLE_CHOICE', 'question': q,
                'descriptionMarkdown': self.description(s, cp, kind, close, resolve, seed_how, independent),
                'closeTime': ms(close), 'answers': answers, 'addAnswersMode': add_mode,
                'shouldAnswersSumToOne': not independent, 'liquidityTier': self.tier,
                'visibility': self.mcfg['visibility'], 'groupIds': self.group_ids()}
        if independent and answers:                 # each answer's own starting chance, in percent
            body['answerProbs'] = [mcfg.get('seed_prob', 10)] * len(answers)

        if not self.live:
            self.spend += cost
            self.log(f'{code} {mkey}: would open "{q}" - M${cost}, closes {pretty(close)}, '
                     f'resolves after {pretty(resolve)}, answers {answers}{" + Other" if has_other else ""}'
                     f'{f" ({seed_how})" if seed_how else ""}')
            phantom['answers'] = [{'id': None, 'text': a} for a in answers] + \
                ([{'id': None, 'text': 'Other', 'isOther': True}] if has_other else [])
            return phantom

        res = None
        if mid:
            body['idempotencyKey'] = mid
            try:
                res = self.mf.create_market(body)
            except ManifoldError as e:
                if 'already been created' not in e.body:
                    raise
                m = self.wait_for_market(mid)       # taken since find_own looked a moment ago
                if m and m.get('creatorId') == self.me()['id']:
                    self.log(f'{code} {mkey}: the other runner just opened it ({m["url"]}) - recording it')
                    return self.record(sst, mkey, phantom, m, labels)
                self.log(f'{code} {mkey}: someone else just took the fixed id {mid} - using a random id')
                del body['idempotencyKey']
                mid = None
        if not mid:
            res = self.mf.create_market(body)
            mid = res['id']
        # GET /market/<id> 404s for a few seconds after creation (seen 2026-10-01), so retry,
        # and fall back to the create response (a LiteMarket: id + url) rather than crash.
        m = self.wait_for_market(mid) or res
        if not m:
            raise RuntimeError(f'created {mid} but cannot read it back yet - the next run finds it '
                               f'(by fixed id or question) and records it instead of creating another')
        self._me = None
        self.log(f'{code} {mkey}: opened {m["url"]} (M${cost})')
        return self.record(sst, mkey, phantom, m, labels)

    def find_own(self, code, mkey, mid, q):
        """(market, id to create with) for a market slot not in state. The bot's own market at the
        fixed id is adopted. A market there by anyone else is ignored - anyone can create a market
        at any id, and the ids are predictable - and the bot then looks for its own market by exact
        question (one it made at a random id earlier) and, failing that, creates at a random id."""
        me = self.me()['id']
        m = self.mf.market(mid)
        if m and m.get('creatorId') == me:
            return m, mid
        if m:
            self.log(f'{code} {mkey}: the fixed id {mid} belongs to a market by someone else '
                     f'({m.get("url")}) - ignoring it')
            mid = None
        if self._own is None:
            self._own = self.mf.markets_by(me)
        for x in self._own:
            if x.get('question') == q and x.get('creatorId', me) == me:
                return (self.mf.market(x['id']) or x), mid
        return None, mid

    def record(self, sst, mkey, phantom, m, labels):
        entry = dict(phantom, id=m['id'], url=m['url'], created=iso(self.now))
        if entry['kind'] == 'top_pair':
            by_text = {a['text']: a['id'] for a in m.get('answers') or []}
            entry['pair_answers'] = {p: by_text.get(labels[p]) for p in PAIRS}
        del entry['answers']
        sst['markets'][mkey] = entry
        self.save()
        return entry

    def open_deadline(self, cp, close):
        """Last moment a market for this checkpoint may open: min_hours_open before close, or the
        checkpoint's open_until if that is earlier."""
        d = close - self.cfg['min_hours_open'] * HOUR
        return min(d, parse_time(cp['open_until'])) if cp.get('open_until') else d

    def wait_for_market(self, mid, tries=6):
        for attempt in range(tries):
            m = self.mf.market(mid)
            if m:
                return m
            time.sleep(2 * (attempt + 1))
        return None

    def live_answers(self, entry):
        if not entry.get('id'):
            return entry.get('answers', [])
        m = self.mf.market(entry['id'])
        if m and m.get('isResolved'):
            entry['resolution'] = {'outcome': m.get('resolution'), 'by': 'someone else',
                                   'seen': iso(self.now)}
            self.log(f'{entry["question"]}: already resolved on Manifold ({m.get("resolution")}) - recording')
            self.save()
            return None
        return (m or {}).get('answers', [])

    def not_yet(self, entry, msg, late):
        if late:
            self.review(entry, msg + ' a week after the resolve time - the description promises N/A, '
                                     'so resolve it N/A by hand on Manifold')
        else:
            self.log(f'{entry["question"]}: {msg} - waiting')

    @staticmethod
    def earliest(answers):
        """The first-added of several answers naming the same winner (the description's rule)."""
        return min(answers, key=lambda a: (a.get('createdTime') or float('inf'), a.get('index', 0)))

    def resolve(self, entry, s, cp):
        if entry.get('resolution'):
            return
        if entry.get('needs_review'):
            # Left for the owner. Once they resolve it by hand on Manifold, record that, so the
            # set stops being revisited every run.
            if entry.get('id') and self.live_answers(entry) is None:
                entry.setdefault('resolution', {})['review'] = entry['needs_review']
                self.save()
            return
        resolve_at = parse_time(entry['resolve_after'])
        if self.now < resolve_at:
            return
        late = self.now > resolve_at + 7 * DAY
        code, tp = s['code'], cp['time_period']
        answers = self.live_answers(entry)
        if answers is None:
            return

        if entry['kind'] in CARD_KINDS:
            ranked, total, raw = self.ranked_cards(code, entry['kind'], tp)
            if total < self.lcfg['min_total_gih'] or not ranked:
                return self.not_yet(entry, f'only {total:,} games in hand on 17Lands ({tp})', late)
            names = self.set_names(code)
            for r in ranked[:3]:
                r['name'] = repair_name(r['name'], names)
            best = ranked[0]['gih_wr']
            winners = [repair_name(r['name'], names) for r in ranked if r['gih_wr'] == best]
            listed = [a for a in answers if not a.get('isOther')]
            other = [a for a in answers if a.get('isOther')]
            ids, labels = [], []
            for w in winners:
                if '?' in w or '�' in w:       # repair_name found no single Scryfall spelling
                    return self.review(entry, f'17Lands lists the winner as {safe(w)!r}, a mangled name '
                                              f'Scryfall could not repair - settle it by hand')
                hits = [a for a in listed if same_card(w, a['text'])]
                if hits:
                    a = self.earliest(hits)
                    ids.append(a.get('id')); labels.append(safe(a['text']))
                    continue
                near = near_miss(w, [a['text'] for a in listed])
                if near:
                    return self.review(entry, f'winner {w} is not an answer, but these look like it: '
                                              f'{[safe(t) for t in near]}')
                if not other and entry.get('id'):
                    return self.review(entry, f'winner {w} is not an answer and the market has no Other')
                ids.append(other[0]['id'] if other else None); labels.append(f'Other ({w})')
            top3 = '\n'.join(f'{i}. **{r["name"]}** - {100 * r["gih_wr"]:.2f}% GIH WR '
                             f'({r["gih"]:,} games in hand)' for i, r in enumerate(ranked[:3], 1))
            src = card_data_url(code, self.event, tp)
        else:
            ranked, total, raw = pair_ranking(self.http, code, self.event, tp, self.lcfg['combine_splash'],
                                              self.lcfg['min_pair_games'])
            if total < self.lcfg['min_total_games'] or not ranked:
                return self.not_yet(entry, f'only {total:,} games on 17Lands deck colors ({tp})', late)
            best = ranked[0]['win_rate']
            winners = [r['pair'] for r in ranked if r['win_rate'] == best]
            plabels = self.pair_labels(code)
            top3 = '\n'.join(f'{i}. **{plabels[r["pair"]]}** - {100 * r["win_rate"]:.2f}% '
                             f'({r["games"]:,} games)' for i, r in enumerate(ranked[:3], 1))
            src = deck_color_url(code, self.event, tp)
            if entry.get('independent'):
                # Each answer is its own yes/no: YES if it names only winning pair(s), NO if it names
                # none of them (including answers naming no pair at all), by hand if it mixes both.
                bodies, labels = [], []
                for a in answers:
                    if a.get('resolution'):         # already settled by an earlier, interrupted run
                        continue
                    if negated(a['text']) and a['text'] not in plabels.values():
                        return self.review(entry, f'answer {safe(a["text"])!r} reads as a negation - '
                                                  f'settle it by hand')
                    named = answer_pairs(a['text'], plabels)
                    if named & set(winners) and not named <= set(winners):
                        return self.review(entry, f'answer {safe(a["text"])!r} names the top pair '
                                                  f'{plabels[winners[0]]} and others too - settle it by hand')
                    yes = bool(named) and named <= set(winners)
                    bodies.append({'outcome': 'YES' if yes else 'NO', 'answerId': a.get('id')})
                    if yes:
                        labels.append(safe(a['text']))
                if not labels:
                    labels = [f'all NO - no answer names {" or ".join(plabels[w] for w in winners)}']
                bodies.sort(key=lambda b: b['outcome'] == 'YES')     # NOs first, the deciding YES last
                return self.finish(entry, cp, code, tp, src, raw, top3, bodies, labels)
            listed = [a for a in answers if not a.get('isOther')]
            other = [a for a in answers if a.get('isOther')]
            read = {a['text']: answer_pair(a['text'], plabels) for a in listed}
            unread = [safe(t) for t, p in read.items() if p is None]
            ids, labels = [], []
            for w in winners:
                hits = [a for a in listed if read[a['text']] == w]
                if hits:
                    a = self.earliest(hits)
                    ids.append(a.get('id')); labels.append(safe(a['text']))
                    continue
                if unread:
                    return self.review(entry, f'winner {plabels[w]} is not an answer, and these answers name '
                                              f'no single pair - check them by hand: {unread}')
                if not other and entry.get('id'):
                    return self.review(entry, f'winner {plabels[w]} is not an answer and the market has no Other')
                ids.append(other[0]['id'] if other else None); labels.append(f'Other ({plabels[w]})')

        if entry.get('id'):
            ids = list(dict.fromkeys(ids))          # two tied cards can both land on Other
        if len(ids) == 1:
            body = {'outcome': 'CHOOSE_ONE', 'answerId': ids[0]}
        else:
            pct = round(100 / len(ids), 4)
            body = {'outcome': 'CHOOSE_MULTIPLE', 'resolutions': [{'answerId': i, 'pct': pct} for i in ids]}
        return self.finish(entry, cp, code, tp, src, raw, top3, [body], labels)

    def finish(self, entry, cp, code, tp, src, raw, top3, bodies, labels):
        """Send the resolution (one request, or one per answer for independent answers), record it,
        and post the top 3 as a comment."""
        comment = (f'Resolved automatically from [17Lands]({src}) ({self.event}, '
                   f'{TIME_PERIOD_LABELS.get(tp, tp)}, read {pretty(self.now)}):\n\n{top3}\n\n'
                   f'Data from 17Lands; not affiliated with or endorsed by 17Lands.')
        if not self.live:
            self.log(f'{entry["question"]}: would resolve to {" + ".join(labels)}\n{top3}')
            return
        snap = STATE / 'snapshots' / f'{code}_{cp["id"]}_{entry["kind"]}_{self.now:%Y%m%dT%H%M}.json'
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_text(json.dumps({'read': iso(self.now), 'source': src, 'rows': raw}, ensure_ascii=False),
                        encoding='utf-8')
        for body in bodies:
            try:
                self.mf.resolve(entry['id'], body)
            except ManifoldError:
                # The other runner (or the owner) resolved it between our read and now: record theirs.
                if self.live_answers(entry) is None:
                    return
                raise
        entry['resolution'] = {'outcome': labels, 'body': bodies if len(bodies) > 1 else bodies[0],
                               'at': iso(self.now), 'snapshot': snap.name}
        self.save()
        self.log(f'{entry["question"]}: RESOLVED to {" + ".join(labels)} ({entry["url"]})')
        try:
            self.mf.comment(entry['id'], comment)
        except ManifoldError as e:
            self.log(f'  resolution comment failed: {e}')

    # ------------------------------------------------------------ run

    def sets_to_process(self, only):
        if only:
            return [(set_info(self.http, only.upper(), self.event), True)]
        types = self.cfg['sets']['scryfall_set_types']
        found = detect_sets(self.http, self.event, types, self.now)
        newest = found[0] if found else None
        out = [(newest, True)] if newest else []
        for code, sst in self.state['sets'].items():
            if newest and code == newest['code']:
                continue
            if any(not m.get('resolution') for m in sst['markets'].values()):
                out.append(({'code': code, 'name': sst['name'], 'start': parse_time(sst['start'])}, False))
        return out

    def run(self, only=None):
        if self.live and not self.mf.key:
            raise SystemExit(f'no API key: set {self.mcfg["api_key_env"]} or write it to {self.mcfg["api_key_file"]}')
        try:
            bal = self.balance()
        except ManifoldError as e:
            if e.status in (400, 401, 403):
                raise SystemExit(f'Manifold rejected the API key (HTTP {e.status} {e.body or "(empty body)"}). '
                                 f'Copy the key again on Manifold and run mtg\\manifold\\save-api-key.ps1') from None
            raise
        self.log(f'run start; account {self.me()["username"] if self.me() else "(no API key - reads only)"}'
                 + (f', balance M${bal:.0f}' if bal is not None else ''))
        for s, is_newest in self.sets_to_process(only):
            age = (self.now - s['start']) / DAY
            self.log(f'{s["code"]} {s["name"]}: 17Lands start {pretty(s["start"])} (day {age:.1f})')
            for cp in self.cfg['checkpoints']:
                if cp.get('sets') and s['code'] not in cp['sets']:
                    continue
                blocked = False                     # sequential: a later market waits for earlier ones
                for kind in cp.get('kinds', ['top_card', 'top_pair']):
                    if not self.cfg['markets'][kind]['enabled']:
                        continue
                    where = f'{s["code"]} {cp["id"]}:{kind}'
                    try:                            # one failing market must not stop the others
                        entry = self.ensure_market(s, cp, kind, may_open=is_newest and not blocked)
                    except Exception as e:
                        self.error(where, e)
                        entry = None
                    if not entry and cp.get('sequential'):
                        if not blocked and is_newest and self.now < self.open_deadline(
                                cp, s['start'] + cp['close_day'] * DAY):
                            later = cp['kinds'][cp['kinds'].index(kind) + 1:]
                            if later:
                                self.log(f'{s["code"]} {cp["id"]}: {", ".join(later)} wait until {kind} is open')
                        blocked = True
                    if not entry or entry.get('resolution'):
                        continue
                    try:
                        self.resolve(entry, s, cp)
                    except Exception as e:
                        self.error(where, e)
        if not self.live and self.spend:
            b = self.balance()
            self.log(f'mana this run would spend: M${self.spend}' + (f' (balance M${b:.0f})' if b is not None else ''))
        if self.reviews and self.live:
            STATE.mkdir(exist_ok=True)
            with open(REVIEW_FILE, 'a', encoding='utf-8') as f:
                f.write(f'--- {iso(self.now)}\n' + '\n'.join(self.reviews) + '\n')

    def status(self):
        if not self.state['sets']:
            print('no markets recorded yet (state/markets.json is empty)')
        for code, sst in self.state['sets'].items():
            print(f'{code} {sst["name"]} (17Lands start {sst["start"]})')
            for k, m in sst['markets'].items():
                st = ('resolved: ' + ', '.join(m['resolution']['outcome'])
                      if isinstance(m.get('resolution', {}).get('outcome'), list)
                      else 'resolved' if m.get('resolution')
                      else f'REVIEW: {m["needs_review"]}' if m.get('needs_review')
                      else f'open, closes {m["close"]}')
                print(f'  {k:20} {st}\n  {"":20} {m["url"]}')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('command', choices=['plan', 'run', 'status'])
    ap.add_argument('--live', action='store_true', help='actually write to Manifold (run only)')
    ap.add_argument('--set', dest='only', help='17Lands expansion code, e.g. FRA')
    ap.add_argument('--now', help='pretend UTC time, dry runs only, e.g. 2026-10-13T16:00:00Z')
    ap.add_argument('--rehearse', action='store_true', help='dry runs only: treat all markets as open')
    ap.add_argument('--no-key', action='store_true', help='dry runs only: do not load the API key at all')
    ap.add_argument('--fail-on-review', action='store_true', help='exit 3 if a market needs review')
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')         # card names like Fili print as-is, not as cp1252
    cfg = json.loads((HERE / 'config.json').read_text(encoding='utf-8'))
    live = a.command == 'run' and a.live
    if live and (a.now or a.rehearse or a.no_key):
        raise SystemExit('--now, --rehearse and --no-key are for dry runs only')
    now = parse_time(a.now) if a.now else utcnow()
    bot = Bot(cfg, live, now, a.rehearse, a.no_key)
    if a.command == 'status':
        bot.status()
    else:
        bot.run(a.only)
        if bot.reviews:
            print(f'\n{len(bot.reviews)} item(s) need review' + (f' - see {REVIEW_FILE}' if live else ''))
        if bot.errors:
            print(f'\n{len(bot.errors)} market(s) hit an error and were skipped:\n  ' + '\n  '.join(bot.errors))
            sys.exit(1)
        if bot.reviews and a.fail_on_review:
            sys.exit(3)


if __name__ == '__main__':
    main()
