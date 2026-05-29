"""
LLVM IR Parser Module
=====================
Provides functions to count various LLVM IR constructs (instructions, functions,
calls, branches, basic blocks) from raw IR text.  Used by the statistics engine
to track how each optimization pass transforms the program.
"""

from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# Regex patterns for LLVM IR constructs
# ---------------------------------------------------------------------------

# Matches lines that are LLVM instructions:
#   %result = <opcode> ...        (assignment form)
#   store / ret / br / switch ... (standalone, indented)
# Excludes: comments, metadata, labels, blank lines, declarations, attributes
_INSTRUCTION_RE = re.compile(
    r"^\s+"           # leading whitespace (instructions are indented)
    r"(?!"            # negative lookahead — skip non-instruction lines
    r"!|;"            # metadata / comments
    r")"
    r"("
    r"%[\w.]+ \s*=\s* \w+"   # assignment form:  %x = add ...
    r"|"
    r"(?:store|ret|br|switch|unreachable|resume|invoke|indirectbr|callbr|"
    r"fence|cmpxchg|atomicrmw|call|tail\s+call|musttail\s+call|notail\s+call)"
    r")",
    re.VERBOSE,
)

# Matches function definitions: `define ... @name(`
_FUNCTION_DEF_RE = re.compile(r"^\s*define\s+", re.MULTILINE)

# Matches call instructions (including tail call variants)
_CALL_RE = re.compile(
    r"^\s+(?:%[\w.]+ \s*=\s*)?"  # optional assignment
    r"(?:tail\s+|musttail\s+|notail\s+)?"
    r"call\s+",
    re.MULTILINE | re.VERBOSE,
)

# Matches branch instructions
_BRANCH_RE = re.compile(r"^\s+br\s+", re.MULTILINE)

# Matches basic block labels  (e.g.  `entry:`, `if.then:`, `42:`)
_LABEL_RE = re.compile(r"^[\w.]+:\s*(?:;.*)?$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Public counting functions
# ---------------------------------------------------------------------------

def count_instructions(ir_text: str) -> int:
    """Count the number of LLVM IR instructions in the given text.

    Counts both assignment-form instructions (%x = ...) and standalone
    instructions (store, ret, br, call, etc.).
    """
    count = 0
    for line in ir_text.splitlines():
        stripped = line.rstrip()
        if not stripped or stripped.startswith(";") or stripped.startswith("!"):
            continue
        # Instructions are indented
        if line and line[0] in (" ", "\t"):
            # Skip metadata-only lines and pure comments
            content = stripped.lstrip()
            if content.startswith(";") or content.startswith("!"):
                continue
            # Skip label lines inside function bodies
            if _LABEL_RE.match(content):
                continue
            # Anything else indented inside a function is an instruction
            if content:
                count += 1
    return count


def count_functions(ir_text: str) -> int:
    """Count the number of function definitions (`define ...`)."""
    return len(_FUNCTION_DEF_RE.findall(ir_text))


def count_calls(ir_text: str) -> int:
    """Count the number of `call` instructions (including tail call variants)."""
    return len(_CALL_RE.findall(ir_text))


def count_branches(ir_text: str) -> int:
    """Count the number of `br` (branch) instructions."""
    return len(_BRANCH_RE.findall(ir_text))


def count_basic_blocks(ir_text: str) -> int:
    """Count basic blocks.

    Each label line is one basic block.  In addition, each ``define``
    implicitly starts an entry basic block, so we add one per function
    definition.
    """
    labels = len(_LABEL_RE.findall(ir_text))
    functions = count_functions(ir_text)
    return labels + functions
