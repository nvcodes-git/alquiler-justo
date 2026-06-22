"""Pytest config: asegura que la raíz del repo esté en sys.path."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
