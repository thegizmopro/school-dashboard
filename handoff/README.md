# Harmony Today — design handoff

Design system and mockups for the Harmony Union front-page dashboard.
Approved direction: **earthy / outdoor-ed** (option `1a`). The newsprint-gazette alternative (`1b`) stayed in the file for reference and is not the build target.

Contents:

- `Design System.dc.html` — the visual system: color, type ramp, every component in its real states, geometry
- `tokens.json` — the same system machine-readable: colors, type ramps, spacing, radii, event-kind and source-chip mappings, per breakpoint
- `School Dashboard.dc.html` — the mockups, all four boards
- `support.js` — runtime for both HTML files; keep it beside them
- this document — component notes, data bindings, and open items

Open either HTML file directly in a browser.

The mockup renders four boards, referenced below by id:

| id | what |
|----|------|
| `1a` | phone 390px — Today, Week view, Lunch week, plus the token panel |
| `1b` | phone 390px — gazette alternative (not building) |
| `2a` | wall tablet 1194×834 landscape — fits one screen, no scroll |
| `2b` | laptop 1440 — three columns |

All content in the mockups comes from the real files (`menu-and-events.json`, `calendar-year.json`, the shARK site) as of Thu Sep 3, 2026, except the notices and the community digest, which are invented placeholders at realistic length — `notices.json` and `community-digest.json` don't exist yet.

---

## 1. The system in one paragraph

Oat paper, near-white cards, one green for identity and action, and three encoding accents (sun for no-school, clay for alerts and shARK, sky for events, iris for school business). Baloo 2 carries every number and name you're meant to read across a room; Karla carries everything you read up close; IBM Plex Mono marks provenance — kickers, timestamps, source chips, and the `*.json` line under any data-driven slot. Separation is border plus fill, never shadow. Rounded throughout — radius 0 doesn't appear.

Two rules worth keeping as you implement:

1. **Today is the only thing at hero scale.** The date, weather, and lunch are the largest type on the page. Nothing below Today may exceed a 24px heading.
2. **Every data-driven region names its source in mono.** Sponsor slots, the digest, the update stamp. It's how the family knows the page is alive and where to look when a widget goes stale.

---

## 2. Front-page order (all breakpoints)

1. Header — wordmark, district line, leaf mark
2. **Today** — date, day-of-year, weather, countdown chip
3. Summer counter strip (`☀️ N days until summer` · `Last day Jun 2`)
4. **Today's lunch** — main, side chips, always-available, breakfast
5. Theme-day callout (clay) — tomorrow's or today's notable meal
6. Today's calendar items, or the explicit empty state
7. Coming up — next 4–5 dated items
8. Notices — newest first
9. Community digest (5b)
10. shARK spotlight (5c)
11. Footer zone — sponsors + Get Involved + update stamp

Layout differences: the wall tablet splits 2–6 into the left column and 7–8 into the right, and drops 9–10 (see §4). The laptop runs 2–4 in column 1, 5–7 plus shARK in column 2, and notices plus the digest in column 3, with the footer zone spanning full width.

---

## 3. Component notes

### Today hero
Green gradient card, white text. Left: weekday kicker, `Sep 3` at hero scale, one line of school-day context ("Day 16 of the school year · regular dismissal 3:00"). Right: weather glyph, temp, hi/lo. Countdown chip sits inside the card on sun fill.

- **No school today** state: replace the day-of-year line with the reason ("No school — Labor Day") and suppress the lunch card entirely, replacing it with a single oat-filled card. Do not show an empty lunch card.
- Weather glyph maps from Open-Meteo WMO codes. Keep the set small: sun, part-sun, cloud, rain, storm, fog. No animation.
- Countdown chip shows the **single** nearest no-school date. Never stack two chips.

### Summer counter
Its own strip between hero and lunch, on `garden-pale`. Left: emoji + "N days until summer". Right: mono "Last day Jun 2" for context. It reads as a persistent kid feature, not an alert, so it never uses sun or clay.

### Today's lunch
The second-largest thing on the page. Main dish gets an emoji at 40–64px depending on breakpoint plus the dish name in display type. Sides render as a 2×2 chip grid on `paper` fill — one emoji per side, mapped by keyword:

```
salad/kale → 🥗   fruit/apple/pear/orange/berry → 🍏🍐🍊🫐
carrot/celery/cucumber → 🥕🥬🥒   rice/beans → 🍚🫘
cheese/yogurt → 🧀   potato → 🥔   milk → 🥛
```

Below the chips, a hairline, then two lines in `ink-muted`: always-available options and today's breakfast. Both come from the menu file's `daily_options` / `breakfast_weekly`, so they need no per-day authoring.

Main-dish emoji map: pasta 🍝, taco/burrito 🌮🌯, pizza 🍕, grilled cheese 🧇, patty/burger 🍔, nuggets/tofu 🍗, wrap 🌯, mac and cheese 🧈, hot dog 🌭, tamale 🫔. Unmatched → 🍽️.

### Theme-day callout
Clay card, white text, one mono kicker ("Today is" / "Tomorrow is") and one display line. Fires on: Pizza Friday, any day whose main matches a named theme, and early-release days (then the kicker is "Heads up" and the line is the dismissal time). Maximum one per screen — if both a theme day and an early release land together, the early release wins.

### Coming up
Row = date block (mono weekday, display day number) · accent bar · title + detail line. 4 rows on phone and tablet, 5 on laptop. Chronological, next 7–14 days, plus the nearest big-ticket item beyond that window if there's room.

- Accent bar color from `event-kind-color` in `tokens.json`.
- No-school rows take the whole row on oat fill instead of a white card — a no-school day should be visible without reading.
- shARK-sourced events carry a small mono `shARK` tag next to the title. **Do not uppercase it** — the brand capitalization is part of the name.
- shARK events appear here *and* on the shARK card by design. This list answers "when," the card answers "why."

### Notices
Source chip (mono, per `source-chip` map) + relative timestamp, then a bold headline and up to two lines of body. Newest first, hairline between. Three on phone and laptop.

The collector must dedupe across sources before this renders — the same early-release notice will arrive by ParentSquare, email, and WhatsApp. Prefer ParentSquare as canonical, keep the earliest timestamp.

### Community digest (5b)
Compact card, two parts. Top: the agent-written prose digest, 2–3 sentences, mono kicker with its date ("Digest · Wed Sep 2"). Bottom, after a hairline: **For sale & free** as a three-column row set — item (flex), price (bold; `Free` in garden), contact first name (right, small). Sold items render struck through in `ink-ghost` with a mono `Sold` in the price slot. A mono line closes the card: `LISTINGS EXPIRE AFTER 14 DAYS · community-digest.json`.

Density assumption is a handful of listings. Past ~8 active, cap the visible list and add a "N more" line rather than growing the card.

### shARK spotlight (5c)
`garden-pale` card with `garden-line` border, deliberately low on the page and visually distinct from the white information cards. Heading + `harmonyark.org` link, then "Next up" with the nearest shARK event and a one-line "then…" of the two after it, then the campaign line ($75,000 goal — garden, theater, library; $350/student suggested; no amount too small), then a garden-filled CTA: **Let's help shARK help our school →**.

### Footer zone
One combined region on `card-alt`: sponsor slots first under a mono "Thanks to our local sponsors", then a divider, then Get Involved (two mailto buttons — students submit news/editorials, parents suggest an event), then the update stamp. Sponsor slots are dashed placeholders at a fixed aspect until `sponsors.json` has entries; 2 across on phone, 3 on the tablet strip, 4 on laptop. No popups, no tracking, no third-party script — state it in the footer as the mockup does.

---

## 4. Wall tablet specifics (`2a`)

The whole point is that nothing scrolls at 1194×834, so the tablet drops content rather than compressing it:

- Notices becomes **Latest notice** — one notice at full length, a mono "3 this week", and a bottom line pointing at the phone.
- Community digest and shARK card are omitted; the notice card's bottom line mentions the digest.
- Coming up holds exactly 4 rows.
- Header carries both persistent chips (summer counter, countdown) so they survive the two-column split.

If the real display is portrait rather than landscape, the two columns become one and Coming up loses a row — flag it and I'll redraw.

---

## 5. Data bindings

| Region | File | Fields |
|---|---|---|
| Hero date, day count | derived | client clock, `calendar-year.json` first day |
| Weather | Open-Meteo | current temp, WMO code, daily hi/lo |
| Countdown chip | `calendar-year.json` | nearest `kind` in break/holiday/no_school |
| Summer counter | `calendar-year.json` | `2027-06-02` Last Day of School |
| Lunch | `menu-and-events.json` | `menu.lunch[today]`, `daily_options`, `milk`, `breakfast_weekly` |
| Theme day | `menu-and-events.json` | `notes` + main-dish match; early release from `calendar-year.json` |
| Today's items / Coming up | `calendar-year.json`, `parentsquare-live.ics`, shARK fetch | merged, sorted, deduped |
| Notices | `notices.json` | `posted`, `title`, `text`, `source`, `urgency` |
| Community | `community-digest.json` | digest prose + `listings[]` (item, price, contact, status, posted) |
| shARK | shARK weekly fetch | next 3 events + campaign line |
| Sponsors | `sponsors.json` | `name`, `image`, `link`, `active` |

Every widget degrades alone: a missing file hides its card and leaves the rest intact. Two states need real design treatment rather than an empty card — no school today (see hero notes) and no lunch posted (show the always-available options and say the main isn't published yet).

Refresh: 15 minutes is what the mockup's stamp claims. Weather and countdowns can update in place without a reload; a changed events or notices file may re-render its card.

---

## 6. Open items

1. The two mailto addresses — `news@` and `events@` are placeholders in the mockups.
2. Wall tablet orientation, portrait or landscape (see §4).
3. Notices and community digest content is invented. Once the first real digest and a week of real notices exist, check the card heights against the wall tablet — that layout has no slack.
4. Digest voice is written neutral-brief with one light touch, matching the parked default.
