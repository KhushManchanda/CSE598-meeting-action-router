"""
agent/prompts.py
-------------------
Loads versioned prompt files from prompts/ (spec: "Prompts stored as
versioned files in prompts/, not hardcoded"). Every LLM-calling stage
(extractor, resolver, validator's grounding check, B1) loads its
system prompt through this module instead of embedding it as a Python
string constant, so:
  - the prompt text is reviewable/diffable on its own, outside code.
  - eval/run_eval.py can record a short hash of each prompt file used
    in a given run (spec: "recording model, temperature, prompt
    version hash and budgets"), so a results table can be traced back
    to the exact prompt wording that produced it.

Filenames carry an explicit version suffix (e.g. extractor_v1.md) --
bumping the version means a new file, not editing the old one in
place, so a hash recorded in an old run's metadata keeps meaning
something.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """`name` is the filename without extension, e.g. "extractor_v1"."""
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")


def prompt_hash(name: str) -> str:
    """Short (12-hex-char) sha256 hash of the prompt file's exact
    contents, for recording in run metadata/audit logs."""
    return hashlib.sha256(load_prompt(name).encode("utf-8")).hexdigest()[:12]
