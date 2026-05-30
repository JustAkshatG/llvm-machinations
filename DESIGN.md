# Function Inlining with Dead Code Elimination — Design Document

## 1. Problem Statement

Function inlining and dead code elimination (DCE) are two fundamental compiler optimizations that work **synergistically**. Inlining replaces function calls with the body of the called function, which often exposes previously hidden dead code that DCE can then remove. Despite being foundational to modern compilers, these optimizations are typically taught only theoretically, leaving students with limited hands-on understanding of how they transform real code.

### Goal

Build an **interactive visualization tool** that demonstrates step-by-step how LLVM optimization passes — centered on **function inlining** and **dead code elimination** — transform C source code. The tool should make the IR-level transformations accessible by also showing a reconstructed pseudo-C representation at each stage.

---

## 2. Approach

### 2.1 Core Pipeline

We use LLVM's modular optimization infrastructure to apply passes **individually and sequentially**:

1. **Compile** C source → unoptimized LLVM IR via `clang -S -emit-llvm -O0`
2. **Preprocess** IR (strip `noinline`, run `mem2reg` for clean SSA form)
3. **Apply 4 passes sequentially**, capturing IR after each:
   - **Function Inlining** (`inline`)
   - Sparse Conditional Constant Propagation (`sccp`)
   - Control Flow Graph Simplification (`simplifycfg`)
   - **Dead Code Elimination** (`dce`)
4. **Reconstruct** pseudo-C from IR at each stage for readability
5. **Compute** metrics (instruction count, calls, branches, blocks) at each stage
6. **Visualize** all stages in an interactive terminal UI

### 2.2 Why This Pass Ordering

The key insight is that these four passes form a **natural optimization chain** where each pass enables the next:

```
Inlining exposes constant arguments visible in caller
    → SCCP propagates those constants, resolves branch conditions
        → SimplifyCFG removes newly-dead branches and unreachable blocks
            → DCE removes instructions whose results are no longer used
```

SCCP and SimplifyCFG are **bridge passes** — they are not the focus of the assignment, but they are essential to demonstrate how inlining **enables** DCE. Without them, the dead code created by inlining would remain partially hidden behind unresolved branches.

### 2.3 Visualization Strategy

Rather than just showing before/after IR dumps, we provide:

- **Three-panel layout**: Original C (static) | LLVM IR (per-stage) | Reconstructed C (per-stage)
- **Diff views** showing exact changes between consecutive stages
- **Statistics tracking** with color-coded deltas
- **Educational explanations** for each pass
- **Presentation mode** for classroom demos
- **Markdown report export** for offline review

---

## 3. Architecture

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

### Module Responsibilities

| Module | Lines | Responsibility |
|--------|------:|----------------|
| `app.py` | 701 | Textual TUI — layout, keybindings, rendering |
| `pipeline.py` | 360 | Orchestrates `clang` compilation and `opt` pass execution |
| `c_reconstructor.py` | 567 | Regex-based LLVM IR → pseudo-C translator |
| `ir_parser.py` | 109 | IR construct counting (instructions, calls, branches, blocks) |
| `statistics.py` | 137 | Per-stage metrics computation and Rich table formatting |
| `diff_viewer.py` | 92 | Unified diff computation and rendering (Rich + Markdown) |
| `file_manager.py` | 161 | File validation, output management, report generation |

---

## 4. Key Design Decisions

### 4.1 Using `opt` CLI vs. Custom LLVM Pass Plugin

We invoke LLVM's `opt` tool via subprocess for each pass rather than writing a custom LLVM pass plugin.

**Rationale:** Using `opt` with individual `-passes=<name>` flags lets us capture the IR after **each** pass independently. A custom plugin would require C++ development, LLVM build infrastructure, and would couple us to a specific LLVM version. The subprocess approach is portable, simple, and works with any installed LLVM version.

### 4.2 `-O0` Compilation with `noinline` Stripping

We compile with `-O0` (no optimizations) and then manually strip the `noinline` attribute from the generated IR.

**Rationale:** `-O0` produces maximally verbose IR where every optimization has maximum visible effect. However, `-O0` also adds `noinline` to all functions, preventing the inline pass from working. We strip this attribute so that inlining can proceed while keeping all other code unoptimized.

### 4.3 `mem2reg` Preprocessing

Before the main pass pipeline, we run the `mem2reg` pass to promote stack allocations to SSA registers.

**Rationale:** `-O0` generates `alloca`/`load`/`store` for every variable, producing noisy IR that obscures the actual program logic. `mem2reg` converts these to clean SSA form with `phi` nodes, making the IR readable and enabling subsequent passes to work effectively.

### 4.4 Regex-Based C Reconstruction

The pseudo-C reconstructor uses regular expressions rather than a full decompiler.

**Rationale:** Full decompilers (RetDec, LLVM's old C backend) produce complex output not suited for educational display. Our regex approach produces **simplified, readable pseudo-C** that highlights the key transformations students need to see. The output is explicitly labeled as "not compilable" to avoid confusion.

---

## 5. Alternatives Considered

### 5.1 GCC Instead of LLVM

GCC's optimization passes are more tightly coupled and cannot be easily invoked individually via a command-line tool equivalent to `opt`. LLVM's modular architecture — where each pass is independently invocable — is essential for step-by-step visualization.

### 5.2 Web-Based UI (React/Flask)

A web application would provide richer visualizations but introduces significant dependencies (Node.js, browsers) and setup friction. A **terminal UI** (Textual framework) works everywhere — including SSH sessions, lab machines, and minimal environments — with only Python as a dependency.

### 5.3 Source-to-Source Transformation

Performing optimizations directly at the C source level would be simpler to visualize but wouldn't reflect what real compilers actually do. Operating on **LLVM IR** teaches students the actual optimizer behavior and the IR representation used in production compilers.

### 5.4 Showing Only IR (No Reconstruction)

We could show just the raw IR at each stage, but LLVM IR is unfamiliar to most students. The **pseudo-C reconstruction** bridges the gap by translating IR back into a C-like form, making the transformations immediately comprehensible even without IR knowledge.

### 5.5 Running All Passes at Once (`-O2`)

We could run `-O2` and show only the final result, but this hides the **step-by-step chain** that is the entire educational point. Splitting into individual passes reveals **causality**: inlining creates the opportunity, SCCP exploits it, SimplifyCFG cleans up, and DCE finishes the job.

---

## 6. Limitations

1. **Recursive functions cannot be inlined** — LLVM's inline pass will not expand recursive calls, so the optimization chain has limited effect on recursive code (see test case 5).

2. **Regex-based reconstruction is approximate** — Complex IR constructs (vector operations, exception handling, complex GEPs) may not be perfectly translated. The reconstructor handles common patterns well but is not a general-purpose decompiler.

3. **Fixed pass pipeline** — The current implementation uses a fixed set of 4 passes. Adding or reordering passes requires code changes.

4. **External tool dependency** — The tool requires `clang` and `opt` to be installed and in PATH, which may not be available on all systems.
