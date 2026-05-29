# C Source → IR → Reconstructed C — Implementation Plan

Transform the LLVM Explorer from `.ll`-only input to **C source input** with a three-panel display showing Original C, LLVM IR, and Reconstructed C side-by-side.

## Proposed Changes

---

### New Module: C Reconstructor

#### [NEW] [c_reconstructor.py](file:///run/media/akshat/New%20Volume/Akshat/RVCE/Subjects/Sem%206/Compiler%20Design/EL/llvm-machinations/llvm_explorer/c_reconstructor.py)

A regex-based LLVM IR → pseudo-C translator. **Not a real decompiler** — the goal is educational visualization.

**Approach:** Parse the IR line-by-line, recognizing:
- `define` → C function signatures (`int compute() {`)
- `%x = add i32 %a, %b` → `int x = a + b;`
- `%x = call i32 @func(...)` → `int x = func(...);`
- `br i1 %cond, label %t, label %f` → `if (cond) goto t; else goto f;`
- `br label %target` → `goto target;`
- `ret i32 %x` → `return x;`
- `%x = icmp sgt i32 %a, %b` → `bool x = (a > b);`
- `%x = phi i32 [%a, %bb1], [%b, %bb2]` → `int x = φ(a from bb1, b from bb2);`
- `store`, `load`, `alloca` → memory operations in C-like syntax
- Labels → `label_name:` (preserved as goto targets)
- Dead/unreachable code → annotated with `/* DEAD */` or `/* UNREACHABLE */`

Each function body is reconstructed independently. The output is a pseudo-C string that reads like C but may not compile — it's for understanding only.

**Key class:** `CReconstructor`
- `reconstruct(ir_text: str) → str` — main entry point, returns pseudo-C
- Internal helpers for each IR instruction type
- Maps SSA `%name` variables to readable C-like names
- Annotates removed code with comments (for educational purposes)

---

### Modified: Pipeline

#### [MODIFY] [pipeline.py](file:///run/media/akshat/New%20Volume/Akshat/RVCE/Subjects/Sem%206/Compiler%20Design/EL/llvm-machinations/llvm_explorer/pipeline.py)

Changes:
1. Add `_find_clang()` — locate `clang` in PATH
2. Add `compile_c_to_ir(c_file, output_ll)` — run `clang -S -emit-llvm -O0 -o output.ll input.c`
3. Add `reconstructed_c: str` field to `OptimizationStage` dataclass
4. After each pass, call `CReconstructor.reconstruct()` to generate pseudo-C
5. Store original C source in a new `original_c: str` field on the pipeline result
6. Save reconstructed C files as `0_original_reconstructed.c` … `4_dce_reconstructed.c`

---

### Modified: File Manager

#### [MODIFY] [file_manager.py](file:///run/media/akshat/New%20Volume/Akshat/RVCE/Subjects/Sem%206/Compiler%20Design/EL/llvm-machinations/llvm_explorer/file_manager.py)

Changes:
1. Rename `validate_ll_file` → `validate_input_file`
2. Accept both `.c` and `.ll` files
3. Add `generate_report()` support for reconstructed C sections
4. Update report to include reconstructed C diffs

---

### Modified: TUI Application

#### [MODIFY] [app.py](file:///run/media/akshat/New%20Volume/Akshat/RVCE/Subjects/Sem%206/Compiler%20Design/EL/llvm-machinations/llvm_explorer/app.py)

**New three-panel layout:**

```
┌──────────┬─────────────────┬────────────────────┬──────────────────┐
│ Timeline │   Original C    │     LLVM IR        │ Reconstructed C  │
│ Sidebar  │   (read-only)   │   (per stage)      │  (per stage)     │
│          │                 │                    │                  │
│          ├─────────────────┴────────────────────┴──────────────────┤
│          │          Bottom Panel (diff / stats / help)             │
└──────────┴────────────────────────────────────────────────────────┘
```

Changes:
1. Three `RichLog` panels side by side: Original C (static), IR (per-stage), Reconstructed C (per-stage)
2. `c` keybinding to toggle "Reconstructed C Diff" mode in the bottom panel — shows diff between consecutive reconstructed C versions
3. Original C panel stays constant across all stages (the source file)
4. IR and Reconstructed C panels update when stage changes
5. Presentation mode shows IR + Reconstructed C (hides sidebar + original C)
6. Update usage text/help to reference `.c` files

**New keybinding:** `c` — toggle reconstructed C diff (shows what changed in pseudo-C between stages)

---

### New Example Files

#### [NEW] [examples/sample1.c](file:///run/media/akshat/New%20Volume/Akshat/RVCE/Subjects/Sem%206/Compiler%20Design/EL/llvm-machinations/llvm_explorer/examples/sample1.c)

C source demonstrating inlining → DCE pipeline:

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

#### [NEW] [examples/sample2.c](file:///run/media/akshat/New%20Volume/Akshat/RVCE/Subjects/Sem%206/Compiler%20Design/EL/llvm-machinations/llvm_explorer/examples/sample2.c)

Second example with multiple function call chains.

---

### Unchanged Modules

- **ir_parser.py** — no changes needed
- **statistics.py** — no changes needed
- **diff_viewer.py** — no changes needed (it's generic enough to diff any text)

---

### Updated Meta Files

#### [MODIFY] [README.md](file:///run/media/akshat/New%20Volume/Akshat/RVCE/Subjects/Sem%206/Compiler%20Design/EL/llvm-machinations/README.md)

- Update usage from `.ll` to `.c` files
- Document new three-panel layout and keybindings
- Update architecture diagram

---

## Open Questions

> [!NOTE]
> **Should `.ll` files still be accepted?** I plan to support both: if the input is `.c`, compile to IR first; if `.ll`, skip compilation (but the Original C panel will show "N/A — loaded from IR directly"). This keeps backward compatibility. Let me know if you want `.c`-only.

## Verification Plan

### Automated Tests

```bash
cd llvm_explorer && source .venv/bin/activate

# 1. Test C compilation
python3 -c "from pipeline import OptimizationPipeline; p = OptimizationPipeline(); ..."

# 2. Test reconstructor on known IR
python3 -c "from c_reconstructor import CReconstructor; r = CReconstructor(); print(r.reconstruct(open('output/0_original.ll').read()))"

# 3. Full pipeline with C input
python app.py examples/sample1.c

# 4. Verify output files
ls output/  # expect .ll files + .c reconstructed files
```

### Manual Verification

- Verify three-panel layout renders correctly
- Step through stages: Original C stays, IR changes, Reconstructed C changes
- Press `d` for IR diff, `c` for reconstructed C diff
- Press `p` for presentation mode (IR + reconstructed C only)
- Press `e` for report export with reconstructed C sections
