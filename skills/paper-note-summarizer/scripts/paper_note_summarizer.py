#!/usr/bin/env python3
"""Run the project-level paper note summarizer from inside the skill."""

from __future__ import annotations

import runpy
from pathlib import Path


ROOT_SCRIPT = Path(__file__).resolve().parents[3] / "paper_note_summarizer.py"


if __name__ == "__main__":
    runpy.run_path(str(ROOT_SCRIPT), run_name="__main__")
