# LLVM Optimization Explorer

An interactive terminal application that demonstrates how LLVM optimization passes transform C code step-by-step. It compiles C source files under the hood, executes optimization passes sequentially, and visualizes both the LLVM IR and a reconstructed pseudo-C representation side-by-side.

Built for compiler-design courses and anyone curious about how compilers optimize code.

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![LLVM](https://img.shields.io/badge/LLVM-required-orange)
![Clang](https://img.shields.io/badge/Clang-required-red)

## Features

- **Step-by-step pipeline** — compiles C source files and runs 4 LLVM passes sequentially: Inlining → SCCP → SimplifyCFG → DCE
- **Three-Panel Layout** — displays Original C Source, LLVM IR, and Reconstructed C side-by-side
- **Reconstructed C Visualizer** — translates intermediate IR back into a readable, pseudo-C form (not compilable, but structured to mimic source code)
- **Syntax-highlighted viewers** — browse source, IR, and reconstructed C with line numbers and scroll support
- **Double Diff viewer** — view what changed between stages in LLVM IR (`d` key) and Reconstructed C (`c` key)
- **Statistics engine** — track instruction, call, branch, and block counts across stages
- **Educational explanations** — learn what each optimization does and why
- **Presentation mode** — full-screen, step-by-step progression for classroom demos (hides Original C and sidebar, showing IR and Reconstructed C side-by-side)
- **Markdown report export** — generate a complete optimization report with statistical tables, IR diffs, and reconstructed C diffs

## Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| Python 3.11+ | Runtime | [python.org](https://python.org) |
| LLVM (`opt`) | Optimization passes | See below |
| `clang` | Compile C to IR | Bundled with LLVM |

### Installing LLVM & Clang

```bash
# Arch Linux
sudo pacman -S llvm clang

# Ubuntu / Debian
sudo apt install llvm clang

# macOS (Homebrew)
brew install llvm
export PATH="/opt/homebrew/opt/llvm/bin:$PATH"

# Fedora
sudo dnf install llvm clang
```

Verify installation:
```bash
opt --version
clang --version
```

## Quick Start

```bash
# 1. Clone and enter the project
cd llvm_explorer

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Run with the built-in C sample
python app.py examples/sample1.c
```

## Usage

```bash
python app.py <path-to-file.c>
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1` – `5` | Jump to stage (Original / Inline / SCCP / SimplifyCFG / DCE) |
| `←` `→` | Previous / Next stage |
| `d` | Toggle LLVM IR diff panel |
| `c` | Toggle Reconstructed C diff panel |
| `s` | Toggle statistics panel |
| `h` | Toggle help / explanation panel |
| `p` | Enter / exit presentation mode (shows IR + Reconstructed C side-by-side) |
| `e` | Export Markdown report |
| `q` | Quit |

### Presentation Mode

Press `p` to enter full-screen presentation mode suitable for classrooms:
- Sidebar and Original C source are hidden for maximum visibility of intermediate code
- `SPACE` advances to the next stage
- `BACKSPACE` goes back

### Export

Press `e` to generate `output/report.md` — a Markdown document containing:
- Original C source code
- Statistics table across all stages
- Total instruction reduction summary
- Unified diffs for LLVM IR at every pass
- Unified diffs for Reconstructed C at every pass
- Final reconstructed C code

## Project Structure

```
llvm_explorer/
├── app.py              # Textual TUI application (entry point)
├── pipeline.py         # C compilation, LLVM opt execution, and stage management
├── c_reconstructor.py  # Regex-based IR to pseudo-C translator
├── diff_viewer.py      # Diff computation and Rich formatting
├── statistics.py       # IR statistics engine
├── ir_parser.py        # LLVM IR counting functions
├── file_manager.py     # File validation and report generation
├── requirements.txt    # Python dependencies
├── examples/
│   ├── sample1.c       # Demo: inline + SCCP + CFG + DCE
│   └── sample2.c       # Demo: multi-function call chains
└── output/             # Generated intermediate IR/C files and reports
```

## Example Optimization Walkthrough

`sample1.c` demonstrates how function inlining enables downstream optimizations:

1. **Original** — Unoptimized IR is generated. The call to `add_offset(10, 5)` is present.
2. **Inlining** — The body of `add_offset(10, 5)` is inline-substituted. The function call is gone and the constant inputs (`10` and `5`) are combined as `15`.
3. **SCCP** — Constant propagation runs. The branch condition `15 > 0` evaluates to `true`. Unreachable branches are marked dead, and the function return value simplifies to `16`.
4. **SimplifyCFG** — Control flow graph is simplified. Unconditional jumps and dead basic blocks are removed.
5. **DCE** — Unused instructions (like the multiplication `t1 * 42` which has no consumers) are completely deleted. The final function is optimized down to a single return instruction.

## Architecture

```
┌────────────────────────────────────────────────────────┐
│                      app.py (TUI)                      │
│  ┌──────────┬──────────────┬──────────────┬─────────┐  │
│  │ Timeline │  Original C  │   LLVM IR    │ Reconst │  │
│  │ Sidebar  │  (Static)    │  (Per Stage) │ C (Per) │  │
│  └──────────┴──────────────┴──────────────┴─────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │            Bottom Panel (Diffs/Stats/Help)       │  │
│  └──────────────────────────────────────────────────┘  │
└───────────────────────────┬────────────────────────────┘
                            │
                      ┌─────▼─────┐
                      │ pipeline  │──→ subprocess: clang & opt
                      └─────┬─────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
    ir_parser         statistics          c_reconstructor
         │                  │                  │
         └──────────────────┼──────────────────┘
                            ▼
                       diff_viewer
                            │
                            ▼
                       file_manager ──→ report.md
```

## License

MIT
