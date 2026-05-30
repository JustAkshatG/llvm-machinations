#!/usr/bin/env bash
# ============================================================================
# run.sh — LLVM Optimization Explorer Run Script
# ============================================================================
# Launches the interactive TUI application on a C source file, or runs the
# headless evaluation suite on all test cases.
#
# Usage:
#   ./run.sh <path-to-file.c>            # Interactive TUI
#   ./run.sh                              # Interactive TUI with default test case
#   ./run.sh --evaluate                   # Headless evaluation of all test cases
#
# Examples:
#   ./run.sh testcases/test1_basic_inline_dce.c
#   ./run.sh llvm_explorer/examples/sample1.c
#   ./run.sh --evaluate
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/llvm_explorer/.venv"
APP="$SCRIPT_DIR/llvm_explorer/app.py"
EVALUATOR="$SCRIPT_DIR/scripts/evaluate.py"
DEFAULT_TEST="$SCRIPT_DIR/testcases/test1_basic_inline_dce.c"

# ── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

# ── Check build ─────────────────────────────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${RED}[ERROR]${NC} Virtual environment not found."
    echo "        Run ./build.sh first to set up the project."
    exit 1
fi

# ── Activate venv ───────────────────────────────────────────────────────────
source "$VENV_DIR/bin/activate"

# ── Parse arguments ─────────────────────────────────────────────────────────
if [ $# -eq 0 ]; then
    echo -e "${CYAN}[INFO]${NC}  No input file specified, using default: $DEFAULT_TEST"
    INPUT_FILE="$DEFAULT_TEST"
elif [ "$1" == "--evaluate" ]; then
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  Running Headless Evaluation Suite"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    python "$EVALUATOR"
    exit $?
elif [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    echo "Usage: ./run.sh [OPTIONS] [path-to-file.c]"
    echo ""
    echo "Arguments:"
    echo "  path-to-file.c    C source file to analyze (default: testcases/test1_basic_inline_dce.c)"
    echo ""
    echo "Options:"
    echo "  --evaluate         Run headless evaluation on all test cases"
    echo "  --help, -h         Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./run.sh testcases/test1_basic_inline_dce.c"
    echo "  ./run.sh llvm_explorer/examples/sample1.c"
    echo "  ./run.sh --evaluate"
    exit 0
else
    INPUT_FILE="$1"
fi

# ── Validate input file ────────────────────────────────────────────────────
if [ ! -f "$INPUT_FILE" ]; then
    echo -e "${RED}[ERROR]${NC} File not found: $INPUT_FILE"
    exit 1
fi

# ── Launch ──────────────────────────────────────────────────────────────────
echo -e "${GREEN}[START]${NC} Launching LLVM Optimization Explorer..."
echo -e "        Input: $INPUT_FILE"
echo ""

python "$APP" "$INPUT_FILE"
