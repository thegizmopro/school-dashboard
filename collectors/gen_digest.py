"""Community digest helper.

The digest PROSE and the published listings are agent-curated — this script
never overwrites them by accident. It rescans the WhatsApp logs and shows
candidate listings; with --write it regenerates the listings block in
site/data/community-digest.json while PRESERVING the digest prose.

Usage:
  python gen_digest.py                    # dry run: print candidates, write nothing
  python gen_digest.py --write            # regenerate listings, keep existing prose
  python gen_digest.py --write "prose"    # regenerate listings AND set new prose

Always writes data/community-items.json (local scratch for the digest writer,
never published). Listings auto-expire after 14 days, are deduped, and carry
the first URL found in the message (rendered as a link by the site).
"""
import re, json, datetime, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE_DIGEST = ROOT / "site" / "data" / "community-digest.json"
LOCAL_ITEMS = ROOT / "data" / "community-items.json"

logs = [
    r'C:\Users\kenzo\SynologyDrive\projects\whatsapp\whatsapp-salmon-creek.md',
    r'C:\Users\kenzo\SynologyDrive\projects\whatsapp\whatsapp-harmony-sc-free-trade-sell.md'
]
KW = re.compile(r'no school|reminder|due|early release|forms?|field trip|meeting|event|fundrais|volunteer|picture day|book fair|conference|spirit|schedule|cancel|heads up|alert|workshop|pizza|menu', re.I)
SALE = re.compile(r'\$\d|for sale|free\b|iso\b|selling|giveaway|trade', re.I)
EXPIRE_DAYS = 14

def first_url(text):
    m = re.search(r'https?://\S+', text or '')
    return m.group(0).rstrip('.,)!') if m else None

def strip_urls(text):
    return re.sub(r'\s*https?://\S+', '', text).strip()

items, listings = [], []
seen = set()
cutoff = datetime.date.today() - datetime.timedelta(days=EXPIRE_DAYS)
for lp in logs:
    p = pathlib.Path(lp)
    if not p.exists():
        continue
    for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
        m = re.match(r'\[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})\] \[([^\]]+)\] ([^:]+): (.*)', line)
        if not m:
            continue
        d, t, g, who, text = m.groups()
        try:
            if datetime.date.fromisoformat(d) < cutoff:
                continue
        except ValueError:
            continue
        key = (d, who.strip(), text.strip()[:60])
        if key in seen:
            continue
        seen.add(key)
        if SALE.search(text):
            price_m = re.search(r'\$\d+[\d,\.]*', text)
            listings.append({'posted': d, 'who': who.strip(),
                             'item': strip_urls(text)[:100] or text.strip()[:100],
                             'price': price_m.group(0) if price_m else 'Free',
                             'url': first_url(text)})
        if KW.search(text):
            items.append({'date': d, 'who': who.strip(), 'text': strip_urls(text)[:200], 'url': first_url(text)})

listings = listings[-12:]

args = sys.argv[1:]
write = '--write' in args
prose_arg = next((a for a in args if a != '--write'), None)

print(f'notable: {len(items)} | listings: {len(listings)}')
for i in items[-10:]:
    print('  -', i['date'], i['who'] + ':', i['text'][:90])
for l in listings:
    print('  $', l['posted'], l['who'] + ':', l['item'][:80], '|', l['price'])

if not write:
    print('\n(dry run — pass --write to update site/data/community-digest.json)')
    sys.exit(0)

existing = {}
if SITE_DIGEST.exists():
    try:
        existing = json.loads(SITE_DIGEST.read_text(encoding='utf-8'))
    except Exception:
        existing = {}

digest = existing.get('digest', '') if prose_arg is None else prose_arg
out = {'generated': datetime.datetime.now().isoformat(timespec='seconds'),
       'digest': digest,
       'listings': listings}
SITE_DIGEST.parent.mkdir(parents=True, exist_ok=True)
SITE_DIGEST.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
LOCAL_ITEMS.parent.mkdir(parents=True, exist_ok=True)
LOCAL_ITEMS.write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding='utf-8')
print(f'\nwrote {SITE_DIGEST.relative_to(ROOT)} (prose {"SET" if prose_arg is not None else "preserved"}) + {LOCAL_ITEMS.relative_to(ROOT)}')
