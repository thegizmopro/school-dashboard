import re, json, datetime

logs = [
    r'C:\Users\kenzo\SynologyDrive\projects\whatsapp\whatsapp-salmon-creek.md',
    r'C:\Users\kenzo\SynologyDrive\projects\whatsapp\whatsapp-harmony-sc-free-trade-sell.md'
]
KW = re.compile(r'no school|reminder|due|early release|forms?|field trip|meeting|event|fundrais|volunteer|picture day|book fair|conference|spirit|schedule|cancel|heads up|alert|workshop|pizza|menu', re.I)
SALE = re.compile(r'\$\d|for sale|free\b|iso\b|selling|giveaway|trade', re.I)

items, listings = [], []
for lp in logs:
    lines = open(lp, encoding='utf-8', errors='replace').read().splitlines()
    for line in lines:
        m = re.match(r'\[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})\] \[([^\]]+)\] ([^:]+): (.*)', line)
        if not m:
            continue
        d, t, g, who, text = m.groups()
        if SALE.search(text):
            price_m = re.search(r'\$\d+[\d,\.]*', text)
            listings.append({'date': d, 'who': who.strip(), 'text': text.strip()[:150],
                             'price': price_m.group(0) if price_m else 'Free'})
        if KW.search(text):
            items.append({'date': d, 'who': who.strip(), 'text': text.strip()[:200]})

out = {'generated': datetime.datetime.now().isoformat(timespec='seconds'),
       'digest': '',
       'listings': listings}
with open(r'site\data\community-digest.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
with open(r'site\data\community-items.json', 'w', encoding='utf-8') as f:
    json.dump(items, f, indent=1, ensure_ascii=False)
print('notable:', len(items), '| listings:', len(listings))
for i in items:
    print(' -', i['date'], i['who'] + ':', i['text'][:90])
for l in listings:
    print(' $', l['date'], l['who'] + ':', l['text'][:90])
