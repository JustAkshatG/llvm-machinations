/*
 * Test 6: Minimal Optimization Opportunity
 * ==========================================
 * A simple program with no helper function calls and where all
 * computations are live (used in the final return value).
 *
 * This tests the "nothing to optimize" scenario:
 *
 *   1. Inlining   → NO EFFECT (no function calls to inline within compute)
 *   2. SCCP       → Constants propagated (3 + 7 = 10, 3 * 7 = 21, 10 + 21 = 31)
 *   3. SimplifyCFG → May merge basic blocks
 *   4. DCE        → NO EFFECT (all variables are used)
 *
 * Key insight: DCE has nothing to remove because every computation
 * contributes to the return value. This shows that DCE is only effective
 * when prior passes (especially inlining) create dead code.
 *
 * Expected: SCCP constant-folds everything, but DCE contributes nothing.
 */

int test_all_live() {
    int a = 3;
    int b = 7;
    int sum = a + b;            /* Live: used in result */
    int product = a * b;        /* Live: used in result */
    int result = sum + product;  /* Live: returned */
    return result;               /* Returns 31 */
}

int main() {
    return test_all_live();
}
