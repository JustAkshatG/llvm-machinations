"""
Optimization Pipeline Module
=============================
Orchestrates the execution of LLVM optimization passes via the ``opt``
command-line tool.  Compiles C source files to LLVM IR using ``clang``,
runs each optimization pass, and generates a reconstructed pseudo-C
representation at every stage using the C reconstructor.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from c_reconstructor import CReconstructor
from statistics import StageStats, compute_stats


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class LLVMToolError(Exception):
    """Raised when an LLVM tool is missing or a pass execution fails."""


# ---------------------------------------------------------------------------
# Educational explanations for each pass
# ---------------------------------------------------------------------------

EXPLANATIONS: dict[str, str] = {
    "Original": (
        "This is the unoptimized LLVM IR produced by clang with -O0.\n"
        "It faithfully represents the C source program but contains many\n"
        "redundancies: every variable is stack-allocated (alloca), loaded\n"
        "and stored through pointers, and no optimizations are applied.\n"
        "\n"
        "Compare the Original C (left) with the Reconstructed C (right)\n"
        "to see how the IR-level representation differs from the source."
    ),
    "Inline": (
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║              FUNCTION INLINING  (inline)                   ║\n"
        "╚══════════════════════════════════════════════════════════════╝\n"
        "\n"
        "Function inlining copies the body of a called function directly\n"
        "into the caller, replacing the `call` instruction.  This:\n"
        "\n"
        "  • Eliminates call/return overhead\n"
        "  • Exposes the callee's code to the caller's optimization context\n"
        "  • Enables further constant propagation, dead code elimination,\n"
        "    and branch simplification\n"
        "\n"
        "KEY INSIGHT: Before inlining, the compiler cannot see through\n"
        "the call boundary.  After inlining, constant arguments become\n"
        "visible in the caller, enabling SCCP and DCE.\n"
        "\n"
        "Look at the Reconstructed C — the function call is gone!"
    ),
    "SCCP": (
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║     SPARSE CONDITIONAL CONSTANT PROPAGATION  (sccp)        ║\n"
        "╚══════════════════════════════════════════════════════════════╝\n"
        "\n"
        "SCCP combines two analyses:\n"
        "\n"
        "  1. Constant Propagation — tracks which SSA values are provably\n"
        "     constant and replaces their uses with the constant value.\n"
        "\n"
        "  2. Conditional Constant Propagation — determines which branches\n"
        "     have constant conditions, marking unreachable blocks as dead.\n"
        "\n"
        "The 'sparse' qualifier means it operates on the SSA def-use graph\n"
        "rather than iterating over all instructions, making it efficient.\n"
        "\n"
        "Look at the Reconstructed C — constants have replaced variables!"
    ),
    "SimplifyCFG": (
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║       CONTROL FLOW GRAPH SIMPLIFICATION  (simplifycfg)     ║\n"
        "╚══════════════════════════════════════════════════════════════╝\n"
        "\n"
        "SimplifyCFG cleans up the control flow graph by:\n"
        "\n"
        "  • Merging basic blocks with a single predecessor/successor\n"
        "  • Removing unconditional branches to the next block\n"
        "  • Folding branches with constant conditions\n"
        "  • Eliminating empty basic blocks\n"
        "  • Converting switches with few cases to branches\n"
        "\n"
        "This pass often runs after SCCP to clean up the newly-dead branches\n"
        "that constant propagation revealed.\n"
        "\n"
        "Look at the Reconstructed C — dead branches are gone!"
    ),
    "DCE": (
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║           DEAD CODE ELIMINATION  (dce)                     ║\n"
        "╚══════════════════════════════════════════════════════════════╝\n"
        "\n"
        "DCE removes instructions whose results are never used and that\n"
        "have no observable side effects.  An instruction is 'dead' if:\n"
        "\n"
        "  • No other instruction uses its result (%value)\n"
        "  • It does not write to memory or perform I/O\n"
        "\n"
        "After inlining and constant propagation, many intermediate\n"
        "computations become dead because their original consumers were\n"
        "replaced with constants.\n"
        "\n"
        "Look at the Reconstructed C — unused computations are removed!"
    ),
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class OptimizationStage:
    """Represents one stage in the optimization pipeline."""

    name: str
    pass_name: Optional[str]      # None for the original
    output_file: Path
    ir_content: str = ""
    reconstructed_c: str = ""     # Pseudo-C reconstruction of this stage
    stats: StageStats = field(default_factory=StageStats)
    explanation: str = ""


# ---------------------------------------------------------------------------
# Pass definitions
# ---------------------------------------------------------------------------

# (stage_name, opt_pass_flag, output_filename)
PASSES: list[tuple[str, str, str]] = [
    ("Inline",      "inline",      "1_inline.ll"),
    ("SCCP",        "sccp",        "2_sccp.ll"),
    ("SimplifyCFG", "simplifycfg", "3_simplifycfg.ll"),
    ("DCE",         "dce",         "4_dce.ll"),
]


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class OptimizationPipeline:
    """Runs the LLVM optimization pipeline on a C source file.

    Workflow::

        1. Compile C → LLVM IR using clang -S -emit-llvm -O0
        2. Run opt passes sequentially
        3. Generate reconstructed pseudo-C at each stage

    Usage::

        pipeline = OptimizationPipeline()
        original_c, stages = pipeline.run(Path("input.c"), Path("output/"))
    """

    def __init__(self) -> None:
        self._clang_path = self._find_tool("clang")
        self._opt_path = self._find_tool("opt")
        self._reconstructor = CReconstructor()

    @staticmethod
    def _find_tool(name: str) -> str:
        """Locate a tool binary or raise a clear error."""
        path = shutil.which(name)
        if path is None:
            raise LLVMToolError(
                f"The '{name}' tool was not found in PATH.\n"
                "\n"
                "On Arch Linux:   sudo pacman -S llvm clang\n"
                "On Ubuntu/Debian: sudo apt install llvm clang\n"
                "On macOS (brew):  brew install llvm\n"
                "\n"
                f"Make sure '{name}' is accessible in your $PATH."
            )
        return path

    def run(
        self,
        input_path: Path,
        output_dir: Path,
    ) -> tuple[str, list[OptimizationStage]]:
        """Execute the full optimization pipeline.

        Parameters
        ----------
        input_path : Path
            Path to the input ``.c`` file.
        output_dir : Path
            Directory to store intermediate ``.ll`` and reconstructed ``.c``
            outputs.

        Returns
        -------
        tuple[str, list[OptimizationStage]]
            The original C source text, and a list of 5 stages
            (original + 4 passes).
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Read original C source
        original_c = input_path.read_text(encoding="utf-8")

        # Step 1: Compile C → LLVM IR
        raw_ll = output_dir / "0_raw.ll"
        self._compile_c_to_ir(input_path, raw_ll)

        # Step 2: Strip 'noinline' attribute (added by -O0) so that
        # the inline pass can actually inline functions, and run
        # mem2reg to promote stack allocas to clean SSA form.
        raw_ir = raw_ll.read_text(encoding="utf-8")
        raw_ir = raw_ir.replace(" noinline", "")
        raw_ll.write_text(raw_ir, encoding="utf-8")

        original_ll = output_dir / "0_original.ll"
        self._run_pass("mem2reg", raw_ll, original_ll)

        original_ir = original_ll.read_text(encoding="utf-8")
        original_reconstructed = self._reconstructor.reconstruct(original_ir)

        # Save reconstructed C
        (output_dir / "0_original_reconstructed.c").write_text(
            original_reconstructed, encoding="utf-8",
        )

        original_stage = OptimizationStage(
            name="Original",
            pass_name=None,
            output_file=original_ll,
            ir_content=original_ir,
            reconstructed_c=original_reconstructed,
            stats=compute_stats(original_ir),
            explanation=EXPLANATIONS["Original"],
        )

        stages: list[OptimizationStage] = [original_stage]
        prev_file = original_ll

        # Steps 2–5: optimization passes
        for idx, (stage_name, pass_flag, out_filename) in enumerate(PASSES, 1):
            out_file = output_dir / out_filename
            self._run_pass(pass_flag, prev_file, out_file)

            content = out_file.read_text(encoding="utf-8")
            reconstructed = self._reconstructor.reconstruct(content)

            # Save reconstructed C
            recon_filename = f"{idx}_{pass_flag}_reconstructed.c"
            (output_dir / recon_filename).write_text(
                reconstructed, encoding="utf-8",
            )

            stage = OptimizationStage(
                name=stage_name,
                pass_name=pass_flag,
                output_file=out_file,
                ir_content=content,
                reconstructed_c=reconstructed,
                stats=compute_stats(content),
                explanation=EXPLANATIONS.get(stage_name, ""),
            )
            stages.append(stage)
            prev_file = out_file

        return original_c, stages

    def _compile_c_to_ir(
        self,
        c_file: Path,
        output_ll: Path,
        timeout: int = 30,
    ) -> None:
        """Compile a C source file to LLVM IR using clang.

        Uses ``-O0`` to generate unoptimized IR so that each pass
        has maximum effect.
        """
        cmd = [
            self._clang_path,
            "-S", "-emit-llvm",
            "-O0",
            "-Xclang", "-disable-O0-optnone",  # Allow opt passes to work on -O0 IR
            "-o", str(output_ll),
            str(c_file),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise LLVMToolError(
                f"Clang compilation timed out after {timeout}s."
            ) from exc
        except FileNotFoundError as exc:
            raise LLVMToolError(
                f"Could not execute 'clang': {exc}"
            ) from exc

        if result.returncode != 0:
            raise LLVMToolError(
                f"Clang compilation failed (exit code {result.returncode}):\n"
                f"{result.stderr.strip()}"
            )

    def _run_pass(
        self,
        pass_name: str,
        input_file: Path,
        output_file: Path,
        timeout: int = 30,
    ) -> None:
        """Execute a single ``opt`` pass.

        Raises ``LLVMToolError`` on failure.
        """
        cmd = [
            self._opt_path,
            f"-passes={pass_name}",
            "-S",
            "-o", str(output_file),
            str(input_file),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise LLVMToolError(
                f"Pass '{pass_name}' timed out after {timeout}s."
            ) from exc
        except FileNotFoundError as exc:
            raise LLVMToolError(
                f"Could not execute 'opt': {exc}"
            ) from exc

        if result.returncode != 0:
            raise LLVMToolError(
                f"Pass '{pass_name}' failed (exit code {result.returncode}):\n"
                f"{result.stderr.strip()}"
            )
