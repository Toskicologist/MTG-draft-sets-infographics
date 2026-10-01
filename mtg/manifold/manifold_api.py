"""Minimal Manifold Markets API client (https://docs.manifold.markets/api).

Where the published docs and the server disagree, this follows the server source
(github.com/manifoldmarkets/manifold, common/src/api/market-types.ts, checked 2026-09-29):
  - POST /market needs `liquidityTier` (100, 1000, 10000 or 100000) - the docs don't list it
  - resolving a sum-to-one multiple-choice market takes {"outcome": "CHOOSE_ONE", "answerId": ...}
    or {"outcome": "CHOOSE_MULTIPLE", "resolutions": [{"answerId", "pct"}]} - the docs still show
    an older {"outcome": "MKT", "resolutions": [{"answer": index}]} shape
  - `idempotencyKey` (10 chars from ID_ALPHABET) becomes the new market's id, and a second create
    with the same key fails with 400 'Contract has already been created at <url>'. ANY user may
    create a market with any key (create-market.ts has no creator check), so a market found at a
    key is only the bot's own if its creatorId says so
  - GET /markets?userId=<id> lists one user's markets, newest first (limit up to 1000)
Rate limit is 500 requests/minute/IP; this bot makes a few per run.
"""
import hashlib, json, os, re, urllib.error, urllib.request
from pathlib import Path

ID_ALPHABET = 'useandom26T198340PX75pxJACKVERYMINDBUSHWOLFGQZbfghjklqvwyzrict'   # common/src/util/random.ts
ANSWER_COST_BY_TIER = {100: 25, 1000: 100, 10000: 1000, 100000: 10000}             # common/src/tier.ts


class ManifoldError(Exception):
    def __init__(self, status, body):
        super().__init__(f'HTTP {status}: {body}')
        self.status, self.body = status, body


def idempotency_key(*parts):
    """Deterministic 10-character market id for (salt, set, checkpoint, kind)."""
    digest = hashlib.sha256(':'.join(parts).encode('utf-8')).digest()
    return ''.join(ID_ALPHABET[b % len(ID_ALPHABET)] for b in digest[:10])     # 62 chars, not 64


def market_cost(outcome_type, num_answers, has_other, liquidity_tier):
    """Mana charged to create a market (common/src/economy.ts getAnte)."""
    if outcome_type != 'MULTIPLE_CHOICE':
        return liquidity_tier
    n = num_answers + (1 if has_other else 0)
    return max(n * ANSWER_COST_BY_TIER[liquidity_tier], liquidity_tier) if n else liquidity_tier


KEY_SHAPE = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')


def load_api_key(env_name, key_file):
    """The key from the env var or key file, checked for shape but never printed.
    Manifold makes keys with crypto.randomUUID() (web/lib/api/api-key.ts). A control character
    in the header - e.g. the literal Ctrl+V (0x16) a classic Windows console types into a hidden
    Read-Host prompt - gets HTTP 400 with an empty body from Manifold's front end, not a 401."""
    key, source = os.environ.get(env_name, '').strip(), f'${env_name}'
    if not key:
        p = Path(os.path.expanduser(key_file))
        if not p.exists():
            return None
        key, source = p.read_text(encoding='utf-8-sig', errors='replace').strip(), key_file
    if key and not KEY_SHAPE.fullmatch(key):
        odd = sum(1 for c in key if not 33 <= ord(c) <= 126)
        raise SystemExit(f'the API key in {source} is not a Manifold key: expected 36 characters like '
                         f'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx, found {len(key)} characters, {odd} of them '
                         f'invisible/control/non-ASCII. Copy it again on Manifold and run '
                         f'mtg\\manifold\\save-api-key.ps1')
    return key or None


class Manifold:
    def __init__(self, base, key=None, user_agent='mtg-manifold-bot/0.1'):
        self.base, self.key, self.ua = base.rstrip('/'), key, user_agent

    def _call(self, method, path, body=None, auth=False):
        headers = {'User-Agent': self.ua, 'Accept': 'application/json'}
        if auth:
            if not self.key:
                raise ManifoldError(0, 'no API key configured')
            headers['Authorization'] = f'Key {self.key}'
        data = None
        if body is not None:
            data = json.dumps(body).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode('utf-8')
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            raise ManifoldError(e.code, e.read().decode('utf-8', 'replace')[:500]) from None

    # reads
    def me(self):
        return self._call('GET', '/me', auth=True)

    def market(self, market_id):
        try:
            return self._call('GET', f'/market/{market_id}')
        except ManifoldError as e:
            if e.status == 404:
                return None
            raise

    def group(self, slug):
        return self._call('GET', f'/group/{slug}')

    def markets_by(self, user_id, limit=1000):
        """Markets created by this user (LiteMarkets: no answers), newest first."""
        return self._call('GET', f'/markets?userId={user_id}&limit={limit}') or []

    # writes
    def create_market(self, body):
        return self._call('POST', '/market', body, auth=True)

    def update_market(self, market_id, **fields):
        """POST /market/<id>/update (in the server schema, not the public docs): question,
        descriptionMarkdown, closeTime, visibility, ..."""
        return self._call('POST', f'/market/{market_id}/update', fields, auth=True)

    def add_answer(self, market_id, text):
        return self._call('POST', f'/market/{market_id}/answer', {'text': text}, auth=True)

    def resolve(self, market_id, body):
        return self._call('POST', f'/market/{market_id}/resolve', body, auth=True)

    def comment(self, market_id, markdown):
        return self._call('POST', '/comment', {'contractId': market_id, 'markdown': markdown}, auth=True)
