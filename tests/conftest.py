# tests/conftest.py

import sys
from pathlib import Path

# Compute absolute path to the project root (one folder up from tests/)
ROOT = Path(__file__).resolve().parents[1]

# Prepend project root to sys.path so "import src.download" works:
sys.path.insert(0, str(ROOT))
