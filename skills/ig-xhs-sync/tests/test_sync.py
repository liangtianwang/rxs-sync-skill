from unittest.mock import MagicMock, patch
from pathlib import Path

from sync import REQUIRED_ENV_KEYS


def test_validate_env_all_present():
    """No missing keys returns empty list."""
    from sync import validate_env
    env = {k: "value" for k in REQUIRED_ENV_KEYS}
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
    mock_write.assert_not_called()


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
         patch("sync.cleanup_post_images") as mock_cleanup, \
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
    mock_cleanup.assert_called_once()


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


def test_sync_rewrite_failure_not_marked_synced(tmp_path):
    """When rewrite_caption raises an exception, the post is counted as failed and state is not written."""
    from sync import run_sync
    mock_post = {
        "shortcode": "ERR1",
        "images": [tmp_path / "img.jpg"],
        "caption": "hello",
        "timestamp": "2026-03-19T10:00:00",
    }
    with patch("sync.scrape_new_posts", return_value=[mock_post]), \
         patch("sync.read_state", return_value={"synced_posts": [], "last_checked": None}), \
         patch("sync.rewrite_caption", side_effect=RuntimeError("API error")), \
         patch("sync.write_state") as mock_write, \
         patch("sync.make_client", return_value=MagicMock()):
        result = run_sync(
            ig_username="user", fetch_count=10,
            xhs_username="xhs", xhs_password="pw",
            api_key="key", headless=False, skill_dir=tmp_path,
        )
    assert result["failed"] == 1
    assert result["synced"] == 0
    mock_write.assert_not_called()
