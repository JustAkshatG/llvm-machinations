/*
 * Test 1: Basic Function Inlining + Dead Code Elimination
 * ========================================================
 * Demonstrates the fundamental inline → DCE chain.
 *
 * Expected optimizations:
 *   1. Inlining   → square(5) is inlined into test_basic(), body becomes 5 * 5
 *   2. SCCP       → 5 * 5 = 25 is computed at compile time
 *   3. SimplifyCFG → the always-true branch (25 > 0) is folded
 *   4. DCE        → 'unused' variable (square(3) = 9) is eliminated
 *
 * Final expected result: test_basic() returns 26 (= 25 + 1)
 */

/* Small pure function — ideal inlining candidate */
int square(int x) {
    return x * x;
}

int test_basic() {
    int result = square(5);     /* Inline: becomes 5 * 5 = 25 */
    int unused = square(3);     /* Dead: result never read → DCE removes */

    /* Constant condition after SCCP: 25 > 0 is always true */
    if (result > 0) {
        return result + 1;      /* Survives: returns 26 */
    } else {
        return result - 1;      /* Unreachable → SimplifyCFG removes */
    }
}

int main() {
    return test_basic();
}
