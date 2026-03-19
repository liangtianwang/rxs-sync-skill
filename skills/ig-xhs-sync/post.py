"""
post.py — Post content to Xiaohongshu via Playwright.

Usage:
  python post.py --login              # First-time login + save session
  (called directly by sync.py)        # Normal posting
"""
import argparse
import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv
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

        # Upload images — pass all at once (XHS supports multi-select)
        file_input = page.locator('input[type="file"]').first
        file_input.set_input_files([str(img_path) for img_path in images])
        time.sleep(2)  # wait for all uploads to register

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
        try:
            if session_path:
                context = browser.new_context(storage_state=str(session_path))
                print("  Reusing saved XHS session.")
            else:
                context = browser.new_context()

            # Verify session is valid — navigate to creator platform and check for login redirect
            page = context.new_page()
            page.goto(f"{XHS_CREATOR_URL}/publish/publish")
            page.wait_for_load_state("networkidle")
            is_logged_in = "login" not in page.url and "signin" not in page.url
            page.close()

            if not is_logged_in:
                print("  Session expired or missing — attempting credential login...")
                page = context.new_page()
                success = login_with_credentials(page, username, password)
                page.close()
                if not success:
                    return False
                save_session(context)

            return post_note(context, images, caption)
        finally:
            browser.close()


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
