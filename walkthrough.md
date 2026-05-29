# LLVM Optimization Explorer — Walkthrough (C Source Support & Reconstructed C Visualizer)

This walkthrough documents the major enhancements made to transition the LLVM Optimization Explorer from processing static `.ll` files to working directly with **C source files**, automatically compiling them to LLVM IR, and generating an educational **reconstructed C visualizer** at each stage.

## Changes Made

### 1. New Module: C Reconstructor
- **File**: [c_reconstructor.py](file:///run/media/akshat/New%20Volume/Akshat/RVCE/Subjects/Sem%206/Compiler%20Design/EL/llvm-machinations/llvm_explorer/c_reconstructor.py)
- **Role**: Translates raw LLVM IR at each pipeline stage back into a readable, pseudo-C form (not compilable, but structured to mimic source code).
- **Key Features**:
  - Automatically identifies variables, arithmetic, function calls, and control flow.
  - Formats branch instructions as C-like conditional/unconditional `goto` statements.
  - Maps numeric SSA values to readable temporal variable names (e.g. `%3` → `t3`).
  - Resolves target labels dynamically, prefixing numeric basic block names to make them valid identifier labels (e.g. `%4:` → `lbl_4:`).
  - Highlights `phi` nodes using mathematical $\phi$ notation (`x = φ(val1 from lbl_1, val2 from lbl_2)`).

### 2. Modified: Pipeline Orchestrator
- **File**: [pipeline.py](file:///run/media/akshat/New%20Volume/Akshat/RVCE/Subjects/Sem%206/Compiler%20Design/EL/llvm-machinations/llvm_explorer/pipeline.py)
- **Role**: Builds and coordinates compilation and optimization steps.
- **Key Features**:
  - Compiles the input `.c` source file to unoptimized LLVM IR via `clang -S -emit-llvm -O0`.
  - Automatically strips `-O0` `noinline` attributes to allow function inlining to take place.
  - Sequentially applies optimization passes: `mem2reg` -> `inline` -> `sccp` -> `simplifycfg` -> `dce`.
  - Reconstructs pseudo-C and saves both `.ll` and reconstructed `.c` files for every step in the `output/` directory.

### 3. Modified: File Manager & Report Generation
- **File**: [file_manager.py](file:///run/media/akshat/New%20Volume/Akshat/RVCE/Subjects/Sem%206/Compiler%20Design/EL/llvm-machinations/llvm_explorer/file_manager.py)
- **Role**: Handles input validation and report rendering.
- **Key Features**:
  - Validates that the input file is a readable C source (`.c`) file.
  - Enhances report exports to include side-by-side or sequential diffs for both LLVM IR and Reconstructed C across all pipeline stages.

### 4. Modified: Textual App Layout
- **File**: [app.py](file:///run/media/akshat/New%20Volume/Akshat/RVCE/Subjects/Sem%206/Compiler%20Design/EL/llvm-machinations/llvm_explorer/app.py)
- **Role**: Main TUI application.
- **Key Features**:
  - Implements a modern **three-panel layout**:
    - **Original C Source** (fixed, green border) on the left.
    - **LLVM IR** (per-stage, blue/accent border) in the center.
    - **Reconstructed C** (per-stage, orange/warning border) on the right.
  - Adds the `c` keybinding to toggle Reconstructed C diff view in the bottom panel.
  - Updates presentation mode (`p`) to show LLVM IR and Reconstructed C side-by-side.

---

## Verification Results

### Pipeline Execution on `examples/sample1.c`

```c
// Small function that will be inlined
int add_offset(int x, int offset) {
    return x + offset;
}

int compute() {
    int val = add_offset(10, 5);   // inline candidate + const args
    int dead = val * 42;           // unused → DCE target
    if (val > 0) {                 // constant condition → SimplifyCFG
        return val + 1;
    } else {
        return val - 100;          // unreachable
    }
}

int main() {
    return compute();
}
```

The pipeline executes through five distinct stages:

1. **Original**: Unoptimized IR is generated. The call to `add_offset(10, 5)` is present in both IR and Reconstructed C.
2. **Inline**: The `add_offset` call inside `compute()` is inline-substituted with its computation (`15`). In the reconstructed C:
   `int t1 = 15 * 42;`
3. **SCCP**: Constant propagation runs. The branch condition `15 > 0` resolves to true. Unreachable branches are marked dead, and the function simply jumps to returning `16`.
4. **SimplifyCFG**: The control-flow graph is simplified, removing the dead branches and unnecessary labels.
5. **DCE**: Dead code (such as the unused `t1` multiplication) is completely eliminated. The final reconstructed C shows:
   ```c
   int compute() {
       return 16;
   }
   ```

### Tests Executed
- **Smoke Tests**: Verified successful imports of all modules (`app`, `pipeline`, `c_reconstructor`, etc.).
- **Reconstruction Verification**: Validated that `_resolve` correctly separates registers (`%3` → `t3`) and numeric constants (`10` stays `10`), and that basic blocks (`4` → `lbl_4`) are cleanly prefixed.
- **Report Generation**: Verified report exports save all files correctly.
