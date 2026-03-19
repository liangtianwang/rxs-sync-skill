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
