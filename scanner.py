#!/usr/bin/env python3
"""Memecoin Narrative Radar V2: public-source scanner, one pass, stdlib only.

Run with DISCORD_WEBHOOK as an environment variable. Designed for a short
GitHub Actions scheduled run (not an always-open local terminal).
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

WEBHOOK = os.getenv('DISCORD_WEBHOOK', '').strip()
STATE_PATH = Path(__file__).with_name('state.json')
NOW = datetime.now(timezone.utc)
MAX_AGE_HOURS = max(1, min(48, int(os.getenv('MAX_AGE_HOURS', '12'))))
MIN_SCORE = max(4, min(20, int(os.getenv('MIN_SCORE', '8'))))
MAX_ALERTS = max(1, min(10, int(os.getenv('MAX_ALERTS', '3'))))
USER_AGENT = 'Mozilla/5.0 (compatible; NarrativeRadarV2/2.0; public feeds)'

# Focused queries, not broad words like "AI" or "meme" that cause junk alerts.
BSKY_QUERIES = [
    'baby animal rescued', 'monkey rescued', 'zoo newborn named',
    'animal viral video', 'unexpected discovery', 'robot went viral',
    'AI viral meme', 'new internet meme', 'strange breaking news',
]
NEWS_QUERIES = [
    'animal rescued named OR zoo baby animal',
    'viral animal video unusual OR hilarious',
    'AI robot viral unexpected',
    'internet meme viral trend',
    'bizarre discovery unusual news',
]

ANIMAL = r'\b(monkeys?|spider monkeys?|gorillas?|penguins?|otters?|capybaras?|raccoons?|cats?|kittens?|dogs?|puppies|foxes|fox|birds?|elephants?|pandas?|koalas?|sloths?|turtles?|ducks?|goats?|wildlife|zoo|animals?|pets?)\b'
ANIMAL_EVENT = r'\b(rescued?|saved?|found|born|birth|newborn|baby|named|adopted?|escaped?|survived?|released?|rare|discovered?|reunited|orphaned|first|unexpected)\b'
MEME_EVENT = r'\b(viral|meme|trend(?:ing)?|internet sensation|blows? up|explod(?:ed|es|ing)|millions? of views|catchphrase|internet-famous)\b'
AI = r'\b(artificial intelligence|a[. ]?i[. ]?|robots?|humanoids?|chatbots?|deepfakes?|synthetic video|machine learning)\b'
NEWS_EVENT = r'\b(breaking|discovered?|uncovered?|revealed?|unusual|bizarre|strange|unexpected|mystery|record-breaking|first-ever|rare|surprising)\b'
POSITIVE = [r'\b(rescued? from trafficking|wildlife trafficking|newborn|rare baby|given the names?|named [a-z]+|unexpectedly|caught on camera|went viral|going viral|first ever|first-ever)\b']
SPAM = re.compile(r'\b(buy now|click here|affiliate|promo code|referral|discount code|giveaway|airdrop|presale|free tokens?|pump\.fun|contract address|ca:|dm me|onlyfans|crypto signals?|paid partnership)\b',re.I)
CHITCHAT = re.compile(r'\b(i (think|wish|want|need|feel|am|\x27m)|my (website|blog|dog|cat|friend|thoughts)|please|can someone|does anyone|what do you think|your ai chatbot|i don\x27t want|subscribe to)\b',re.I)
GENERIC = set('the a an and or to in on at for from with by of is are was were it its this that these those two one new now today yesterday latest viral internet breaking news video photo footage footage says say after before amid about can could should would will named name baby animal animals rescued rescue gets got have has had been what why how who where when source update live story report reports amid via more than into over under again watch caught first first-ever wild zoo scientists people media social online see seen many some'.split())


def request_bytes(url):
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json, application/rss+xml, application/xml, */*'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()


def parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
    except (ValueError, TypeError):
        try:
            return parsedate_to_datetime(value).astimezone(timezone.utc)
        except (ValueError, TypeError, IndexError):
            return None


def normalize(s):
    return re.sub(r'\s+', ' ', re.sub(r'https?://\S+', '', s or '')).strip()


def fetch_bluesky():
    results = []
    for query in BSKY_QUERIES:
        qs = urllib.parse.urlencode({'q': query, 'sort': 'latest', 'limit': '30'})
        try:
            data = json.loads(request_bytes('https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?' + qs))
            for p in data.get('posts', []):
                rec = p.get('record') or {}
                author = p.get('author') or {}
                handle = author.get('handle', '')
                rkey = p.get('uri', '').rsplit('/', 1)[-1]
                title = normalize(rec.get('text', ''))
                when = parse_iso(rec.get('createdAt') or p.get('indexedAt'))
                if title and handle and rkey:
                    results.append({'title': title, 'url': f'https://bsky.app/profile/{handle}/post/{rkey}',
                                    'source': 'Bluesky', 'date': when,
                                    'likes': int(p.get('likeCount') or 0),
                                    'reposts': int(p.get('repostCount') or 0)})
        except (urllib.error.URLError, ValueError, TimeoutError, OSError) as exc:
            print('Bluesky unavailable for', repr(query), ':', str(exc)[:100])
    return results


def fetch_news():
    results = []
    for query in NEWS_QUERIES:
        qs = urllib.parse.urlencode({'q': query + ' when:1d', 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'})
        try:
            root = ET.fromstring(request_bytes('https://news.google.com/rss/search?' + qs))
            for i in root.findall('.//item')[:25]:
                title = normalize(i.findtext('title', ''))
                url = normalize(i.findtext('link', ''))
                date = parse_iso(i.findtext('pubDate'))
                if title and url.startswith('https://'):
                    results.append({'title': title, 'url': url, 'source': 'Google News',
                                    'date': date, 'likes': 0, 'reposts': 0})
        except (urllib.error.URLError, ET.ParseError, TimeoutError, OSError) as exc:
            print('Google News unavailable for', repr(query), ':', str(exc)[:100])
    return results


def is_recent(dt):
    # Reject undated posts and old stories, to avoid fake "new" notifications.
    return bool(dt and dt <= NOW + timedelta(minutes=5)
                and NOW - dt <= timedelta(hours=MAX_AGE_HOURS))


def classify(item):
    text = item['title']
    t = text.lower()
    if len(text) < 40 or SPAM.search(t) or CHITCHAT.search(t) or not is_recent(item['date']):
        return None
    animal = bool(re.search(ANIMAL, t))
    animal_event = bool(re.search(ANIMAL_EVENT, t))
    mem = bool(re.search(MEME_EVENT, t))
    ai = bool(re.search(AI, t))
    news = bool(re.search(NEWS_EVENT, t))
    categories = []
    if animal and animal_event: categories.append(('Animal story', 6))
    if animal and mem: categories.append(('Viral animal', 7))
    if ai and (mem or news): categories.append(('AI trend', 6))
    if mem and (news or re.search(r'\b(name|mascot|character|joke|trend|video|catchphrase|challenge)\b', t)):
        categories.append(('Meme trend', 5))
    if news and re.search(r'\b(record|discovery|scientists?|space|ocean|mystery|creature|robot|species|strange|bizarre|unexpected|unusual)\b', t):
        categories.append(('Unusual news', 5))
    if not categories:
        return None
    category, score = max(categories, key=lambda k: k[1])
    score += 2 if re.search(POSITIVE[0], t) else 0
    if item['source'] == 'Google News': score += 1
    likes = item['likes']; reposts = item['reposts']
    if likes >= 15 or reposts >= 5: score += 2
    if likes >= 100 or reposts >= 25: score += 2
    if re.search(r'\b(rescued?|named|born|discovered?|viral|unexpected|bizarre)\b', t): score += 1
    if score < MIN_SCORE:
        return None
    return {'category': category, 'score': score, 'ticker': suggest_ticker(text, category)}


def suggest_ticker(title, category):
    # This is creative ideation, not a claim that a token exists.
    # Prefer names in quotes, then first meaningful capitalized word.
    picks = re.findall(r'["\u201c\u2018\x27]([A-Za-z]{3,12})["\u201d\u2019\x27]', title)
    picks += re.findall(r'\bnamed\s+([A-Z][a-z]{2,11})\b', title)
    picks += re.findall(r'\b([A-Z][a-z]{3,11})\b', title)
    for word in picks:
        if word.lower() not in GENERIC and word.lower() not in {'google', 'bluesky', 'reddit', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday', 'reporter'}:
            return word.upper()[:8]
    return {'Animal story':'RESCUE', 'Viral animal':'CRITTER', 'Meme trend':'MEME',
            'AI trend':'AIMEME', 'Unusual news':'ODDITY'}[category]


def signature(text):
    words = set(re.findall(r'[a-z]{4,}', text.lower())) - GENERIC
    return sorted(words)[:30]


def same_story(sig, prior):
    a = set(sig)
    for words in prior:
        b = set(words)
        if len(a & b) >= 3 and len(a & b) / max(1, min(len(a), len(b))) >= .7:
            return True
    return False


def ident(url):
    return hashlib.sha256(url.encode()).hexdigest()[:24]


def discord(payload):
    if not WEBHOOK.startswith(('https://discord.com/api/webhooks/', 'https://discordapp.com/api/webhooks/')):
        raise RuntimeError('Missing or invalid DISCORD_WEBHOOK secret. Set it in GitHub Settings > Secrets and variables > Actions.')
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(WEBHOOK, data=body, method='POST', headers={'Content-Type': 'application/json', 'User-Agent': USER_AGENT})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                if response.status not in (200, 204): raise RuntimeError('Discord returned HTTP ' + str(response.status))
            return
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt == 0:
                time.sleep(min(10, float(exc.headers.get('Retry-After', '2')))); continue
            raise RuntimeError('Discord rejected message: HTTP ' + str(exc.code)) from exc


def alert(item, analysis):
    title = item['title'][:230]
    payload = {'allowed_mentions': {'parse': []}, 'embeds': [{
        'title': '🚨 ' + analysis['category'] + ': ' + title,
        'url': item['url'],
        'description': ('**Possible ticker idea:** `$' + analysis['ticker'] + '` (not an existing-token check)\n'
                        '**Narrative:** ' + explain(item, analysis) + '\n'
                        '**Source:** ' + item['source'] + ' · **Filter score:** ' + str(analysis['score']) + '/12+\n'
                        '**Original post / article:** ' + item['url'] + '\n'
                        '_Idea only. Not investment advice, and virality is not guaranteed._'),
        'color': 0x27B6D8, 'timestamp': (item['date'] or NOW).isoformat()
    }]}
    discord(payload)


def explain(item, analysis):
    category = analysis['category']
    return {'Animal story': 'A specific real-world animal event can give a coin a recognizable story.',
            'Viral animal': 'An unusual animal story is already being shared online.',
            'AI trend': 'An AI-related event or character could spark a distinct online meme.',
            'Meme trend': 'A recognizable meme or trend may inspire a community nickname.',
            'Unusual news': 'An unexpected event with a clear hook could become a meme.'}[category]


def load_state():
    if not STATE_PATH.exists(): return None
    try:
        d = json.loads(STATE_PATH.read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else None
    except (ValueError, OSError):
        return None


def scan():
    if os.getenv('TEST_ALERT') == '1':
        discord({'allowed_mentions': {'parse': []}, 'embeds': [{'title': '✅ Memecoin Radar V2 connected!',
                'description': 'Your Discord webhook works. The scheduled scanner can now send filtered narrative leads.',
                'color': 0x28A745}]})
        print('Test alert delivered.'); return
    # Require a real webhook before altering the repo state.
    if not WEBHOOK.startswith(('https://discord.com/api/webhooks/', 'https://discordapp.com/api/webhooks/')):
        raise RuntimeError('DISCORD_WEBHOOK is not set. Add the repository secret.')
    fetched = fetch_bluesky() + fetch_news()
    if not fetched:
        print('No feeds reachable; keeping state unchanged so next scan can retry.'); return
    old = load_state()
    virgin = old is None
    seen = (old or {}).get('seen', {})
    if not isinstance(seen, dict): seen = {}
    recent_topics = (old or {}).get('topics', [])
    if not isinstance(recent_topics, list): recent_topics = []
    # Keep a bounded 48h history; URL hashes only, no webhook or credentials.
    cutoff = (NOW - timedelta(hours=48)).timestamp()
    seen = {k:v for k,v in seen.items() if isinstance(v,(int,float)) and v >= cutoff}
    recent_topics = [x for x in recent_topics if isinstance(x,dict) and x.get('ts', 0) >= cutoff]
    known_topics = [x.get('words', []) for x in recent_topics]
    pending = []
    this_batch = set()
    for item in fetched:
        key = ident(item['url'])
        if key in seen or key in this_batch: continue
        this_batch.add(key)
        # Only persist candidates that pass the quality filter.
        # Weak posts are re-evaluated in memory, rather than filling Git history.
        meta = classify(item)
        if not meta: continue
        seen[key] = NOW.timestamp()
        sig = signature(item['title'])
        if same_story(sig, known_topics): continue
        pending.append((meta['score'], item, meta, sig))
    pending.sort(key=lambda row: (row[0], row[1]['likes'] + 2*row[1]['reposts']), reverse=True)
    sent = 0
    picked = []
    for _, item, meta, sig in pending:
        if same_story(sig, known_topics + picked): continue
        picked.append(sig)
        if virgin or sent >= MAX_ALERTS: continue
        try:
            alert(item, meta)
            print('Alert sent:', meta['category'], item['url'])
            recent_topics.append({'words': sig, 'ts': NOW.timestamp()})
            sent += 1
        except Exception as exc:
            # Don't mark failed alerts as sent; URL can retry next run.
            seen.pop(ident(item['url']), None)
            print('Alert failed:', str(exc)[:140])
    # On a first run, index existing stories but don't send old backlog.
    if virgin:
        print('First run: learned', len(this_batch), 'existing posts; no old alerts sent.')
        recent_topics.extend({'words': sig, 'ts': NOW.timestamp()} for sig in picked[:50])
    # Limit stored hashes so a frequently scheduled public repo stays small.
    seen = dict(sorted(seen.items(), key=lambda kv: kv[1], reverse=True)[:1500])
    STATE_PATH.write_text(json.dumps({'seen': seen, 'topics': recent_topics[-150:]}, indent=2), encoding='utf-8')
    print('Scan complete. Sources:', len(fetched), 'Candidates:', len(pending), 'Alerts:', sent)


if __name__ == '__main__':
    try:
        scan()
    except Exception as exc:
        print('Scanner error:', str(exc))
        sys.exit(1)
