#!/usr/bin/env python3
"""Repository-local CLI bootstrap, never used as a sudo entry point."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sretoolkit.runner import main

if __name__ == "__main__":
    sys.exit(main())
