# Evaluation — Metrics, Comparison, and Test Cases

This document evaluates the Function Inlining + Dead Code Elimination pipeline across **8 test cases** (6 dedicated test cases + 2 built-in examples), measuring instruction reduction, call elimination, branch removal, and block reduction at each optimization stage.

---

## 1. Test Case Descriptions

| # | File | Description | Key Optimization |
|---|------|-------------|------------------|
| 1 | `test1_basic_inline_dce.c` | Basic inline + DCE: `square(5)` inlined, unused `square(3)` eliminated | Inline → DCE |
| 2 | `test2_multi_func_chain.c` | Three-function call chain (`add → double_it → quad`) fully inlined | Multi-level inline |
| 3 | `test3_multi_dead_vars.c` | Cascade of dead variables (`dead1 → dead2 → dead3`) all eliminated | Cascading DCE |
| 4 | `test4_mixed_live_dead.c` | Two helper functions with live/dead mix and branch folding | Inline + branch fold + DCE |
| 5 | `test5_recursive_no_inline.c` | **FAILURE CASE**: Recursive `factorial()` — cannot be inlined | Limitation demo |
| 6 | `test6_minimal_optimization.c` | All-live code, no function calls to inline — minimal DCE effect | Baseline comparison |
| 7 | `examples/sample1.c` | Built-in demo: `add_offset(10,5)` → inline → DCE | Reference case |
| 8 | `examples/sample2.c` | Built-in demo: multi-function with call chains | Reference case |

---

## 2. How to Run the Evaluation

```bash
# Run all test cases and produce metrics
./run.sh --evaluate

# Or run directly:
python scripts/evaluate.py

# Output as Markdown tables:
python scripts/evaluate.py --markdown

# Evaluate a single file:
python scripts/evaluate.py testcases/test1_basic_inline_dce.c
```

---

## 3. Metrics Collected

At each of the 5 pipeline stages (Original → Inline → SCCP → SimplifyCFG → DCE), we measure:

| Metric | Description |
|--------|-------------|
| **Instructions** | Total LLVM IR instructions (assignments + standalone) |
| **Functions** | Number of `define` declarations |
| **Calls** | Number of `call`/`tail call` instructions |
| **Branches** | Number of `br` instructions |
| **Blocks** | Number of basic blocks (labels + implicit entry blocks) |

The primary metric is **instruction count reduction** from Original to DCE, expressed as both an absolute count and a percentage.

---

## 4. Expected Results

### Test 1: Basic Inline + DCE (`test1_basic_inline_dce.c`)

| Stage | Instructions | Calls | Branches | Key Change |
|-------|------------:|------:|---------:|------------|
| Original | ~14 | 2 | 3 | `square()` called twice |
| Inline | ~12 | 0 | 3 | Both calls inlined, constants exposed |
| SCCP | ~8 | 0 | 1 | `25 > 0` resolved to true |
| SimplifyCFG | ~5 | 0 | 0 | Dead branch removed |
| DCE | ~3 | 0 | 0 | `unused = square(3)` computation removed |

**Expected reduction:** ~70–80%

### Test 2: Multi-Function Chain (`test2_multi_func_chain.c`)

| Stage | Key Change |
|-------|------------|
| Original | `quad(3)` calls `double_it()` which calls `add()` — deep chain |
| Inline | Entire chain collapsed: `add(x,x)` → `x+x`, `double_it(x)` → `x+x` |
| SCCP | `quad(3)` = 12, `12 > 100` = false |
| SimplifyCFG | Unreachable `if` branch removed |
| DCE | `waste = val * val` removed |

**Expected reduction:** ~70–80%

### Test 3: Cascading Dead Variables (`test3_multi_dead_vars.c`)

| Stage | Key Change |
|-------|------------|
| Original | `dead1`, `dead2`, `dead3` form a chain of dead computations |
| Inline | `offset(10, 20)` inlined → 30 |
| SCCP | All values computed: a=30, b=35, c=60 |
| DCE | `dead1`, `dead2`, `dead3` all removed in one pass |

**Expected reduction:** ~60–70%

### Test 4: Mixed Live/Dead with Branches (`test4_mixed_live_dead.c`)

| Stage | Key Change |
|-------|------------|
| Original | `max_val()` and `min_val()` have internal branches |
| Inline | Both functions inlined, internal branches exposed |
| SCCP | Constants propagated: big=10, small=3, `10==3` = false |
| SimplifyCFG | Dead `if` branch removed, internal branches simplified |
| DCE | `dead_sum = big + small` removed |

**Expected reduction:** ~60–75%

### Test 5: Recursive — FAILURE CASE (`test5_recursive_no_inline.c`)

| Stage | Instructions | Calls | Key Change |
|-------|------------:|------:|------------|
| Original | ~8–12 | 2 | `factorial()` calls itself recursively |
| Inline | ~8–12 | 1–2 | **Recursive call NOT inlined** |
| SCCP | ~8–12 | 1–2 | Cannot resolve runtime-dependent recursion |
| SimplifyCFG | ~8–12 | 1–2 | May simplify some structure |
| DCE | ~8–12 | 1–2 | **Minimal removal** — most code is live |

**Expected reduction:** <10% — **This is the failure case**

This demonstrates the fundamental **limitation of function inlining**: recursive functions cannot be expanded because inlining would require infinite code generation. The recursive `call` instruction remains, and since the loop's iteration count depends on the runtime argument, SCCP cannot constant-fold the computation either.

### Test 6: Minimal Optimization (`test6_minimal_optimization.c`)

| Stage | Key Change |
|-------|------------|
| Original | Single function, all variables are live, no function calls to inline |
| Inline | **No effect** — no call sites within the function |
| SCCP | Constants propagated (a=3, b=7, sum=10, product=21, result=31) |
| SimplifyCFG | Minimal cleanup |
| DCE | **No effect** — all computations are used |

**Expected reduction:** Moderate (from SCCP constant folding), but **DCE contributes nothing**

This shows that dead code elimination is only effective when prior passes (especially inlining) **create** dead code. When all code is live from the start, DCE has nothing to remove.

---

## 5. Baseline Comparison

The baseline is the **Original** stage (unoptimized IR after `mem2reg`). The optimized result is the **DCE** stage (final output after all 4 passes).

| Test Case | Category | Expected Reduction |
|-----------|----------|-------------------:|
| test1 (basic) | Standard inline + DCE | ~70–80% |
| test2 (chain) | Multi-level inline | ~70–80% |
| test3 (cascading dead) | Aggressive DCE | ~60–70% |
| test4 (mixed) | Inline + branch fold + DCE | ~60–75% |
| **test5 (recursive)** | **FAILURE** | **<10%** |
| test6 (minimal) | SCCP only, no DCE effect | ~40–60% |
| sample1 | Reference | ~70% |
| sample2 | Reference | ~65–75% |

### Key Observations

1. **Inlining is the enabler**: Without inlining, constant arguments remain hidden behind call boundaries, and SCCP/DCE have limited effect.

2. **DCE alone is insufficient**: DCE only removes instructions with no users. It cannot discover that code is dead due to constant conditions — that requires SCCP + SimplifyCFG first.

3. **Recursive functions are a hard limit**: The inline pass cannot expand recursive calls. This is a fundamental limitation, not a bug.

4. **SCCP amplifies inlining**: After inlining exposes constants, SCCP propagates them through the entire function, often resolving branch conditions and creating opportunities for SimplifyCFG and DCE.

---

## 6. Reproducing Results

To reproduce the evaluation results on your system:

```bash
# 1. Build the project
./build.sh

# 2. Run the headless evaluation
./run.sh --evaluate

# 3. For Markdown output (to fill exact numbers into this document)
python scripts/evaluate.py --markdown
```

The evaluation script runs all test cases in `testcases/` and `llvm_explorer/examples/`, printing per-stage metrics and a summary table.

**Note:** Exact instruction counts may vary slightly between LLVM versions due to differences in the initial IR generated by `clang`. The relative reductions (percentages) should be consistent.

---

## 7. Demo Instructions

### Interactive TUI Demo

```bash
# Launch the interactive explorer on any test case
./run.sh testcases/test1_basic_inline_dce.c

# Keyboard shortcuts in the TUI:
#   1-5       Jump to stage (Original / Inline / SCCP / SimplifyCFG / DCE)
#   ← →       Previous / Next stage
#   d         Toggle LLVM IR diff panel
#   c         Toggle Reconstructed C diff panel
#   s         Toggle statistics panel
#   h         Toggle help/explanation panel
#   p         Enter/exit presentation mode
#   e         Export Markdown report
#   q         Quit
```

### What to Demonstrate

1. **Working case**: Run `test1_basic_inline_dce.c` and step through all 5 stages. Show:
   - Stage 1 (Original): `square()` calls present in IR and reconstructed C
   - Stage 2 (Inline): calls replaced with inlined body
   - Stage 5 (DCE): unused computation completely removed
   - Press `d` for IR diff, `c` for C diff, `s` for statistics

2. **Failure case**: Run `test5_recursive_no_inline.c` and show:
   - Stage 2 (Inline): recursive `call` still present — NOT inlined
   - Stage 5 (DCE): function largely unchanged — optimization has limited effect
   - Press `s` to show statistics: instruction count barely changes

3. **Export**: Press `e` to generate `output/report.md` with full optimization report

### Capturing Screenshots

To capture demo screenshots:
1. Launch the TUI: `./run.sh testcases/test1_basic_inline_dce.c`
2. Navigate to each stage and take a screenshot
3. Press `d` to show the diff panel and capture
4. Press `s` to show statistics and capture
5. Repeat with `test5_recursive_no_inline.c` for the failure case
