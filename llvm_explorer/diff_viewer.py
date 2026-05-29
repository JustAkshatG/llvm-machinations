"""
Diff Viewer Module
==================
Computes unified diffs between two LLVM IR texts and formats them for
display with Rich (colored terminal output) or as Markdown.
"""

from __future__ import annotations

import difflib

from rich.text import Text


# ---------------------------------------------------------------------------
# Diff computation
# ---------------------------------------------------------------------------

def compute_diff(
    before: str,
    after: str,
    before_label: str = "before",
    after_label: str = "after",
    context_lines: int = 3,
) -> list[str]:
    """Compute a unified diff between *before* and *after* IR texts.

    Returns a list of diff lines (strings) including the header.
    """
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    return list(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=before_label,
            tofile=after_label,
            n=context_lines,
        )
    )


# ---------------------------------------------------------------------------
# Rich formatting
# ---------------------------------------------------------------------------

def format_diff_rich(diff_lines: list[str]) -> Text:
    """Convert unified diff lines into a Rich Text object with colors.

    * Added lines   → green
    * Removed lines → red
    * Hunk headers  → cyan
    * Context       → dim white
    """
    result = Text()

    if not diff_lines:
        result.append("No differences found.", style="dim italic")
        return result

    for line in diff_lines:
        line_stripped = line.rstrip("\n")
        if line.startswith("+++") or line.startswith("---"):
            result.append(line_stripped + "\n", style="bold white")
        elif line.startswith("@@"):
            result.append(line_stripped + "\n", style="bold cyan")
        elif line.startswith("+"):
            result.append(line_stripped + "\n", style="green")
        elif line.startswith("-"):
            result.append(line_stripped + "\n", style="red")
        else:
            result.append(line_stripped + "\n", style="dim")

    return result


# ---------------------------------------------------------------------------
# Markdown formatting
# ---------------------------------------------------------------------------

def diff_to_markdown(
    before_name: str,
    after_name: str,
    diff_lines: list[str],
) -> str:
    """Render a unified diff as a Markdown fenced code block."""
    header = f"### Diff: {before_name} → {after_name}\n\n"
    if not diff_lines:
        return header + "_No differences._\n"
    body = "".join(diff_lines)
    return header + f"```diff\n{body}```\n"
