# Instagram → Xiaohongshu Sync — Design Spec

**Date:** 2026-03-19
**Status:** Approved

---

## Overview

A self-contained tool + Claude skill that syncs new Instagram posts (images + captions) to Xiaohongshu. Triggered manually by asking Claude to run the sync. One-way: Instagram → Xiaohongshu only.

---

## Repository Structure

```
rb-sync/
└── skills/
    └── ig-xhs-sync/
        ├── SKILL.md              # Claude's instruction manual
        ├── requirements.txt      # Python dependencies
        ├── scrape.py             # Fetch recent Instagram posts via instaloader
        ├── rewrite.py            # Rewrite caption to XHS-native style via Claude API
        ├── post.py               # Post to Xiaohongshu via Playwright browser automation
        ├── sync.py               # Orchestrator
        ├── state.json            # Tracks which Instagram post IDs have been synced
        └── .env                  # Credentials and config
```

All scripts reference `state.json` and `.env` relative to their own file location (`Path(__file__).parent`), making the skill fully portable when installed to `~/.claude/skills/`.

---

## Data Flow

```
Instagram public profile (username)
    │  instaloader scrapes IG_FETCH_COUNT most recent posts
    ▼
scrape.py → [{id, shortcode, images: [local_path, ...], caption, timestamp}, ...]
    │  filter: skip IDs already in state.json
    │  skip: video posts (images only)
    ▼
rewrite.py → Claude API rewrites caption to XHS-native style
    │  shorter, conversational Chinese
    │  3-5 relevant emojis
    │  5-8 hashtags at end in #话题 format
    ▼
post.py → Playwright reuses saved session (cookies); uploads images, pastes caption, submits
    │  on success: mark post ID in state.json + update last_checked
    │  on failure: log error, leave unsynced (retry next run)
    │  temp images deleted after successful upload
    ▼
sync.py prints summary: "Synced N/M posts. X failed."
```

---

## Components

### `scrape.py`
- Fetches the `IG_FETCH_COUNT` most recent posts (default: 10) from a public Instagram username using `instaloader`
- Returns structured post data: `{id, shortcode, images: [local_path, ...], caption, timestamp}`
- Filters out already-synced post IDs (from `state.json`)
- Downloads images to `<skill_dir>/tmp/<post_id>/` — cleaned up after successful post
- Skips video posts with a log message

### `rewrite.py`
- Accepts an Instagram caption string
- Calls Claude API (model: `claude-haiku-4-5-20251001` — fast, cheap)
- Prompt: rewrite as XHS note — shorter, conversational Chinese, 3-5 emojis, 5-8 hashtags in `#话题` format
- If caption is empty or very short, produces a minimal fallback: a single-line XHS-style note with emojis and hashtags (no vision/image analysis)
- Returns rewritten caption string

### `post.py`
- Accepts list of local image paths + rewritten caption
- Launches Playwright (headed/headless configurable via `.env`)
- **Session management:** saves browser session cookies to `<skill_dir>/xhs_session/` after first successful login; reuses cookies on subsequent runs to skip login. If cookies are expired/invalid, falls back to credential login
- **First-time login:** runs headed (regardless of `PLAYWRIGHT_HEADLESS`) so user can complete any SMS OTP or CAPTCHA manually; saves session after success
- Navigates to post creation UI, uploads images one by one, pastes caption, submits
- Deletes temp image folder (`tmp/<post_id>/`) after successful upload
- Returns success/failure with error details

### `sync.py` (orchestrator)
- Entry point: reads `.env` and `state.json`
- Validates required env keys — exits early with clear message listing all missing keys
- Calls scrape → rewrite → post for each new post sequentially
- On success: atomically writes updated `state.json` (write to `.state.json.tmp`, then rename) to avoid partial-write corruption; updates `last_checked` timestamp
- On failure: logs error, skips (post remains unsynced for retry)
- Prints summary at end: `Synced N/M posts. X failed.`

### `state.json`
```json
{
  "synced_posts": ["ABC123", "DEF456"],
  "last_checked": "2026-03-19T10:00:00Z"
}
```
- `synced_posts`: list of Instagram post **shortcodes** (the dedup key — used to filter already-synced posts in `scrape.py`) that have been successfully posted to XHS
- `last_checked`: ISO timestamp of the last sync run (updated by `sync.py` at end of each run)
- Created fresh if missing: `{"synced_posts": [], "last_checked": null}`

### `.env`
```
IG_USERNAME=your_instagram_username
IG_FETCH_COUNT=10
XHS_USERNAME=your_xhs_phone_or_email
XHS_PASSWORD=your_xhs_password
ANTHROPIC_API_KEY=sk-ant-...
PLAYWRIGHT_HEADLESS=false
```

---

## SKILL.md Design

The skill is a **reference + technique** type. It tells Claude:

1. **What the skill does** — syncs new Instagram posts to Xiaohongshu
2. **Prerequisites check** — verify `.env` has all required keys before running
3. **First-time setup** — run `pip install -r requirements.txt && playwright install chromium` once; run `python post.py --login` to complete first-time XHS login and save session
4. **How to run** — `cd <skill_dir> && python sync.py`
5. **How to read output** — success summary format, failure message format
6. **Common failure modes and fixes** (see Error Handling below)
7. **Reporting back** — summarize to user: how many synced, any failures

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Post already synced | Skipped silently (filtered by `state.json`) |
| Post has no caption | Rewrite produces minimal fallback note with emojis + hashtags |
| Post has video | Skipped with log message — images only |
| XHS session expired | `post.py` retries with credential login; if that fails, exits with error |
| XHS login fails (credentials) | `post.py` exits with error; post NOT marked synced |
| XHS submission fails | Not marked synced, retries next run |
| Claude API rewrite fails | Skip that post, log error, continue with others |
| Instagram returns 0 new posts | Log "nothing new to sync", exit cleanly |
| `state.json` missing | Created fresh with `{"synced_posts": [], "last_checked": null}` |
| `.env` missing required key | `sync.py` exits early listing all missing keys |
| `sync.py` crash between XHS post success and state.json write | Duplicate post risk on next run — accepted risk (low probability, low severity); atomic write minimises the window |

**Key invariant:** A post is only added to `state.json` after it has been **successfully posted to XHS**. `state.json` is written atomically (tmp file + rename) to prevent corruption.

### Common Failure Modes (for SKILL.md)

| Error | Fix |
|---|---|
| Playwright browser not installed | `playwright install chromium` |
| XHS session expired / login fails | Run `python post.py --login` to redo first-time login |
| Instagram scrape returns nothing | Check `IG_USERNAME` in `.env`; verify profile is public |
| Claude API error | Check `ANTHROPIC_API_KEY` in `.env` |

---

## Decisions & Trade-offs

- **Browser automation over official API** — Xiaohongshu's official API requires a registered business account. Playwright is the only practical option for personal accounts.
- **instaloader over Instagram Graph API** — Public profile scraping requires no developer app or access token.
- **claude-haiku-4-5-20251001 for rewrites** — Fast and cheap; caption rewriting doesn't need Sonnet/Opus quality.
- **JSON file over SQLite** — Simple enough for tracking post IDs; no query complexity needed.
- **Manual trigger over cron** — User asks Claude to run the sync; no daemon or scheduler needed.
- **Cookie-based session reuse** — Avoids repeated XHS login friction and reduces risk of login-related account flags.
- **Atomic state.json writes** — Prevents corruption if process is killed mid-write; minimises duplicate-post window.
- **Skill self-contained in project** — Developed in `rb-sync/skills/ig-xhs-sync/`; installed to `~/.claude/skills/` when ready.
