"""conftest.py for the coding-0 worktree.

Sets up proper sys.path so dashboard modules can be imported correctly
when running pytest from the worktree directory.
"""
import sys
from pathlib import Path

# coding-0 worktree root
_WORKTREE_ROOT = Path(__file__).parent

# Ensure the worktree root is on sys.path for module imports
if str(_WORKTREE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKTREE_ROOT))
