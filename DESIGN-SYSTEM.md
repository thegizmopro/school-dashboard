# School Dashboard — Design System v1 (implemented)
_Based on Claude's tokens.json (option 1a, earthy/outdoor-ed). This doc records the implemented values; tokens.json is authoritative._

## Colors
paper #F6F1E4 (page bg) · card #FFFDF7 · card-alt #EFE9D9 (footer zone)
ink #22301F · ink-body #3B4A37 · ink-soft #5A6B54 · ink-muted #6B7A63 · ink-faint #8A9280 · ink-ghost #A39A83
garden #3F7A43 · garden-deep #2C5A34 · garden-pale #E7EEDF · garden-line #CFDCC4
clay #C2643B (alerts, theme-day, shARK tag) · sun #E8A33D (countdown chip, no-school) · sky #6E9BC2 (events) · iris #8E7CB0 (conference)
Hero gradient: 150deg #3F7A43 → #2C5A34

## Type
Baloo 2 (display, 700-800) — dates, headings, menu names, countdowns
Karla (body, 400/700) — copy, lists, buttons
IBM Plex Mono (500) — kickers, timestamps, source chips, provenance
Google Fonts import, laptop hero-date 58px / wall 68px / phone 46px

## Layout
Grid 2-col ≥820px, 1-col below. Hero 150deg gradient. Cards 16px radius, hero 20px. Borders + fill, never shadows.

## Front page order
Hero (date/weather) → countdown chip → Today's Lunch (+theme callout) → Today & Coming Up → Notices → Community (feed + For Sale) → shARK card → Footer zone (sponsors + Get Involved + provenance stamp)
