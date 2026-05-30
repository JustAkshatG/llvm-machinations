#!/usr/bin/env python3
"""
Headless Evaluation Script
===========================
Runs the LLVM optimization pipeline on all test cases (without the TUI)
and produces a formatted metrics comparison table.

Usage::

    python scripts/evaluate.py                  # Run all testcases/
    python scripts/evaluate.py testcases/test1_basic_inline_dce.c   # Single file
    python scripts/evaluate.py --markdown       # Output as Markdown table

This script is called by ``./run.sh --evaluate``.
"""

from __future__ import annotations

import argparse
import sys
import shutil
from pathlib import Path

# Add the llvm_explorer source directory to the Python path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "llvm_explorer"))

from pipeline import OptimizationPipeline, LLVMToolError  # noqa: E402
from file_manager import validate_c_file, ensure_output_dir, FileValidationError  # noqa: E402


# ── Colors (for terminal output) ────────────────────────────────────────────

class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    END = "\033[0m"


# ── Main evaluation logic ──────────────────────────────────────────────────

def evaluate_file(
    pipeline: OptimizationPipeline,
    c_file: Path,
    output_base: Path,
) -> dict | None:
    """Run the pipeline on a single C file and return metrics.

    Returns a dict with per-stage stats, or None on failure.
    """
    try:
        validated = validate_c_file(c_file)
    except FileValidationError as exc:
        print(f"  {Colors.RED}SKIP{Colors.END} {c_file.name}: {exc}")
        return None

    # Each test case gets its own output subdirectory
    case_output = output_base / c_file.stem
    try:
        original_c, stages = pipeline.run(validated, case_output)
    except LLVMToolError as exc:
        print(f"  {Colors.RED}FAIL{Colors.END} {c_file.name}: {exc}")
        return None
    except Exception as exc:
        print(f"  {Colors.RED}ERROR{Colors.END} {c_file.name}: {exc}")
        return None

    result = {
        "file": c_file.name,
        "stages": [],
    }
    for stage in stages:
        result["stages"].append({
            "name": stage.name,
            "instructions": stage.stats.instructions,
            "functions": stage.stats.functions,
            "calls": stage.stats.calls,
            "branches": stage.stats.branches,
            "blocks": stage.stats.blocks,
        })

    return result


def print_results_table(results: list[dict], markdown: bool = False) -> None:
    """Print a formatted comparison table."""
    if not results:
        print("No results to display.")
        return

    stage_names = ["Original", "Inline", "SCCP", "SimplifyCFG", "DCE"]

    if markdown:
        _print_markdown_table(results, stage_names)
    else:
        _print_terminal_table(results, stage_names)


def _print_terminal_table(results: list[dict], stage_names: list[str]) -> None:
    """Print a colored terminal table."""
    C = Colors

    # ── Per-test-case detail tables ─────────────────────────────────────
    for res in results:
        file_name = res["file"]
        stages = res["stages"]
        original = stages[0]["instructions"]
        final = stages[-1]["instructions"]
        removed = original - final
        pct = (removed / original * 100) if original else 0

        print(f"\n{C.BOLD}{C.CYAN}{'═' * 70}{C.END}")
        print(f"{C.BOLD}  {file_name}{C.END}")
        print(f"{C.CYAN}{'═' * 70}{C.END}")
        print(
            f"  {'Stage':<14} {'Instr':>7} {'Funcs':>7} {'Calls':>7} "
            f"{'Branch':>7} {'Blocks':>7} {'Δ Instr':>8}"
        )
        print(f"  {'─' * 62}")

        for s in stages:
            delta = s["instructions"] - original
            if delta < 0:
                delta_str = f"{C.GREEN}{delta}{C.END}"
            elif delta > 0:
                delta_str = f"{C.RED}+{delta}{C.END}"
            else:
                delta_str = f"{C.DIM}  0{C.END}"

            print(
                f"  {s['name']:<14} {s['instructions']:>7} {s['functions']:>7} "
                f"{s['calls']:>7} {s['branches']:>7} {s['blocks']:>7} "
                f"{delta_str:>17}"
            )

        print(f"  {'─' * 62}")
        color = C.GREEN if removed > 0 else (C.YELLOW if removed == 0 else C.RED)
        print(
            f"  {color}{C.BOLD}Result: {removed} instructions removed "
            f"({pct:.1f}% reduction){C.END}"
        )

    # ── Summary table ──────────────────────────────────────────────────
    print(f"\n{C.BOLD}{C.CYAN}{'═' * 70}{C.END}")
    print(f"{C.BOLD}  SUMMARY — All Test Cases{C.END}")
    print(f"{C.CYAN}{'═' * 70}{C.END}")
    print(
        f"  {'Test Case':<35} {'Before':>7} {'After':>7} "
        f"{'Removed':>8} {'Reduction':>10}"
    )
    print(f"  {'─' * 62}")

    total_before = 0
    total_after = 0

    for res in results:
        name = res["file"]
        before = res["stages"][0]["instructions"]
        after = res["stages"][-1]["instructions"]
        removed = before - after
        pct = (removed / before * 100) if before else 0
        total_before += before
        total_after += after

        color = C.GREEN if removed > 0 else C.YELLOW
        print(
            f"  {name:<35} {before:>7} {after:>7} "
            f"{color}{removed:>8}{C.END} {color}{pct:>9.1f}%{C.END}"
        )

    print(f"  {'─' * 62}")
    total_removed = total_before - total_after
    total_pct = (total_removed / total_before * 100) if total_before else 0
    print(
        f"  {C.BOLD}{'TOTAL':<35} {total_before:>7} {total_after:>7} "
        f"{C.GREEN}{total_removed:>8}{C.END} {C.GREEN}{C.BOLD}{total_pct:>9.1f}%{C.END}"
    )
    print()


def _print_markdown_table(results: list[dict], stage_names: list[str]) -> None:
    """Print results as Markdown tables (for EVALUATION.md)."""
    # ── Per-test detail ─────────────────────────────────────────────────
    for res in results:
        file_name = res["file"]
        stages = res["stages"]
        original = stages[0]["instructions"]

        print(f"\n### {file_name}\n")
        print("| Stage | Instructions | Functions | Calls | Branches | Blocks | Δ Instructions |")
        print("|-------|------------:|----------:|------:|---------:|-------:|---------------:|")

        for s in stages:
            delta = s["instructions"] - original
            delta_str = f"{delta:+d}" if delta != 0 else "—"
            print(
                f"| {s['name']} | {s['instructions']} | {s['functions']} | "
                f"{s['calls']} | {s['branches']} | {s['blocks']} | {delta_str} |"
            )

        final = stages[-1]["instructions"]
        removed = original - final
        pct = (removed / original * 100) if original else 0
        print(f"\n**Result:** {removed} instructions removed ({pct:.1f}% reduction)\n")

    # ── Summary ─────────────────────────────────────────────────────────
    print("\n## Summary\n")
    print("| Test Case | Original | Final | Removed | Reduction |")
    print("|-----------|--------:|------:|--------:|----------:|")

    for res in results:
        name = res["file"]
        before = res["stages"][0]["instructions"]
        after = res["stages"][-1]["instructions"]
        removed = before - after
        pct = (removed / before * 100) if before else 0
        print(f"| {name} | {before} | {after} | {removed} | {pct:.1f}% |")

    print()


# ── Entry point ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate LLVM optimization pipeline on test cases.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Specific C files to evaluate (default: all in testcases/)",
    )
    parser.add_argument(
        "--markdown", "-m",
        action="store_true",
        help="Output results as Markdown tables",
    )
    args = parser.parse_args()

    # Determine which files to evaluate
    if args.files:
        c_files = [Path(f) for f in args.files]
    else:
        testcases_dir = _ROOT / "testcases"
        examples_dir = _ROOT / "llvm_explorer" / "examples"
        c_files = sorted(testcases_dir.glob("*.c"))
        c_files.extend(sorted(examples_dir.glob("*.c")))

    if not c_files:
        print("No test case files found.")
        sys.exit(1)

    # Check LLVM tools
    if not shutil.which("clang") or not shutil.which("opt"):
        print(
            f"{Colors.RED}ERROR:{Colors.END} clang and opt must be in PATH.\n"
            "Install LLVM and try again."
        )
        sys.exit(1)

    # Output directory for evaluation artifacts
    output_base = _ROOT / "evaluation_output"
    output_base.mkdir(parents=True, exist_ok=True)

    print(f"\n{Colors.BOLD}LLVM Optimization Explorer — Evaluation Suite{Colors.END}")
    print(f"{'─' * 50}")
    print(f"  Test cases: {len(c_files)}")
    print(f"  Output dir: {output_base}")
    print()

    # Run pipeline on each file
    pipeline = OptimizationPipeline()
    results = []

    for c_file in c_files:
        print(f"  Processing {c_file.name}...", end=" ", flush=True)
        result = evaluate_file(pipeline, c_file, output_base)
        if result:
            results.append(result)
            original = result["stages"][0]["instructions"]
            final = result["stages"][-1]["instructions"]
            removed = original - final
            print(f"{Colors.GREEN}OK{Colors.END} ({removed} instructions removed)")
        else:
            print()  # error already printed

    # Display results
    print_results_table(results, markdown=args.markdown)


if __name__ == "__main__":
    main()
