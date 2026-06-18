#!/usr/bin/env python3
"""Entry point for the ANPR Edge Agent."""

import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path when running as script
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.agent import main  # noqa: E402


if __name__ == "__main__":
    asyncio.run(main())
