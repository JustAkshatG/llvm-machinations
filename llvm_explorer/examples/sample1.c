/*
 * sample1.c — LLVM Optimization Explorer Demo
 * =============================================
 * This sample demonstrates how four optimization passes transform C code:
 *
 *   1. Inlining   → add_offset() is inlined into compute()
 *   2. SCCP       → constants 10 + 5 = 15 are propagated, 15 > 0 = true
 *   3. SimplifyCFG → the always-true branch is folded, else block removed
 *   4. DCE        → the unused 'dead' variable is eliminated
 *
 * The primary goal: show how function inlining enables dead code elimination.
 * Without inlining, the compiler can't see through the call boundary to
 * discover that 'dead' is unused and the branch is always taken.
 */

/* Small helper — a good inlining candidate */
int add_offset(int x, int offset) {
    return x + offset;
}

/* Main computation with several optimization opportunities */
int compute() {
    /* Call with constant arguments → inline + SCCP opportunity */
    int val = add_offset(10, 5);

    /* Unused computation — result never read → DCE target
       (only visible as dead AFTER inlining exposes the constant) */
    int dead = val * 42;

    /* Constant condition (val == 15, which is > 0) → SimplifyCFG */
    if (val > 0) {
        return val + 1;    /* This path survives: returns 16 */
    } else {
        return val - 100;  /* Unreachable after constant propagation */
    }
}

int main() {
    return compute();
}
