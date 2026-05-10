"""Prompt loader for MCP tool system prompts.

Per CLAUDE.md: every prompt lives in `*/prompts/*.md` with YAML frontmatter
(version, model, temperature, max_output_tokens). Tools import the loaded
text at module import time so the server can fail fast if a prompt file is
missing.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@lru_cache(maxsize=32)
def load(name: str) -> str:
    """Load a prompt by file stem (no .md). YAML frontmatter is stripped.

    Args:
        name: Filename without extension, e.g. "triage" for prompts/triage.md.

    Returns:
        The prompt body text, frontmatter removed and leading whitespace stripped.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
    """
    path = PROMPTS_DIR / f"{name}.md"
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4 :].lstrip()
    return text
