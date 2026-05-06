#!/usr/bin/env python3
"""Run the project-level paper note summarizer from inside the skill.

这个文件不是第二份实现，只是 Codex skill 的轻量入口。

调用关系：
- 用户显式使用 `$paper-note-summarizer` skill 时，Codex 可以运行本脚本。
- 本脚本通过相对路径找到项目根目录的 `paper_note_summarizer.py`。
- `runpy.run_path(..., run_name="__main__")` 会让根脚本像命令行直接执行一样
  进入 `main()`，因此 skill 和普通 CLI 始终复用同一套逻辑。

这样做可以避免两份代码行为不一致：修主程序即可同时修 CLI 和 skill。
"""

from __future__ import annotations

import runpy
from pathlib import Path


# 当前文件路径：
# skills/paper-note-summarizer/scripts/paper_note_summarizer.py
# parents[3] 正好回到项目根目录，再拼出真正的主程序。
ROOT_SCRIPT = Path(__file__).resolve().parents[3] / "paper_note_summarizer.py"


if __name__ == "__main__":
    runpy.run_path(str(ROOT_SCRIPT), run_name="__main__")
