import sys
from pathlib import Path

# Add the skill directory to sys.path so tests can import modules directly
# (e.g. `from state import read_state` instead of `from ig_xhs_sync.state import ...`)
sys.path.insert(0, str(Path(__file__).parent.parent))
