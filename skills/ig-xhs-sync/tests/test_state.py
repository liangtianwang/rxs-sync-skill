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
