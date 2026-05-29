/*
 * sample2.c — LLVM Optimization Explorer Demo (Multi-function)
 * =============================================================
 * A more involved example with a chain of function calls and multiple
 * dead-code / constant-propagation opportunities.
 *
 *   1. Inlining   → double_val() and negate() are inlined into transform()
 *   2. SCCP       → constant 7 propagates: double_val(7)=14, negate(3)=-3
 *   3. SimplifyCFG → 14 > 100 is false, so the 'yes' branch is removed
 *   4. DCE        → 'unused' and 'also_dead' computations are eliminated
 */

/* Doubles its argument using a left shift */
int double_val(int x) {
    return x << 1;
}

/* Negates its argument */
int negate(int x) {
    return 0 - x;
}

/* Applies a chain of transformations on constant inputs */
int transform() {
    /* Both calls use constants → inline + SCCP */
    int a = double_val(7);    /* will become 14 */
    int b = negate(3);        /* will become -3 */

    /* Dead computation — 'unused' is never read → DCE target */
    int unused = a + b;

    /* Constant comparison: 14 > 100 is false → branch folded */
    if (a > 100) {
        /* Unreachable — will be removed by SimplifyCFG */
        return a + 999;
    } else {
        /* This path survives: returns 15 */
        int also_dead = b * b;  /* unused → DCE target */
        return a + 1;
    }
}

int main() {
    return transform();
}
