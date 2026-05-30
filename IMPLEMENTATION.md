# Implementation — LLVM Details

This document describes the LLVM-specific implementation details of the Function Inlining with Dead Code Elimination project.

---

## 1. Compilation Strategy

### 1.1 Generating Unoptimized IR

```bash
clang -S -emit-llvm -O0 -Xclang -disable-O0-optnone -o output.ll input.c
```

| Flag | Purpose |
|------|---------|
| `-S` | Output human-readable textual IR (`.ll`) instead of binary bitcode (`.bc`) |
| `-emit-llvm` | Produce LLVM IR rather than native assembly |
| `-O0` | No optimizations — maximally verbose IR |
| `-Xclang -disable-O0-optnone` | **Critical**: prevents clang from adding the `optnone` attribute, which would make `opt` skip all functions entirely |
| `-o output.ll` | Output file path |

### 1.2 Preprocessing: Enabling Inlining on `-O0` IR

The `-O0` compilation adds a `noinline` attribute to every function definition, which tells the `inline` pass to skip them. We handle this with a two-step preprocessing:

**Step 1 — Strip `noinline`:**
```python
raw_ir = raw_ir.replace(" noinline", "")
```
This simple text replacement removes the attribute from all function definitions, allowing the inliner to consider them as candidates.

**Step 2 — Promote to SSA (`mem2reg`):**
```bash
opt -passes=mem2reg -S -o 0_original.ll 0_raw.ll
```

The `-O0` IR allocates every local variable on the stack:
```llvm
; Before mem2reg (noisy, hard to optimize)
%x.addr = alloca i32
store i32 %x, ptr %x.addr
%0 = load i32, ptr %x.addr
```

After `mem2reg`, the IR is in clean SSA form:
```llvm
; After mem2reg (clean SSA, ready for optimization)
; %x is used directly — no alloca/load/store
```

This preprocessing is essential because:
- The `inline` pass works much better on SSA form (no memory dependencies to track)
- SCCP can propagate constants through SSA values but not through memory
- The IR is dramatically more readable for display

### 1.3 Why Not `-O1`?

Using `-O1` or higher would run dozens of passes simultaneously, making it impossible to observe individual transformations. Our approach gives us a clean, unoptimized baseline where each subsequent pass has **maximum observable effect**.

---

## 2. Optimization Passes

Each pass is invoked individually via LLVM's `opt` tool:

```bash
opt -passes=<pass_name> -S -o <output.ll> <input.ll>
```

The `-S` flag ensures the output is human-readable textual IR.

### 2.1 Pass 1: Function Inlining (`inline`)

```bash
opt -passes=inline -S -o 1_inline.ll 0_original.ll
```

**What it does:** Replaces `call` instructions with the body of the called function, effectively copying the callee's code into the caller.

**How LLVM decides what to inline:**
- **Cost model**: Estimates the cost (in "abstract units") of inlining vs. not inlining
- **Function size**: Small functions (few instructions) are preferred candidates
- **Call count**: Functions called from only one site are strongly favored
- **Attributes**: `alwaysinline` forces inlining; `noinline` prevents it (which is why we strip it)
- **Recursion**: Recursive calls are **never** inlined (would require infinite expansion)

**Example transformation (from `sample1.c`):**

```llvm
; BEFORE inlining:
define i32 @compute() {
  %1 = call i32 @add_offset(i32 10, i32 5)   ; ← call instruction present
  ...
}

; AFTER inlining:
define i32 @compute() {
  %1 = add nsw i32 10, 5                       ; ← call replaced with body
  ...
}
```

**Why this enables DCE:** After inlining, the constant arguments `10` and `5` are directly visible in the caller. This lets SCCP compute `10 + 5 = 15` and determine that branches depending on this value can be resolved at compile time, ultimately making the dead code visible to DCE.

### 2.2 Pass 2: Sparse Conditional Constant Propagation (`sccp`)

```bash
opt -passes=sccp -S -o 2_sccp.ll 1_inline.ll
```

**What it does:** Combines two analyses:

1. **Constant Propagation** — tracks which SSA values are provably constant and replaces their uses with the constant value
2. **Conditional Constant Propagation** — determines which branch conditions are constant, marking unreachable branches as dead

**How it works (SSA-based lattice):**
1. All values start as `⊤` (undefined/unknown)
2. Values are lowered to constants when provably constant
3. Values that receive multiple different constants are lowered to `⊥` (overdefined/not constant)
4. Branch conditions that are constant determine reachability of successor blocks
5. Iteration continues until a fixed point is reached

The "sparse" qualifier means SCCP operates on the SSA **def-use graph** rather than iterating over all instructions, making it efficient even on large functions.

**Example (after inlining exposes constants):**
```llvm
; BEFORE SCCP:
  %1 = add nsw i32 10, 5             ; → SCCP determines: %1 = 15
  %2 = mul nsw i32 %1, 42            ; → SCCP determines: %2 = 630
  %3 = icmp sgt i32 %1, 0            ; → SCCP determines: %3 = true
  br i1 %3, label %4, label %6       ; → else branch is UNREACHABLE

; AFTER SCCP:
  br label %4                         ; unconditional — condition resolved
```

**Role in the chain:** SCCP is the bridge between inlining and DCE. Inlining exposes constants; SCCP propagates them and marks unreachable paths. Without SCCP, the branch condition `val > 0` would remain unresolved, and the dead code in the unreachable branch would persist.

### 2.3 Pass 3: Control Flow Graph Simplification (`simplifycfg`)

```bash
opt -passes=simplifycfg -S -o 3_simplifycfg.ll 2_sccp.ll
```

**What it does:** Cleans up the control flow graph:

| Simplification | Description |
|----------------|-------------|
| Block merging | Merges basic blocks that have a single predecessor and single successor |
| Branch folding | Removes branches with constant conditions (replaces with unconditional jump) |
| Dead block removal | Eliminates basic blocks that are unreachable |
| Empty block elimination | Removes basic blocks that contain only an unconditional branch |
| Switch simplification | Converts switches with few cases to branches |

**Role in the chain:** After SCCP marks branches as constant, SimplifyCFG physically removes the dead basic blocks and simplifies the remaining control flow. This makes the IR cleaner and may expose additional dead instructions for DCE.

### 2.4 Pass 4: Dead Code Elimination (`dce`)

```bash
opt -passes=dce -S -o 4_dce.ll 3_simplifycfg.ll
```

**What it does:** Removes instructions whose results are **never used** and that have **no observable side effects**.

**An instruction is "dead" if:**
1. No other instruction references its SSA value (`%result`)
2. It does not write to memory (`store`)
3. It does not perform I/O or call functions with side effects

**Example (the culmination of the chain):**
```llvm
; BEFORE DCE:
  %dead = mul nsw i32 15, 42         ; result is never used anywhere
  ret i32 16

; AFTER DCE:
  ret i32 16                          ; dead instruction removed!
```

**Why DCE needs the prior passes:** Consider `int dead = val * 42` from `sample1.c`. Before inlining, `val` was returned by a function call, so the compiler couldn't know if `dead` might be used later. After the full chain (inline → SCCP → SimplifyCFG), the only remaining code is `ret i32 16`, which makes `dead`'s computation provably unused.

---

## 3. The Complete Optimization Chain

This diagram shows how the passes work together on `sample1.c`:

```
ORIGINAL (after mem2reg):
    int val = add_offset(10, 5);    ← compiler can't see through call
    int dead = val * 42;            ← might be used (val is unknown)
    if (val > 0) { return val+1; }  ← condition is unknown
    else { return val-100; }

         ↓ INLINE
    
    int val = 10 + 5;               ← constants now visible!
    int dead = val * 42;            ← still looks potentially alive
    if (val > 0) { return val+1; }  ← condition still symbolic
    else { return val-100; }

         ↓ SCCP

    // val = 15 (constant propagated)
    int dead = 630;                 ← computed but unused? maybe...
    if (true) { return 16; }        ← condition resolved!
    else { /* unreachable */ }

         ↓ SIMPLIFYCFG

    int dead = 630;                 ← dead branch removed, but dead is still here
    return 16;

         ↓ DCE

    return 16;                      ← dead = 630 was unused → REMOVED!
```

**Key educational takeaway:** Function inlining alone doesn't remove dead code. It's the **combination** of passes that achieves the full optimization. This is why modern compilers run many passes in sequence — each creates opportunities for the next.

---

## 4. IR → Pseudo-C Reconstruction

### 4.1 Approach

The `CReconstructor` class performs a **line-by-line regex-based translation** of LLVM IR into pseudo-C. This is explicitly **not a decompiler** — the output is for educational understanding only.

### 4.2 Translation Table

| LLVM IR Pattern | Pseudo-C Output |
|-----------------|-----------------|
| `define i32 @func(i32 %0)` | `int func(int arg0) {` |
| `%3 = add nsw i32 %0, %1` | `int t3 = arg0 + arg1;` |
| `%x = call i32 @func(i32 10)` | `int x = func(10);` |
| `%c = icmp sgt i32 %a, 0` | `bool c = (a > 0);` |
| `br i1 %c, label %t, label %f` | `if (c) goto t; else goto f;` |
| `br label %target` | `goto target;` |
| `ret i32 %x` | `return x;` |
| `%x = phi i32 [%a, %bb1], [%b, %bb2]` | `int x = φ(a from bb1, b from bb2);` |
| `store i32 %val, ptr %dest` | `*dest = val;` |
| `%x = load i32, ptr %src` | `int x = *src;` |
| `%x = alloca i32` | `int x;  /* stack allocation */` |
| `%x = select i1 %c, i32 %t, i32 %f` | `auto x = c ? t : f;` |
| `%x = sext i32 %v to i64` | `long x = (long)v;` |
| `unreachable` | `/* UNREACHABLE */;` |

### 4.3 SSA Naming Conventions

| IR Name | C Name | Rule |
|---------|--------|------|
| `%0`, `%1` (function params) | `arg0`, `arg1` | Parameters get readable names |
| `%3`, `%4` (temporaries) | `t3`, `t4` | Prefix with `t` to avoid bare numbers |
| `%myvar` (named) | `myvar` | Strip `%` prefix |
| `4:` (numeric label) | `lbl_4:` | Prefix with `lbl_` for valid identifier |
| `entry:` (first label) | `// entry block` | Comment instead of label |

---

## 5. Statistics Computation

The IR parser uses regex matching on the raw IR text to count constructs:

| Metric | How Counted |
|--------|-------------|
| **Instructions** | Any indented line that isn't a label, comment (`;`), or metadata (`!`) |
| **Functions** | Lines matching `define ...` |
| **Calls** | Lines matching `[tail] call ...` (including assignment form) |
| **Branches** | Lines matching `br ...` |
| **Basic Blocks** | Label count + function count (entry block is implicit per `define`) |

These metrics are computed at each pipeline stage, enabling quantitative comparison of optimization effectiveness.

---

## 6. External Tools and Dependencies

| Tool | Version | Purpose | Required |
|------|---------|---------|----------|
| Python | 3.11+ | Runtime | Yes |
| Textual | ≥3.0.0 | Terminal UI framework | Yes |
| Rich | ≥13.0.0 | Text formatting, syntax highlighting | Yes |
| LLVM `opt` | Any modern version | Optimization pass execution | Yes |
| `clang` | Any modern version | C → LLVM IR compilation | Yes |

### Tool Discovery

Both `clang` and `opt` are located at runtime via `shutil.which()`, which searches the system `PATH`. If either tool is not found, a descriptive error message is shown with installation instructions for common Linux distributions and macOS.
