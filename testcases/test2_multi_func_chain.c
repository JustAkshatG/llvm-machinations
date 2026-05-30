/*
 * Test 2: Multi-Function Call Chain
 * ===================================
 * A chain of three functions where each calls the next.
 * Inlining collapses the entire chain, enabling full constant propagation.
 *
 * Expected optimizations:
 *   1. Inlining   → add() inlined into double_it(), double_it() into quad()
 *   2. SCCP       → quad(3) = double_it(double_it(3)) = double_it(6) = 12
 *   3. SimplifyCFG → 12 > 100 is false, 'if' branch removed
 *   4. DCE        → 'waste' variable eliminated
 *
 * Final expected result: test_chain() returns 13 (= 12 + 1)
 */

int add(int a, int b) {
    return a + b;
}

int double_it(int x) {
    return add(x, x);    /* Calls add — two levels deep */
}

int quad(int x) {
    return double_it(double_it(x));   /* Four levels of inlining */
}

int test_chain() {
    int val = quad(3);           /* After full inline+SCCP: val = 12 */
    int waste = val * val;       /* Dead: never used → DCE */

    if (val > 100) {
        return val + 999;        /* Unreachable: 12 > 100 is false */
    } else {
        return val + 1;          /* Survives: returns 13 */
    }
}

int main() {
    return test_chain();
}
