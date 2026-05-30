/*
 * Test 5: Recursive Function — FAILURE / LIMITATION CASE
 * ========================================================
 * Demonstrates a case where function inlining CANNOT help.
 *
 * Recursive functions cannot be fully inlined because inlining would
 * require infinite expansion. LLVM's inline pass will NOT inline the
 * recursive call to factorial(), so:
 *
 *   1. Inlining   → NO EFFECT on the recursive call
 *   2. SCCP       → Limited effect (cannot resolve runtime-dependent values)
 *   3. SimplifyCFG → May simplify some branch structure
 *   4. DCE        → Limited effect (most code is live)
 *
 * This test case shows that our optimization pipeline has LIMITATIONS:
 * - Recursive algorithms retain their call overhead
 * - The optimizer cannot compute factorial(5) = 120 at compile time
 *   because it would need to "run" the recursion
 *
 * Expected: The function mostly survives all passes unchanged.
 */

int factorial(int n) {
    if (n <= 1)
        return 1;
    return n * factorial(n - 1);    /* Recursive — CANNOT be inlined */
}

int test_recursive() {
    int result = factorial(5);       /* Call to recursive fn — stays */
    return result;
}

int main() {
    return test_recursive();
}
