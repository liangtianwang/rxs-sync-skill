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
