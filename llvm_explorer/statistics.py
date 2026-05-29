"""
Statistics Engine
=================
Computes per-stage IR statistics using the ir_parser module and provides
helpers to format them as Rich tables or Markdown text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rich.table import Table
from rich.text import Text

from ir_parser import (
    count_basic_blocks,
    count_branches,
    count_calls,
    count_functions,
    count_instructions,
)

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class StageStats:
    """Statistics for a single optimization stage."""

    instructions: int = 0
    functions: int = 0
    calls: int = 0
    branches: int = 0
    blocks: int = 0


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------

def compute_stats(ir_text: str) -> StageStats:
    """Compute IR statistics from raw LLVM IR text."""
    return StageStats(
        instructions=count_instructions(ir_text),
        functions=count_functions(ir_text),
        calls=count_calls(ir_text),
        branches=count_branches(ir_text),
        blocks=count_basic_blocks(ir_text),
    )


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _delta(current: int, original: int) -> Text:
    """Return a Rich Text showing the delta from original, color-coded."""
    diff = current - original
    if diff < 0:
        return Text(f" ({diff})", style="bold green")
    elif diff > 0:
        return Text(f" (+{diff})", style="bold red")
    return Text("")


def format_stats_table(
    stage_names: list[str],
    stage_stats: list[StageStats],
) -> Table:
    """Build a Rich Table comparing statistics across all stages.

    Improvements (reductions) are highlighted in green.
    """
    table = Table(
        title="Optimization Statistics",
        title_style="bold cyan",
        border_style="bright_black",
        header_style="bold magenta",
        show_lines=True,
        expand=True,
    )

    table.add_column("Stage", style="bold white", ratio=2)
    table.add_column("Instructions", justify="right", ratio=1)
    table.add_column("Functions", justify="right", ratio=1)
    table.add_column("Calls", justify="right", ratio=1)
    table.add_column("Branches", justify="right", ratio=1)
    table.add_column("Blocks", justify="right", ratio=1)

    original = stage_stats[0] if stage_stats else None

    for name, stats in zip(stage_names, stage_stats):
        if original is not None and stats is not original:
            instr_text = Text(str(stats.instructions))
            instr_text.append_text(_delta(stats.instructions, original.instructions))
            func_text = Text(str(stats.functions))
            func_text.append_text(_delta(stats.functions, original.functions))
            call_text = Text(str(stats.calls))
            call_text.append_text(_delta(stats.calls, original.calls))
            br_text = Text(str(stats.branches))
            br_text.append_text(_delta(stats.branches, original.branches))
            blk_text = Text(str(stats.blocks))
            blk_text.append_text(_delta(stats.blocks, original.blocks))
        else:
            instr_text = Text(str(stats.instructions))
            func_text = Text(str(stats.functions))
            call_text = Text(str(stats.calls))
            br_text = Text(str(stats.branches))
            blk_text = Text(str(stats.blocks))

        table.add_row(name, instr_text, func_text, call_text, br_text, blk_text)

    return table


def stats_to_markdown(
    stage_names: list[str],
    stage_stats: list[StageStats],
) -> str:
    """Render statistics as a Markdown table string."""
    lines = [
        "| Stage | Instructions | Functions | Calls | Branches | Blocks |",
        "|-------|------------:|----------:|------:|---------:|-------:|",
    ]
    for name, s in zip(stage_names, stage_stats):
        lines.append(
            f"| {name} | {s.instructions} | {s.functions} | {s.calls} "
            f"| {s.branches} | {s.blocks} |"
        )
    return "\n".join(lines)
