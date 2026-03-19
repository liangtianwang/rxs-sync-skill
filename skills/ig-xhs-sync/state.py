import json
import os
from pathlib import Path
from datetime import datetime, timezone


def read_state(state_path: Path) -> dict:
    """Read state.json; return default state if file is missing."""
    if not state_path.exists():
        return {"synced_posts": [], "last_checked": None}
    return json.loads(state_path.read_text())


def write_state(state_path: Path, state: dict) -> None:
    """Write state atomically: write to .tmp then rename."""
    tmp_path = state_path.with_name("." + state_path.name + ".tmp")
    try:
        tmp_path.write_text(json.dumps(state, indent=2))
        os.replace(tmp_path, state_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def mark_synced(state: dict, shortcode: str) -> dict:
    """Return updated state with shortcode added to synced_posts."""
    updated = dict(state)
    updated["synced_posts"] = list(state["synced_posts"]) + [shortcode]
    updated["last_checked"] = datetime.now(timezone.utc).isoformat()
    return updated
