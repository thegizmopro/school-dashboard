# Board Meetings Overlay — What Changed & Why
**Date:** Oct 30, 2026 (just after midnight)

## Problem
Special board meetings (like Oct 30's two-session day) aren't in the district's online calendar when they're first announced. The school dashboard's board page reads the district-calendar.ics for the next "Board Meeting" event, and manual ICS edits get overwritten by the collector's next sync run (4x daily). Result: the board page showed the wrong next meeting.

## What Changed

### 1. New file: `site/data/board-meetings.json`
A manually-maintained overlay listing special board meetings. Each entry has:
- `date` — ISO date (YYYY-MM-DD)
- `label` — how it appears in the ICS/board page
- `times` — array of `{start, end, session}` (supports multi-session days)
- `location`, `description` — optional context
- `added`, `added_by` — provenance

**To add a special meeting:** add an entry to this file (or tell Arty). The next collector run picks it up automatically.

### 2. Modified: `collectors/collector.py`
The `fetch_district_cal()` function now calls `merge_board_meetings()` after downloading the district calendar. This function:
- Reads `board-meetings.json`
- Skips entries whose date has passed (natural expiry — no stale meetings)
- Generates ICS VEVENT blocks for each remaining entry
- Inserts them at the top of the ICS (before district events)
- Logs the manual count: `district cal: 76 events (2 manual)`

### 3. No changes to the board page
The board page already reads the ICS and matches `/board meeting/i` in the SUMMARY field. The overlay entries have "HUSD Board Meeting" in their summary, so they're found naturally. Zero frontend changes needed.

## Why This Approach
- **Option 1** (board.json override) required manually clearing expired dates — a trap.
- **Option 2** (this overlay) persists across collector runs, expires naturally, needs zero frontend changes.
- **Option 3** (smarter Simbli scraping) is the long-term goal but can't be built tonight.

## Current State
- Oct 30 morning + evening board meetings are in the overlay and the live ICS
- The collector will re-merge them on every run (00/06/12/18 PT)
- When the date passes (tomorrow), the overlay entry stays in the JSON but is skipped — add the next meeting when announced
