#!/usr/bin/env python3
"""
LLVM Optimization Explorer — Interactive TUI Application
=========================================================
A Textual-based terminal application that demonstrates how LLVM optimization
passes transform C code step-by-step, showing Original C, LLVM IR, and
Reconstructed C side-by-side.

Usage::

    python app.py examples/sample1.c
    python app.py /path/to/your/file.c

Key bindings:
    1-5         Jump to stage (Original / Inline / SCCP / SimplifyCFG / DCE)
    ← →         Previous / Next stage
    d           Toggle IR diff panel
    c           Toggle Reconstructed C diff panel
    s           Toggle statistics panel
    h           Toggle help / explanation panel
    p           Enter / exit presentation mode
    e           Export Markdown report
    q           Quit
"""

from __future__ import annotations

import sys
from pathlib import Path

from rich.syntax import Syntax
from rich.text import Text

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Footer, Header, Static, RichLog, Label

# Local modules (same directory)
from pipeline import OptimizationPipeline, OptimizationStage, LLVMToolError
from file_manager import (
    FileValidationError,
    validate_c_file,
    ensure_output_dir,
    generate_report,
)
from diff_viewer import compute_diff, format_diff_rich
from statistics import format_stats_table


# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

STAGE_NAMES = ["Original", "Inline", "SCCP", "SimplifyCFG", "DCE"]

# CSS styling for the entire application
APP_CSS = """
/* ── Global ────────────────────────────────────────────────────────── */

Screen {
    background: $surface;
}

/* ── Timeline Sidebar ──────────────────────────────────────────────── */

#sidebar {
    width: 22;
    dock: left;
    background: $panel;
    border-right: thick $accent;
    padding: 1 0;
}

#sidebar-title {
    text-align: center;
    text-style: bold;
    color: $accent;
    padding: 0 1 1 1;
}

.timeline-item {
    padding: 0 1;
    height: 3;
    content-align: center middle;
}

.timeline-item.active {
    background: $accent 20%;
    text-style: bold;
    color: $text;
}

.timeline-item.inactive {
    color: $text-muted;
}

.timeline-arrow {
    text-align: center;
    color: $accent 60%;
    height: 1;
}

/* ── Three-Panel Content Area ──────────────────────────────────────── */

#main-area {
    width: 1fr;
}

#panels-row {
    height: 1fr;
}

/* Original C panel (left) */
#original-c-panel {
    width: 1fr;
    border: round $success;
    padding: 0 1;
}

#original-c-title {
    dock: top;
    text-style: bold;
    color: $success;
    padding: 0 1;
    background: $panel;
}

#original-c-viewer {
    height: 1fr;
}

/* LLVM IR panel (center) */
#ir-panel {
    width: 1fr;
    border: round $accent;
    padding: 0 1;
}

#ir-panel-title {
    dock: top;
    text-style: bold;
    color: $accent;
    padding: 0 1;
    background: $panel;
}

#ir-viewer {
    height: 1fr;
}

/* Reconstructed C panel (right) */
#recon-c-panel {
    width: 1fr;
    border: round $warning;
    padding: 0 1;
}

#recon-c-title {
    dock: top;
    text-style: bold;
    color: $warning;
    padding: 0 1;
    background: $panel;
}

#recon-c-viewer {
    height: 1fr;
}

/* ── Bottom Panel (diff / stats / help) ────────────────────────────── */

#bottom-panel {
    height: 16;
    border: round $secondary;
    padding: 0 1;
    display: none;
}

#bottom-panel.visible {
    display: block;
}

#bottom-panel-title {
    dock: top;
    text-style: bold;
    color: $secondary;
    padding: 0 1;
    background: $panel;
}

#bottom-viewer {
    height: 1fr;
}

/* ── Presentation Mode ─────────────────────────────────────────────── */

.presentation #sidebar {
    display: none;
}

.presentation #original-c-panel {
    display: none;
}

.presentation #bottom-panel {
    display: none;
}

.presentation #ir-panel {
    border: heavy $accent;
}

.presentation #recon-c-panel {
    border: heavy $warning;
}

/* ── Status Bar ────────────────────────────────────────────────────── */

#status-bar {
    dock: bottom;
    height: 1;
    background: $accent;
    color: $text;
    text-align: center;
    text-style: bold;
    padding: 0 2;
}

/* ── Notification Toast ────────────────────────────────────────────── */

Toast {
    background: $panel;
    color: $text;
}
"""


# ═══════════════════════════════════════════════════════════════════════════
# Timeline Sidebar Widget
# ═══════════════════════════════════════════════════════════════════════════

class TimelineSidebar(Static):
    """Vertical timeline showing the optimization stages."""

    current_stage: reactive[int] = reactive(0, recompose=True)

    def compose(self) -> ComposeResult:
        yield Label("⚡ Pipeline", id="sidebar-title")
        for i, name in enumerate(STAGE_NAMES):
            cls = "active" if i == self.current_stage else "inactive"
            marker = "▶ " if i == self.current_stage else "  "
            yield Label(
                f"{marker}{i + 1}. {name}",
                classes=f"timeline-item {cls}",
            )
            if i < len(STAGE_NAMES) - 1:
                yield Label("    ↓", classes="timeline-arrow")


# ═══════════════════════════════════════════════════════════════════════════
# Main Application
# ═══════════════════════════════════════════════════════════════════════════

class LLVMExplorerApp(App):
    """Interactive LLVM Optimization Explorer with three-panel display."""

    TITLE = "LLVM Optimization Explorer"
    SUB_TITLE = "C → LLVM IR → Reconstructed C"
    CSS = APP_CSS

    BINDINGS = [
        Binding("1", "stage(0)", "Original", show=True),
        Binding("2", "stage(1)", "Inline", show=True),
        Binding("3", "stage(2)", "SCCP", show=True),
        Binding("4", "stage(3)", "SimplifyCFG", show=True),
        Binding("5", "stage(4)", "DCE", show=True),
        Binding("left", "prev_stage", "← Prev", show=True),
        Binding("right", "next_stage", "Next →", show=True),
        Binding("d", "toggle_diff", "IR Diff", show=True),
        Binding("c", "toggle_c_diff", "C Diff", show=True),
        Binding("s", "toggle_stats", "Stats", show=True),
        Binding("h", "toggle_help", "Help", show=True),
        Binding("p", "toggle_presentation", "Present", show=True),
        Binding("e", "export_report", "Export", show=True),
        Binding("space", "next_stage", "Next (Presentation)", show=False),
        Binding("backspace", "prev_stage", "Prev (Presentation)", show=False),
        Binding("q", "quit", "Quit", show=True),
    ]

    # Reactive state
    current_stage: reactive[int] = reactive(0)
    # "none", "diff", "c_diff", "stats", "help"
    bottom_mode: reactive[str] = reactive("none")
    presentation_mode: reactive[bool] = reactive(False)

    def __init__(self, input_file: str) -> None:
        super().__init__()
        self.input_file = input_file
        self.stages: list[OptimizationStage] = []
        self.original_c: str = ""
        self.output_dir = Path(__file__).parent / "output"

    # ── Compose ────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield TimelineSidebar(id="sidebar")
            with Vertical(id="main-area"):
                with Horizontal(id="panels-row"):
                    # Left panel: Original C source
                    with Vertical(id="original-c-panel"):
                        yield Label("  Original C Source", id="original-c-title")
                        yield RichLog(
                            id="original-c-viewer",
                            highlight=True,
                            markup=True,
                            wrap=False,
                        )
                    # Center panel: LLVM IR
                    with Vertical(id="ir-panel"):
                        yield Label("  LLVM IR", id="ir-panel-title")
                        yield RichLog(
                            id="ir-viewer",
                            highlight=True,
                            markup=True,
                            wrap=False,
                        )
                    # Right panel: Reconstructed C
                    with Vertical(id="recon-c-panel"):
                        yield Label("  Reconstructed C", id="recon-c-title")
                        yield RichLog(
                            id="recon-c-viewer",
                            highlight=True,
                            markup=True,
                            wrap=False,
                        )
                with VerticalScroll(id="bottom-panel"):
                    yield Label("", id="bottom-panel-title")
                    yield RichLog(
                        id="bottom-viewer",
                        highlight=True,
                        markup=True,
                        wrap=False,
                    )
        yield Static("", id="status-bar")
        yield Footer()

    # ── Lifecycle ──────────────────────────────────────────────────────

    def on_mount(self) -> None:
        """Run the optimization pipeline after the UI is ready."""
        self.run_pipeline()

    @work(thread=True)
    def run_pipeline(self) -> None:
        """Execute the pipeline in a background thread."""
        try:
            validated = validate_c_file(self.input_file)
        except FileValidationError as exc:
            self.call_from_thread(self._show_error, str(exc))
            return

        try:
            pipeline = OptimizationPipeline()
            output_dir = ensure_output_dir(self.output_dir)
            self.original_c, self.stages = pipeline.run(validated, output_dir)
        except LLVMToolError as exc:
            self.call_from_thread(self._show_error, str(exc))
            return
        except Exception as exc:
            self.call_from_thread(
                self._show_error,
                f"Unexpected error: {exc}",
            )
            return

        self.call_from_thread(self._pipeline_done)

    def _show_error(self, message: str) -> None:
        """Display an error in the IR viewer panel."""
        viewer = self.query_one("#ir-viewer", RichLog)
        viewer.clear()
        error_text = Text()
        error_text.append("✖ Error\n\n", style="bold red")
        error_text.append(message, style="red")
        viewer.write(error_text)
        self._update_status("Error — see IR panel for details")

    def _pipeline_done(self) -> None:
        """Called when the pipeline completes successfully."""
        # Render original C (static — doesn't change with stages)
        self._render_original_c()

        self._update_status(
            f"Loaded {len(self.stages)} stages from: {self.input_file}"
        )
        self._render_current_stage()
        self.notify(
            "Pipeline complete! Use 1-5 or ←→ to navigate stages.",
            title="Ready",
            timeout=4,
        )

    # ── Original C rendering (static) ─────────────────────────────────

    def _render_original_c(self) -> None:
        """Render the original C source in the left panel (once)."""
        viewer = self.query_one("#original-c-viewer", RichLog)
        viewer.clear()
        syntax = Syntax(
            self.original_c,
            "c",
            theme="monokai",
            line_numbers=True,
            word_wrap=False,
        )
        viewer.write(syntax)

    # ── Stage rendering ───────────────────────────────────────────────

    def _render_current_stage(self) -> None:
        """Render the IR and Reconstructed C for the current stage."""
        if not self.stages:
            return

        stage = self.stages[self.current_stage]

        # Update timeline sidebar
        sidebar = self.query_one(TimelineSidebar)
        sidebar.current_stage = self.current_stage

        # Update IR viewer (center panel)
        ir_viewer = self.query_one("#ir-viewer", RichLog)
        ir_viewer.clear()

        ir_title = self.query_one("#ir-panel-title", Label)
        ir_title.update(
            f"  LLVM IR — Stage {self.current_stage + 1}/5: {stage.name}"
        )

        syntax = Syntax(
            stage.ir_content,
            "llvm",
            theme="monokai",
            line_numbers=True,
            word_wrap=False,
        )
        ir_viewer.write(syntax)

        # Update Reconstructed C viewer (right panel)
        recon_viewer = self.query_one("#recon-c-viewer", RichLog)
        recon_viewer.clear()

        recon_title = self.query_one("#recon-c-title", Label)
        recon_title.update(
            f"  Reconstructed C — {stage.name}"
        )

        recon_syntax = Syntax(
            stage.reconstructed_c,
            "c",
            theme="monokai",
            line_numbers=True,
            word_wrap=False,
        )
        recon_viewer.write(recon_syntax)

        # Update bottom panel if visible
        self._render_bottom_panel()

        # Update status bar
        s = stage.stats
        self._update_status(
            f"Stage: {stage.name}  │  "
            f"Instr: {s.instructions}  │  "
            f"Funcs: {s.functions}  │  "
            f"Calls: {s.calls}  │  "
            f"Branches: {s.branches}  │  "
            f"Blocks: {s.blocks}"
        )

    def _render_bottom_panel(self) -> None:
        """Render the bottom panel based on current mode."""
        panel = self.query_one("#bottom-panel", VerticalScroll)
        viewer = self.query_one("#bottom-viewer", RichLog)
        title = self.query_one("#bottom-panel-title", Label)
        viewer.clear()

        if self.bottom_mode == "none" or not self.stages:
            panel.remove_class("visible")
            return

        panel.add_class("visible")

        if self.bottom_mode == "diff":
            self._render_ir_diff(viewer, title)
        elif self.bottom_mode == "c_diff":
            self._render_c_diff(viewer, title)
        elif self.bottom_mode == "stats":
            self._render_stats(viewer, title)
        elif self.bottom_mode == "help":
            self._render_help(viewer, title)

    def _render_ir_diff(self, viewer: RichLog, title: Label) -> None:
        """Render the LLVM IR diff between current and previous stage."""
        idx = self.current_stage
        if idx == 0:
            title.update("  IR Diff: (no previous stage)")
            viewer.write(
                Text("This is the original IR — no diff available.",
                     style="dim italic")
            )
            return

        prev = self.stages[idx - 1]
        curr = self.stages[idx]
        title.update(f"  IR Diff: {prev.name} → {curr.name}")

        diff_lines = compute_diff(
            prev.ir_content,
            curr.ir_content,
            before_label=prev.name,
            after_label=curr.name,
        )
        viewer.write(format_diff_rich(diff_lines))

    def _render_c_diff(self, viewer: RichLog, title: Label) -> None:
        """Render the Reconstructed C diff between current and previous stage."""
        idx = self.current_stage
        if idx == 0:
            title.update("  C Diff: (no previous stage)")
            viewer.write(
                Text("This is the original — no diff available.",
                     style="dim italic")
            )
            return

        prev = self.stages[idx - 1]
        curr = self.stages[idx]
        title.update(f"  Reconstructed C Diff: {prev.name} → {curr.name}")

        diff_lines = compute_diff(
            prev.reconstructed_c,
            curr.reconstructed_c,
            before_label=f"{prev.name} (C)",
            after_label=f"{curr.name} (C)",
        )
        viewer.write(format_diff_rich(diff_lines))

    def _render_stats(self, viewer: RichLog, title: Label) -> None:
        """Render the statistics table for all stages."""
        title.update("  Optimization Statistics")
        names = [s.name for s in self.stages]
        stats = [s.stats for s in self.stages]
        table = format_stats_table(names, stats)
        viewer.write(table)

    def _render_help(self, viewer: RichLog, title: Label) -> None:
        """Render the educational explanation for the current stage."""
        stage = self.stages[self.current_stage]
        title.update(f"  Explanation: {stage.name}")

        help_text = Text()
        help_text.append(stage.explanation, style="")
        viewer.write(help_text)

    def _update_status(self, message: str) -> None:
        """Update the status bar text."""
        bar = self.query_one("#status-bar", Static)
        mode_indicator = " [PRESENTATION]" if self.presentation_mode else ""
        bar.update(f" {message}{mode_indicator} ")

    # ── Actions (key bindings) ────────────────────────────────────────

    def action_stage(self, index: int) -> None:
        """Jump to a specific stage by index (0-based)."""
        if not self.stages:
            return
        if 0 <= index < len(self.stages):
            self.current_stage = index
            self._render_current_stage()

    def action_next_stage(self) -> None:
        """Move to the next stage."""
        if not self.stages:
            return
        if self.current_stage < len(self.stages) - 1:
            self.current_stage += 1
            self._render_current_stage()

    def action_prev_stage(self) -> None:
        """Move to the previous stage."""
        if not self.stages:
            return
        if self.current_stage > 0:
            self.current_stage -= 1
            self._render_current_stage()

    def action_toggle_diff(self) -> None:
        """Toggle the IR diff panel."""
        self.bottom_mode = "none" if self.bottom_mode == "diff" else "diff"
        self._render_bottom_panel()

    def action_toggle_c_diff(self) -> None:
        """Toggle the Reconstructed C diff panel."""
        self.bottom_mode = "none" if self.bottom_mode == "c_diff" else "c_diff"
        self._render_bottom_panel()

    def action_toggle_stats(self) -> None:
        """Toggle the statistics panel."""
        self.bottom_mode = "none" if self.bottom_mode == "stats" else "stats"
        self._render_bottom_panel()

    def action_toggle_help(self) -> None:
        """Toggle the help / explanation panel."""
        self.bottom_mode = "none" if self.bottom_mode == "help" else "help"
        self._render_bottom_panel()

    def action_toggle_presentation(self) -> None:
        """Enter or exit presentation mode.

        Presentation mode hides the sidebar and original C panel,
        showing only the IR and Reconstructed C side by side.
        """
        self.presentation_mode = not self.presentation_mode
        screen = self.screen
        if self.presentation_mode:
            screen.add_class("presentation")
            self.bottom_mode = "none"
            self.notify(
                "Presentation mode ON — SPACE/BACKSPACE to navigate",
                title="🎓 Presentation",
                timeout=3,
            )
        else:
            screen.remove_class("presentation")
            self.notify(
                "Presentation mode OFF",
                title="Normal Mode",
                timeout=2,
            )
        self._render_current_stage()

    def action_export_report(self) -> None:
        """Export a Markdown optimization report."""
        if not self.stages:
            self.notify("No data to export.", severity="warning")
            return

        report_path = self.output_dir / "report.md"
        try:
            generate_report(
                stage_names=[s.name for s in self.stages],
                stage_ir_contents=[s.ir_content for s in self.stages],
                stage_reconstructed_c=[s.reconstructed_c for s in self.stages],
                stage_stats=[s.stats for s in self.stages],
                original_c=self.original_c,
                output_path=report_path,
            )
            self.notify(
                f"Report saved to {report_path}",
                title="📄 Export",
                timeout=4,
            )
        except Exception as exc:
            self.notify(
                f"Export failed: {exc}",
                severity="error",
                timeout=5,
            )


# ═══════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    """Parse arguments and launch the application."""
    if len(sys.argv) < 2:
        print(
            "Usage: python app.py <path-to-c-source.c>\n"
            "\n"
            "Example:\n"
            "  python app.py examples/sample1.c\n"
            "  python app.py examples/sample2.c\n",
            file=sys.stderr,
        )
        sys.exit(1)

    input_file = sys.argv[1]
    app = LLVMExplorerApp(input_file)
    app.run()


if __name__ == "__main__":
    main()
