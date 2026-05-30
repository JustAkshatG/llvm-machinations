/*
 * Test 4: Mixed Live and Dead Code with Branches
 * =================================================
 * Complex function with multiple branches where some paths are dead
 * and some computations are unused. Tests interaction between
 * branch folding and dead code elimination.
 *
 * Expected optimizations:
 *   1. Inlining   → max_val(10, 3) and min_val(10, 3) are inlined
 *   2. SCCP       → max_val(10,3) = 10, min_val(10,3) = 3
 *                    10 == 3 is false → else branch taken
 *   3. SimplifyCFG → 'if' branch removed (condition is always false)
 *   4. DCE        → 'dead_sum' is eliminated
 *
 * Final expected result: returns 7 (= 10 - 3)
 */

int max_val(int a, int b) {
    if (a > b) return a;
    return b;
}

int min_val(int a, int b) {
    if (a < b) return a;
    return b;
}

int test_mixed() {
    int big   = max_val(10, 3);     /* Inline → 10 */
    int small = min_val(10, 3);     /* Inline → 3  */

    int dead_sum = big + small;     /* Dead: never used → DCE */

    /* Constant condition: big == small → 10 == 3 → false */
    if (big == small) {
        return 0;                   /* Unreachable → SimplifyCFG removes */
    } else {
        return big - small;         /* Survives: 10 - 3 = 7 */
    }
}

int main() {
    return test_mixed();
}
