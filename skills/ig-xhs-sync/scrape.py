import itertools
import instaloader
import shutil
from pathlib import Path


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
    if not images:
        raise RuntimeError(
            f"No images found in {post_dir} after download — "
            f"post {post.shortcode} may have failed to download"
        )
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
    recent_posts = list(itertools.islice(profile.get_posts(), fetch_count))
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
