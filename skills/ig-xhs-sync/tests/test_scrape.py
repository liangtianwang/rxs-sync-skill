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
