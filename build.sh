#!/usr/bin/env bash
# ============================================================================
# build.sh — LLVM Optimization Explorer Build Script
# ============================================================================
# Sets up the Python virtual environment, installs dependencies, and verifies
# that the required LLVM tools (clang, opt) are available.
#
# Usage:
#   chmod +x build.sh
#   ./build.sh
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/llvm_explorer/.venv"
REQ_FILE="$SCRIPT_DIR/llvm_explorer/requirements.txt"

# ── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'  # No Color

info()    { echo -e "${CYAN}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[  OK]${NC}  $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
fail()    { echo -e "${RED}[FAIL]${NC}  $1"; exit 1; }

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  LLVM Optimization Explorer — Build Setup"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ── Step 1: Check Python ────────────────────────────────────────────────────
info "Checking Python installation..."

PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        version=$("$candidate" --version 2>&1 | grep -oP '\d+\.\d+')
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON="$candidate"
            success "Found $candidate ($("$candidate" --version 2>&1))"
            break
        else
            warn "$candidate version $version found, but 3.11+ is required."
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    fail "Python 3.11+ is required but not found. Install it from https://python.org"
fi

# ── Step 2: Check LLVM tools ────────────────────────────────────────────────
info "Checking LLVM tools..."

if command -v clang &>/dev/null; then
    success "clang found: $(clang --version 2>&1 | head -1)"
else
    fail "clang not found in PATH. Install LLVM:\n" \
         "  Arch:   sudo pacman -S llvm clang\n" \
         "  Ubuntu: sudo apt install llvm clang\n" \
         "  macOS:  brew install llvm"
fi

if command -v opt &>/dev/null; then
    success "opt found: $(opt --version 2>&1 | head -1)"
else
    fail "opt not found in PATH. Install LLVM (see above)."
fi

# ── Step 3: Create virtual environment ──────────────────────────────────────
info "Setting up Python virtual environment..."

if [ -d "$VENV_DIR" ]; then
    warn "Virtual environment already exists at $VENV_DIR"
else
    "$PYTHON" -m venv "$VENV_DIR"
    success "Created virtual environment at $VENV_DIR"
fi

# ── Step 4: Install dependencies ────────────────────────────────────────────
info "Installing Python dependencies..."

source "$VENV_DIR/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet -r "$REQ_FILE"
success "Installed: $(pip list --format=freeze | grep -E 'textual|rich' | tr '\n' ' ')"

# ── Step 5: Verify imports ──────────────────────────────────────────────────
info "Verifying module imports..."

"$PYTHON" -c "
import textual
import rich
from pathlib import Path
print('All imports OK')
" && success "All Python modules import successfully" \
  || fail "Module import check failed"

# ── Done ────────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo -e "  ${GREEN}Build complete!${NC} Run the explorer with:"
echo ""
echo "    ./run.sh testcases/test1_basic_inline_dce.c"
echo ""
echo "  Or run the evaluation suite:"
echo ""
echo "    ./run.sh --evaluate"
echo "═══════════════════════════════════════════════════════════════"
echo ""
