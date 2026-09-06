"""Community digest helper.

The digest PROSE is agent-written and the listings may be agent-curated — this
script never destroys either. It rescans the WhatsApp logs and MERGES what it
finds: curated entries stay, newly detected listings are added, everything ages
out 14 days after its post date. (The regex only catches price/keyword posts;
listings a human spots by reading the logs are safe from overwrite.)

Usage:
  python gen_digest.py                    # dry run: preview merge, write nothing
  python gen_digest.py --write            # merge listings, keep existing prose
  python gen_digest.py --write "prose"    # merge listings AND set new prose

Safe to run unattended (cron): prose changes only when explicitly passed.
--write also refreshes data/community-items.json (local scratch for the digest
writer, never published). Extracted listings carry the first URL found in the
message (rendered as a link by the site).
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
# salmon-creek chatter often says "free event/activity" or discusses "$10 pricing"
# for programs — neither is a for-sale listing. Strong sale verbs everywhere;
# bare "free"/"trade"/"$N" only count in the free-trade group; "free" outside it
# must not be an event-ish noun phrase (potluck/class/workshop/...).
SALE_STRONG = re.compile(r'for sale|iso\b|selling|give\s?away|giveaway|wtb', re.I)
SALE_LOOSE = re.compile(r'\$\d|for sale|iso\b|selling|give\s?away|giveaway|wtb|free\b|trade\b|\bgive\b', re.I)
EVENTISH = re.compile(r'\b(event|potluck|activity|class|workshop|program|gathering|webinar|community|parade|festival|performance|movie)\b', re.I)
INVITEISH = re.compile(r'\b(join|sign\s?up|rsvp|drop-?in|meets|monthly|please join|welcome)\b', re.I)
MERGE_WINDOW_MIN = 15   # consecutive messages from one sender = one multi-item giveaway
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
    is_trade = ('harmony' in lp.lower() or 'trade' in lp.lower())
    sale_re = SALE_LOOSE if is_trade else SALE_STRONG
    last_who, last_dt, merged_extra = None, None, 0
    for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
        m = re.match(r'\[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})\] \[([^\]]+)\] ([^:]+): (.*)', line)
        if not m:
            continue
        d, t, g, who, text = m.groups()
        who = who.strip()
        try:
            if datetime.date.fromisoformat(d) < cutoff:
                continue
            dt = datetime.datetime.strptime(f'{d} {t}', '%Y-%m-%d %H:%M')
        except ValueError:
            continue
        key = (d, who, text.strip()[:60])
        if key in seen:
            continue
        seen.add(key)

        marker_sale = bool(sale_re.search(text)) or (not is_trade and re.search(r'\bfree\b', text, re.I)
                        and not EVENTISH.search(text) and not INVITEISH.search(text))
        trivial = text.strip() in ('[image]', '[image removed]') or len(text.strip()) < 5
        # a claim/reply from another sender never updates last_*, so only the
        # OFFERER's own follow-up posts fold into their open giveaway listing
        continuation = (last_who == who and last_dt is not None
                        and 0 <= (dt - last_dt).total_seconds() <= MERGE_WINDOW_MIN * 60
                        and listings and listings[-1].get('who') == who)
        if marker_sale and not trivial:
            price_m = re.search(r'\$\d+[\d,\.]*', text)
            item = strip_urls(text)[:100] or text.strip()[:100]
            if continuation:
                merged_extra += 1
                listings[-1]['item'] = re.sub(r' — \+\d+ more items$', '', listings[-1]['item']) \
                                       + f' — +{merged_extra} more items'
            else:
                merged_extra = 0
                listings.append({'posted': d, 'who': who,
                                 'item': item,
                                 'price': price_m.group(0) if price_m else
                                          'Free' if re.search(r'\bfree\b|\bgive\b', text, re.I) else '—',
                                 'url': first_url(text)})
            last_who, last_dt = who, dt
        elif continuation and not trivial:
            merged_extra += 1
            listings[-1]['item'] = re.sub(r' — \+\d+ more items$', '', listings[-1]['item']) \
                                   + f' — +{merged_extra} more items'
            last_who, last_dt = who, dt
        if KW.search(text):
            items.append({'date': d, 'who': who, 'text': strip_urls(text)[:200], 'url': first_url(text)})

listings = listings[-12:]

args = sys.argv[1:]
write = '--write' in args
prose_arg = next((a for a in args if a != '--write'), None)

existing = {}
if SITE_DIGEST.exists():
    try:
        existing = json.loads(SITE_DIGEST.read_text(encoding='utf-8'))
    except Exception:
        existing = {}
existing_listings = existing.get('listings', [])

# --write MERGES listings: curated entries are kept, newly detected ones are added,
# entries simply age out after EXPIRE_DAYS. Replacement would wipe agent curation
# every run (the regex can't see keyword-less listings a human spots by reading).
def _norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', str(s).lower()).strip()

cutoff_date = (datetime.date.today() - datetime.timedelta(days=EXPIRE_DAYS)).isoformat()
merged = [l for l in existing_listings if str(l.get('posted', '')) >= cutoff_date]
expired = len(existing_listings) - len(merged)
added = []
for l in listings:
    if any(_norm(l['item'])[:30] == _norm(k.get('item', ''))[:30] for k in merged):
        continue
    if any(k.get('posted') == l['posted'] and k.get('who') == l['who'] for k in merged):
        continue
    merged.append(l)
    added.append(l)
merged = merged[-12:]

print(f"notable: {len(items)} | listings on site: {len(existing_listings)} -> {len(merged)} "
      f"(+{len(added)} new, -{expired} expired)")
for i in items[-10:]:
    print('  -', i['date'], i['who'] + ':', i['text'][:90])
for l in added:
    print('  +', l['posted'], l['who'] + ':', l['item'][:80], '|', l['price'])

if not write:
    print('\n(dry run — pass --write to update site/data/community-digest.json)')
    sys.exit(0)

digest = existing.get('digest', '') if prose_arg is None else prose_arg
out = {'generated': datetime.datetime.now().isoformat(timespec='seconds'),
       'digest': digest,
       'listings': merged}
SITE_DIGEST.parent.mkdir(parents=True, exist_ok=True)
SITE_DIGEST.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
LOCAL_ITEMS.parent.mkdir(parents=True, exist_ok=True)
LOCAL_ITEMS.write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding='utf-8')
print(f'\nwrote {SITE_DIGEST.relative_to(ROOT)} (prose {"SET" if prose_arg is not None else "preserved"}, listings merged) + {LOCAL_ITEMS.relative_to(ROOT)}')
