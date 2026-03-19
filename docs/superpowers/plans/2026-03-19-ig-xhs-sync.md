# Instagram → Xiaohongshu Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-contained skill that scrapes new Instagram posts and publishes them to Xiaohongshu with AI-rewritten captions, triggered by asking Claude to run the sync.

**Architecture:** Five Python modules in `skills/ig-xhs-sync/` — a shared state module, a scraper (instaloader), a caption rewriter (Claude API), a poster (Playwright), and an orchestrator. Each module is independently testable via mocks. The SKILL.md tells Claude how to invoke and troubleshoot the system.

**Tech Stack:** Python 3.11+, instaloader, anthropic SDK, playwright (Python), python-dotenv, pytest

---

## File Map

| File | Responsibility |
|---|---|
| `skills/ig-xhs-sync/requirements.txt` | Python dependencies |
| `skills/ig-xhs-sync/.env.example` | Template for required credentials |
| `skills/ig-xhs-sync/state.py` | Read/write `state.json` atomically |
| `skills/ig-xhs-sync/scrape.py` | Fetch new Instagram posts, download images |
| `skills/ig-xhs-sync/rewrite.py` | Rewrite captions via Claude API |
| `skills/ig-xhs-sync/post.py` | Post to XHS via Playwright; `--login` flag for first-time setup |
| `skills/ig-xhs-sync/sync.py` | Orchestrator: validate env → scrape → rewrite → post → update state |
| `skills/ig-xhs-sync/SKILL.md` | Claude's instruction manual for running the sync |
| `skills/ig-xhs-sync/tests/test_state.py` | Unit tests for state.py |
| `skills/ig-xhs-sync/tests/test_scrape.py` | Unit tests for scrape.py (mocked instaloader) |
| `skills/ig-xhs-sync/tests/test_rewrite.py` | Unit tests for rewrite.py (mocked Anthropic client) |
| `skills/ig-xhs-sync/tests/test_sync.py` | Unit tests for sync.py (mocked modules) |

> `post.py` relies entirely on live browser automation — unit tests are not practical. It is tested manually via `python post.py --login` during first-time setup.

---

## Task 1: Project Scaffold

**Files:**
- Create: `skills/ig-xhs-sync/requirements.txt`
- Create: `skills/ig-xhs-sync/.env.example`
- Create: `skills/ig-xhs-sync/state.json`
- Create: `skills/ig-xhs-sync/tests/__init__.py`

- [ ] **Step 1: Create the skill directory structure**

```bash
mkdir -p skills/ig-xhs-sync/tests
mkdir -p skills/ig-xhs-sync/tmp
mkdir -p skills/ig-xhs-sync/xhs_session
touch skills/ig-xhs-sync/tests/__init__.py
```

- [ ] **Step 1b: Create `tests/conftest.py` to fix import paths**

`skills/ig-xhs-sync/tests/conftest.py`:
```python
import sys
from pathlib import Path

# Add the skill directory to sys.path so tests can import modules directly
# (e.g. `from state import read_state` instead of `from ig_xhs_sync.state import ...`)
sys.path.insert(0, str(Path(__file__).parent.parent))
```

- [ ] **Step 2: Create `requirements.txt`**

```
instaloader>=4.10
anthropic>=0.40.0
playwright>=1.49.0
python-dotenv>=1.0.0
pytest>=8.0.0
pytest-mock>=3.14.0
```

- [ ] **Step 3: Create `.env.example`**

```
IG_USERNAME=your_instagram_username
IG_FETCH_COUNT=10
XHS_USERNAME=your_xhs_phone_or_email
XHS_PASSWORD=your_xhs_password
ANTHROPIC_API_KEY=sk-ant-...
PLAYWRIGHT_HEADLESS=false
```

- [ ] **Step 4: Create initial `state.json`**

```json
{"synced_posts": [], "last_checked": null}
```

- [ ] **Step 5: Install dependencies**

```bash
cd skills/ig-xhs-sync
pip install -r requirements.txt
playwright install chromium
```

Expected: all packages install without errors.

- [ ] **Step 6: Commit scaffold**

```bash
git add skills/ig-xhs-sync/
git commit -m "feat: scaffold ig-xhs-sync skill directory"
```

---

## Task 2: State Management (`state.py`)

**Files:**
- Create: `skills/ig-xhs-sync/state.py`
- Create: `skills/ig-xhs-sync/tests/test_state.py`

- [ ] **Step 1: Write failing tests**

`skills/ig-xhs-sync/tests/test_state.py`:
```python
import json
import pytest
from pathlib import Path
from unittest.mock import patch


def test_read_state_missing_file(tmp_path):
    """Missing state.json returns a fresh default state."""
    from state import read_state
    state = read_state(tmp_path / "state.json")
    assert state == {"synced_posts": [], "last_checked": None}


def test_read_state_existing_file(tmp_path):
    """Existing state.json is read correctly."""
    from state import read_state
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({
        "synced_posts": ["ABC123"],
        "last_checked": "2026-03-19T10:00:00Z"
    }))
    state = read_state(state_file)
    assert state["synced_posts"] == ["ABC123"]
    assert state["last_checked"] == "2026-03-19T10:00:00Z"


def test_write_state_atomic(tmp_path):
    """write_state writes atomically — tmp file then rename."""
    from state import write_state
    state_file = tmp_path / "state.json"
    data = {"synced_posts": ["XYZ789"], "last_checked": "2026-03-19T12:00:00Z"}
    write_state(state_file, data)
    written = json.loads(state_file.read_text())
    assert written == data
    # tmp file must be cleaned up
    assert not (tmp_path / ".state.json.tmp").exists()


def test_write_state_no_tmp_leftover(tmp_path):
    """No .state.json.tmp file left after successful write."""
    from state import write_state
    state_file = tmp_path / "state.json"
    write_state(state_file, {"synced_posts": [], "last_checked": None})
    assert not (tmp_path / ".state.json.tmp").exists()


def test_mark_synced_adds_shortcode():
    """mark_synced appends shortcode to synced_posts."""
    from state import mark_synced
    state = {"synced_posts": ["EXISTING"], "last_checked": None}
    updated = mark_synced(state, "NEWPOST")
    assert "NEWPOST" in updated["synced_posts"]
    assert "EXISTING" in updated["synced_posts"]


def test_mark_synced_updates_last_checked():
    """mark_synced sets last_checked to a valid ISO timestamp."""
    from state import mark_synced
    from datetime import datetime
    state = {"synced_posts": [], "last_checked": None}
    updated = mark_synced(state, "ABC")
    assert updated["last_checked"] is not None
    datetime.fromisoformat(updated["last_checked"])  # raises if invalid


def test_mark_synced_does_not_mutate_original():
    """mark_synced returns a new dict — original is not modified."""
    from state import mark_synced
    original = {"synced_posts": ["ORIG"], "last_checked": None}
    mark_synced(original, "NEW")
    assert original["synced_posts"] == ["ORIG"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd skills/ig-xhs-sync
python -m pytest tests/test_state.py -v
```

Expected: `ModuleNotFoundError: No module named 'state'`

- [ ] **Step 3: Implement `state.py`**

```python
import json
import os
from pathlib import Path
from datetime import datetime, timezone


DEFAULT_STATE = {"synced_posts": [], "last_checked": None}


def read_state(state_path: Path) -> dict:
    """Read state.json; return default state if file is missing."""
    if not state_path.exists():
        return dict(DEFAULT_STATE)
    return json.loads(state_path.read_text())


def write_state(state_path: Path, state: dict) -> None:
    """Write state atomically: write to .tmp then rename."""
    tmp_path = state_path.parent / ".state.json.tmp"
    tmp_path.write_text(json.dumps(state, indent=2))
    os.replace(tmp_path, state_path)


def mark_synced(state: dict, shortcode: str) -> dict:
    """Return updated state with shortcode added to synced_posts."""
    updated = dict(state)
    updated["synced_posts"] = list(state["synced_posts"]) + [shortcode]
    updated["last_checked"] = datetime.now(timezone.utc).isoformat()
    return updated
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_state.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/ig-xhs-sync/state.py skills/ig-xhs-sync/tests/test_state.py skills/ig-xhs-sync/tests/conftest.py
git commit -m "feat: add state.py with atomic read/write"
```

---

## Task 3: Instagram Scraper (`scrape.py`)

**Files:**
- Create: `skills/ig-xhs-sync/scrape.py`
- Create: `skills/ig-xhs-sync/tests/test_scrape.py`

- [ ] **Step 1: Write failing tests**

`skills/ig-xhs-sync/tests/test_scrape.py`:
```python
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


def make_mock_post(shortcode, is_video=False, caption="test caption", image_count=1):
    post = MagicMock()
    post.shortcode = shortcode
    post.mediaid = f"id_{shortcode}"
    post.is_video = is_video
    post.caption = caption
    post.date_utc.isoformat.return_value = "2026-03-19T10:00:00"
    # instaloader post.get_sidecar_nodes() for multi-image posts
    if image_count > 1:
        nodes = [MagicMock() for _ in range(image_count)]
        for i, n in enumerate(nodes):
            n.is_video = False
        post.get_sidecar_nodes.return_value = iter(nodes)
        post.typename = "GraphSidecar"
    else:
        post.get_sidecar_nodes.return_value = iter([])
        post.typename = "GraphImage"
    return post


def test_scrape_filters_already_synced(tmp_path):
    """Posts whose shortcode is in synced_posts are excluded."""
    from scrape import filter_new_posts
    posts = [
        make_mock_post("ABC"),
        make_mock_post("DEF"),
        make_mock_post("GHI"),
    ]
    synced = ["ABC", "DEF"]
    result = filter_new_posts(posts, synced)
    assert len(result) == 1
    assert result[0].shortcode == "GHI"


def test_scrape_skips_video_posts():
    """Video posts are excluded with no error."""
    from scrape import filter_new_posts
    posts = [
        make_mock_post("VID1", is_video=True),
        make_mock_post("IMG1", is_video=False),
    ]
    result = filter_new_posts(posts, synced=[])
    assert len(result) == 1
    assert result[0].shortcode == "IMG1"


def test_scrape_empty_caption():
    """Posts with None caption are included (rewrite handles fallback)."""
    from scrape import filter_new_posts
    posts = [make_mock_post("NOCAP", caption=None)]
    result = filter_new_posts(posts, synced=[])
    assert len(result) == 1


def test_download_images_calls_download_post(tmp_path):
    """download_images creates the post dir and calls loader.download_post with it."""
    from scrape import download_images
    post = make_mock_post("ABC123")

    with patch("scrape.instaloader") as mock_il:
        mock_loader = MagicMock()
        mock_il.Instaloader.return_value = mock_loader

        # Write fake jpg files so glob returns them (simulating instaloader download)
        post_dir = tmp_path / "ABC123"
        post_dir.mkdir()
        (post_dir / "img1.jpg").write_bytes(b"fake")
        (post_dir / "img2.jpg").write_bytes(b"fake")

        paths = download_images(post, tmp_dir=tmp_path)

    expected_post_dir = tmp_path / "ABC123"
    mock_loader.download_post.assert_called_once_with(post, target=str(expected_post_dir))
    assert len(paths) == 2
    assert all(p.suffix == ".jpg" for p in paths)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_scrape.py -v
```

Expected: `ModuleNotFoundError: No module named 'scrape'`

- [ ] **Step 3: Implement `scrape.py`**

```python
import instaloader
import shutil
from pathlib import Path
from typing import Optional


def filter_new_posts(posts: list, synced: list[str]) -> list:
    """Remove already-synced and video posts from list."""
    result = []
    for post in posts:
        if post.shortcode in synced:
            continue
        if post.is_video:
            print(f"  [skip] {post.shortcode} is a video — images only")
            continue
        result.append(post)
    return result


def download_images(post, tmp_dir: Path) -> list[Path]:
    """Download all images for a post into tmp_dir/<shortcode>/. Returns list of local paths."""
    post_dir = tmp_dir / post.shortcode
    post_dir.mkdir(parents=True, exist_ok=True)

    # Create a fresh loader with dirname_pattern set in the constructor (not post-hoc)
    # so that the download directory is guaranteed correct across instaloader versions.
    loader = instaloader.Instaloader(
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        quiet=True,
        dirname_pattern=str(post_dir),
        filename_pattern="{shortcode}",
    )
    loader.download_post(post, target=str(post_dir))

    # Collect downloaded jpg/png files
    images = sorted(post_dir.glob("*.jpg")) + sorted(post_dir.glob("*.png"))
    return images


def scrape_new_posts(ig_username: str, fetch_count: int, synced: list[str], tmp_dir: Path) -> list[dict]:
    """
    Fetch up to fetch_count recent posts from ig_username.
    Filter out synced and video posts.
    Download images into tmp_dir.
    Return list of dicts: {shortcode, images, caption, timestamp}
    """
    # Use a basic loader just for fetching profile/posts metadata (no file downloads)
    profile_loader = instaloader.Instaloader(
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        quiet=True,
    )

    profile = instaloader.Profile.from_username(profile_loader.context, ig_username)
    recent_posts = list(profile.get_posts())[:fetch_count]
    new_posts = filter_new_posts(recent_posts, synced)

    results = []
    for post in new_posts:
        print(f"  Downloading images for {post.shortcode}...")
        images = download_images(post, tmp_dir)
        results.append({
            "shortcode": post.shortcode,
            "images": images,
            "caption": post.caption or "",
            "timestamp": post.date_utc.isoformat(),
        })

    return results


def cleanup_post_images(post_dir: Path) -> None:
    """Delete temp image folder after successful post."""
    if post_dir.exists():
        shutil.rmtree(post_dir)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_scrape.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/ig-xhs-sync/scrape.py skills/ig-xhs-sync/tests/test_scrape.py
git commit -m "feat: add scrape.py for Instagram post fetching"
```

---

## Task 4: Caption Rewriter (`rewrite.py`)

**Files:**
- Create: `skills/ig-xhs-sync/rewrite.py`
- Create: `skills/ig-xhs-sync/tests/test_rewrite.py`

- [ ] **Step 1: Write failing tests**

`skills/ig-xhs-sync/tests/test_rewrite.py`:
```python
import pytest
from unittest.mock import MagicMock, patch


SYSTEM_PROMPT_KEYWORDS = ["小红书", "emoji", "hashtag", "#"]


def test_rewrite_returns_string():
    """rewrite_caption returns a non-empty string."""
    from rewrite import rewrite_caption
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [
        MagicMock(text="好美的一天！☀️ #旅行 #生活")
    ]
    result = rewrite_caption("Beautiful day!", mock_client)
    assert isinstance(result, str)
    assert len(result) > 0


def test_rewrite_calls_correct_model():
    """rewrite_caption uses claude-haiku-4-5-20251001."""
    from rewrite import rewrite_caption
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [
        MagicMock(text="测试内容 #标签")
    ]
    rewrite_caption("test", mock_client)
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-haiku-4-5-20251001"


def test_rewrite_empty_caption_returns_fallback():
    """Empty caption produces a fallback note, not an empty string."""
    from rewrite import rewrite_caption
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [
        MagicMock(text="✨ 分享生活点滴 #日常 #生活")
    ]
    result = rewrite_caption("", mock_client)
    assert len(result) > 0


def test_rewrite_api_error_raises():
    """API errors propagate so sync.py can catch and skip the post."""
    from rewrite import rewrite_caption
    mock_client = MagicMock()
    # Use a plain Exception to avoid coupling to internal anthropic SDK constructor details
    mock_client.messages.create.side_effect = Exception("rate limit")
    with pytest.raises(Exception, match="rate limit"):
        rewrite_caption("some caption", mock_client)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_rewrite.py -v
```

Expected: `ModuleNotFoundError: No module named 'rewrite'`

- [ ] **Step 3: Implement `rewrite.py`**

```python
import anthropic


SYSTEM_PROMPT = """You are a Chinese social media content writer specialising in 小红书 (Xiaohongshu/RedNote).

Given an Instagram caption (in any language), rewrite it as a 小红书 note following these rules:
- Write in natural, conversational Simplified Chinese
- Keep it SHORT — 1-3 sentences maximum
- Include 3-5 relevant emojis woven naturally into the text
- End with 5-8 hashtags in #话题 format on a new line
- If the input is empty or very short, produce a generic upbeat lifestyle note with emojis and hashtags

Output ONLY the rewritten note. No explanations, no English, no quotation marks."""


def rewrite_caption(caption: str, client: anthropic.Anthropic) -> str:
    """Rewrite an Instagram caption into XHS-native style using Claude API."""
    user_message = caption.strip() if caption.strip() else "[no caption provided]"

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text.strip()


def make_client(api_key: str) -> anthropic.Anthropic:
    """Create an Anthropic client from API key."""
    return anthropic.Anthropic(api_key=api_key)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_rewrite.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/ig-xhs-sync/rewrite.py skills/ig-xhs-sync/tests/test_rewrite.py
git commit -m "feat: add rewrite.py for XHS-native caption generation"
```

---

## Task 5: XHS Poster (`post.py`)

**Files:**
- Create: `skills/ig-xhs-sync/post.py`

> Unit tests are not practical for pure browser automation. This module is validated manually via `python post.py --login`.

- [ ] **Step 1: Implement `post.py`**

```python
"""
post.py — Post content to Xiaohongshu via Playwright.

Usage:
  python post.py --login              # First-time login + save session
  (called directly by sync.py)        # Normal posting
"""
import argparse
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, BrowserContext

SKILL_DIR = Path(__file__).parent
SESSION_DIR = SKILL_DIR / "xhs_session"
XHS_URL = "https://www.xiaohongshu.com"
XHS_CREATOR_URL = "https://creator.xiaohongshu.com"


def save_session(context: BrowserContext) -> None:
    SESSION_DIR.mkdir(exist_ok=True)
    storage = context.storage_state()
    (SESSION_DIR / "storage.json").write_text(json.dumps(storage))
    print("  Session saved to xhs_session/")


def load_session_path() -> Path | None:
    path = SESSION_DIR / "storage.json"
    return path if path.exists() else None


def login_with_credentials(page: Page, username: str, password: str) -> bool:
    """Attempt credential login. Returns True on success."""
    try:
        page.goto(f"{XHS_URL}/login")
        page.wait_for_load_state("networkidle")
        # Switch to password login tab if present
        pw_tab = page.locator("text=密码登录")
        if pw_tab.count() > 0:
            pw_tab.click()
        page.fill('input[placeholder*="手机号"]', username)
        page.fill('input[type="password"]', password)
        page.click('button[type="submit"]')
        # Wait for redirect away from login page
        page.wait_for_url(lambda url: "login" not in url, timeout=30000)
        return True
    except Exception as e:
        print(f"  Credential login failed: {e}")
        return False


def post_note(context: BrowserContext, images: list[Path], caption: str) -> bool:
    """Upload images and caption to XHS creator platform. Returns True on success."""
    page = context.new_page()
    try:
        page.goto(f"{XHS_CREATOR_URL}/publish/publish")
        page.wait_for_load_state("networkidle")

        # Upload images one by one
        file_input = page.locator('input[type="file"]').first
        for img_path in images:
            file_input.set_input_files(str(img_path))
            time.sleep(1)  # wait for upload to register

        # Wait for upload previews to appear
        page.wait_for_selector(".upload-preview", timeout=30000)

        # Fill caption
        caption_area = page.locator('textarea[placeholder*="描述"]').first
        caption_area.fill(caption)

        # Submit
        page.click('button:has-text("发布")')
        page.wait_for_url(lambda url: "success" in url or "manage" in url, timeout=30000)
        print("  Post submitted successfully.")
        return True
    except Exception as e:
        print(f"  Post failed: {e}")
        return False
    finally:
        page.close()


def run_post(images: list[Path], caption: str, username: str, password: str, headless: bool) -> bool:
    """Main entry point called by sync.py. Returns True on success."""
    session_path = load_session_path()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)

        if session_path:
            context = browser.new_context(storage_state=str(session_path))
            print("  Reusing saved XHS session.")
        else:
            context = browser.new_context()

        # Verify session is valid by checking if we're logged in
        page = context.new_page()
        page.goto(XHS_URL)
        page.wait_for_load_state("networkidle")
        is_logged_in = page.locator('[class*="user-avatar"]').count() > 0
        page.close()

        if not is_logged_in:
            print("  Session expired or missing — attempting credential login...")
            page = context.new_page()
            success = login_with_credentials(page, username, password)
            page.close()
            if not success:
                browser.close()
                return False
            save_session(context)

        result = post_note(context, images, caption)
        browser.close()
        return result


def run_login(username: str, password: str) -> None:
    """First-time login flow — always headed so user can handle OTP/CAPTCHA."""
    print("Starting first-time login (headed mode)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(XHS_URL)
        print("Please log in manually in the browser window.")
        print("Press Enter here once you are logged in...")
        input()
        save_session(context)
        browser.close()
    print("Login complete. Session saved.")


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv(SKILL_DIR / ".env")

    parser = argparse.ArgumentParser()
    parser.add_argument("--login", action="store_true", help="Run first-time login")
    args = parser.parse_args()

    if args.login:
        run_login(
            username=os.environ["XHS_USERNAME"],
            password=os.environ["XHS_PASSWORD"],
        )
    else:
        print("Use sync.py to run the full sync, or --login for first-time setup.")
```

- [ ] **Step 2: Manual smoke test — first-time login**

```bash
cd skills/ig-xhs-sync
python post.py --login
```

Expected: Chromium opens, you log in manually, press Enter, session saved to `xhs_session/storage.json`.

- [ ] **Step 3: Commit**

```bash
git add skills/ig-xhs-sync/post.py
git commit -m "feat: add post.py for XHS browser automation"
```

---

## Task 6: Orchestrator (`sync.py`)

**Files:**
- Create: `skills/ig-xhs-sync/sync.py`
- Create: `skills/ig-xhs-sync/tests/test_sync.py`

- [ ] **Step 1: Write failing tests**

`skills/ig-xhs-sync/tests/test_sync.py`:
```python
import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path


REQUIRED_KEYS = ["IG_USERNAME", "XHS_USERNAME", "XHS_PASSWORD", "ANTHROPIC_API_KEY"]


def test_validate_env_all_present():
    """No missing keys returns empty list."""
    from sync import validate_env
    env = {k: "value" for k in REQUIRED_KEYS}
    env["IG_FETCH_COUNT"] = "10"
    assert validate_env(env) == []


def test_validate_env_missing_keys():
    """Returns list of missing key names."""
    from sync import validate_env
    env = {"IG_USERNAME": "user"}
    missing = validate_env(env)
    assert "XHS_USERNAME" in missing
    assert "ANTHROPIC_API_KEY" in missing


def test_sync_no_new_posts(tmp_path):
    """When scrape returns empty list, prints 'nothing to sync' and exits cleanly."""
    from sync import run_sync
    with patch("sync.scrape_new_posts", return_value=[]) as mock_scrape, \
         patch("sync.read_state", return_value={"synced_posts": [], "last_checked": None}), \
         patch("sync.write_state") as mock_write:
        result = run_sync(
            ig_username="test_user",
            fetch_count=10,
            xhs_username="xhs",
            xhs_password="pw",
            api_key="key",
            headless=False,
            skill_dir=tmp_path,
        )
    assert result["synced"] == 0
    assert result["failed"] == 0


def test_sync_success_updates_state(tmp_path):
    """Successfully posted post is added to state."""
    from sync import run_sync
    mock_post = {
        "shortcode": "ABC123",
        "images": [tmp_path / "img.jpg"],
        "caption": "hello",
        "timestamp": "2026-03-19T10:00:00",
    }
    with patch("sync.scrape_new_posts", return_value=[mock_post]), \
         patch("sync.read_state", return_value={"synced_posts": [], "last_checked": None}), \
         patch("sync.rewrite_caption", return_value="小红书内容 #测试"), \
         patch("sync.run_post", return_value=True), \
         patch("sync.cleanup_post_images"), \
         patch("sync.write_state") as mock_write, \
         patch("sync.make_client", return_value=MagicMock()):
        result = run_sync(
            ig_username="user", fetch_count=10,
            xhs_username="xhs", xhs_password="pw",
            api_key="key", headless=False, skill_dir=tmp_path,
        )
    assert result["synced"] == 1
    assert result["failed"] == 0
    written_state = mock_write.call_args[0][1]
    assert "ABC123" in written_state["synced_posts"]


def test_sync_post_failure_not_marked_synced(tmp_path):
    """Failed post is NOT added to state."""
    from sync import run_sync
    mock_post = {
        "shortcode": "FAIL1",
        "images": [tmp_path / "img.jpg"],
        "caption": "hello",
        "timestamp": "2026-03-19T10:00:00",
    }
    with patch("sync.scrape_new_posts", return_value=[mock_post]), \
         patch("sync.read_state", return_value={"synced_posts": [], "last_checked": None}), \
         patch("sync.rewrite_caption", return_value="内容 #标签"), \
         patch("sync.run_post", return_value=False), \
         patch("sync.write_state") as mock_write, \
         patch("sync.make_client", return_value=MagicMock()):
        result = run_sync(
            ig_username="user", fetch_count=10,
            xhs_username="xhs", xhs_password="pw",
            api_key="key", headless=False, skill_dir=tmp_path,
        )
    assert result["synced"] == 0
    assert result["failed"] == 1
    # write_state is only called on success — must NOT have been called for a failed post
    mock_write.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_sync.py -v
```

Expected: `ModuleNotFoundError: No module named 'sync'`

- [ ] **Step 3: Implement `sync.py`**

```python
"""
sync.py — Orchestrator: scrape Instagram → rewrite captions → post to XHS.

Usage:
  cd skills/ig-xhs-sync && python sync.py
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

SKILL_DIR = Path(__file__).parent
load_dotenv(SKILL_DIR / ".env")

from state import read_state, write_state, mark_synced
from scrape import scrape_new_posts, cleanup_post_images
from rewrite import rewrite_caption, make_client
from post import run_post


REQUIRED_ENV_KEYS = ["IG_USERNAME", "XHS_USERNAME", "XHS_PASSWORD", "ANTHROPIC_API_KEY"]


def validate_env(env: dict) -> list[str]:
    """Return list of missing required env keys."""
    return [k for k in REQUIRED_ENV_KEYS if not env.get(k)]


def run_sync(ig_username, fetch_count, xhs_username, xhs_password,
             api_key, headless, skill_dir) -> dict:
    """Run the full sync pipeline. Returns {synced: int, failed: int}."""
    state_path = skill_dir / "state.json"
    tmp_dir = skill_dir / "tmp"
    tmp_dir.mkdir(exist_ok=True)

    state = read_state(state_path)
    new_posts = scrape_new_posts(ig_username, fetch_count, state["synced_posts"], tmp_dir)

    if not new_posts:
        print("Nothing new to sync.")
        return {"synced": 0, "failed": 0}

    print(f"Found {len(new_posts)} new post(s) to sync.")
    client = make_client(api_key)
    synced = 0
    failed = 0

    for post in new_posts:
        shortcode = post["shortcode"]
        print(f"\nProcessing {shortcode}...")
        try:
            caption = rewrite_caption(post["caption"], client)
            print(f"  Caption rewritten.")
        except Exception as e:
            print(f"  Caption rewrite failed: {e} — skipping.")
            failed += 1
            continue

        success = run_post(
            images=post["images"],
            caption=caption,
            username=xhs_username,
            password=xhs_password,
            headless=headless,
        )

        if success:
            state = mark_synced(state, shortcode)
            write_state(state_path, state)
            cleanup_post_images(tmp_dir / shortcode)
            synced += 1
            print(f"  ✓ {shortcode} synced.")
        else:
            failed += 1
            print(f"  ✗ {shortcode} failed — will retry next run.")

    return {"synced": synced, "failed": failed}


def main():
    missing = validate_env(dict(os.environ))
    if missing:
        print(f"ERROR: Missing required .env keys: {', '.join(missing)}")
        print(f"Copy .env.example to .env and fill in the values.")
        sys.exit(1)

    result = run_sync(
        ig_username=os.environ["IG_USERNAME"],
        fetch_count=int(os.environ.get("IG_FETCH_COUNT", "10")),
        xhs_username=os.environ["XHS_USERNAME"],
        xhs_password=os.environ["XHS_PASSWORD"],
        api_key=os.environ["ANTHROPIC_API_KEY"],
        headless=os.environ.get("PLAYWRIGHT_HEADLESS", "false").lower() == "true",
        skill_dir=SKILL_DIR,
    )

    total = result["synced"] + result["failed"]
    print(f"\nDone. Synced {result['synced']}/{total} posts. {result['failed']} failed.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_sync.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/ig-xhs-sync/sync.py skills/ig-xhs-sync/tests/test_sync.py
git commit -m "feat: add sync.py orchestrator"
```

---

## Task 7: SKILL.md

**Files:**
- Create: `skills/ig-xhs-sync/SKILL.md`

- [ ] **Step 1: Write `SKILL.md`**

```markdown
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
```

- [ ] **Step 2: Verify SKILL.md renders correctly**

Read the file and confirm all sections are present and well-formed.

- [ ] **Step 3: Commit**

```bash
git add skills/ig-xhs-sync/SKILL.md
git commit -m "feat: add SKILL.md for ig-xhs-sync"
```

---

## Task 8: End-to-End Smoke Test

- [ ] **Step 1: Copy `.env.example` to `.env` and fill in real credentials**

```bash
cd skills/ig-xhs-sync
cp .env.example .env
# Edit .env with real IG_USERNAME, XHS credentials, ANTHROPIC_API_KEY
```

- [ ] **Step 2: Run first-time login**

```bash
python post.py --login
```

Expected: browser opens, you log in to XHS, press Enter, `xhs_session/storage.json` created.

- [ ] **Step 3: Run sync dry-run (check scraping works)**

Add a known-unsynced Instagram shortcode to verify scraping:

```bash
python -c "
from scrape import scrape_new_posts
from pathlib import Path
posts = scrape_new_posts('YOUR_IG_USERNAME', 3, [], Path('tmp'))
for p in posts:
    print(p['shortcode'], p['caption'][:50] if p['caption'] else '[no caption]')
"
```

Expected: prints 3 recent post shortcodes with captions.

- [ ] **Step 4: Run full sync**

```bash
python sync.py
```

Expected: posts appear on XHS, `state.json` updated with synced shortcodes.

- [ ] **Step 5: Run sync again to verify deduplication**

```bash
python sync.py
```

Expected: `Nothing new to sync.`

- [ ] **Step 6: Final commit**

```bash
git add skills/ig-xhs-sync/
git commit -m "feat: complete ig-xhs-sync skill — end-to-end tested"
```
