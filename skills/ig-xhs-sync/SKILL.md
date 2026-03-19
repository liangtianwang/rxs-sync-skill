---
name: ig-xhs-sync
description: Use when asked to sync Instagram posts to Xiaohongshu, check for new posts to sync, or post Instagram content to 小红书. Handles scraping, caption rewriting, and browser posting.
---

# Instagram → Xiaohongshu Sync

## Overview

Syncs new posts from a public Instagram profile to Xiaohongshu. Scrapes Instagram via instaloader, rewrites captions to XHS-native Chinese style via Claude API, and posts via Playwright browser automation. State is tracked in `state.json` to avoid duplicates.

## First-Time Setup

Run once before first sync:

```bash
cd <skill_dir>
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# Fill in .env with your credentials
python post.py --login   # Opens browser — log in manually, press Enter when done
```

Required `.env` keys: `IG_USERNAME`, `XHS_USERNAME`, `XHS_PASSWORD`, `ANTHROPIC_API_KEY`

Optional: `IG_FETCH_COUNT` (default: 10), `PLAYWRIGHT_HEADLESS` (default: false)

## Running the Sync

```bash
cd <skill_dir>
python sync.py
```

**Success output:**
```
Found 2 new post(s) to sync.

Processing ABC123...
  Caption rewritten.
  Post submitted successfully.
  ✓ ABC123 synced.

Done. Synced 2/2 posts. 0 failed.
```

**Partial failure output:**
```
Processing DEF456...
  Post failed: Timeout waiting for selector
  ✗ DEF456 failed — will retry next run.

Done. Synced 1/2 posts. 1 failed.
```

**Nothing to sync:**
```
Nothing new to sync.
```

## Checking Prerequisites Before Running

1. Verify `.env` exists and contains all required keys
2. Verify `xhs_session/storage.json` exists (if not, run `python post.py --login` first)
3. If deps missing: `pip install -r requirements.txt && playwright install chromium`

## Reporting Back to User

After `sync.py` completes, report:
- How many posts were synced
- Any failures and their error messages
- If 0 new posts: confirm "nothing new to sync"

## Troubleshooting

| Error | Fix |
|---|---|
| `playwright install` needed | Run `playwright install chromium` |
| XHS session expired / login fails | Run `python post.py --login` to redo login |
| Instagram scrape returns nothing | Check `IG_USERNAME` in `.env`; verify the profile is public |
| `anthropic.APIError` | Check `ANTHROPIC_API_KEY` in `.env` |
| Missing `.env` keys listed on exit | Fill them in `.env` |
