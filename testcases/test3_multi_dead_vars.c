/*
 * Test 3: Multiple Dead Variables After Inlining
 * ================================================
 * Several computations become dead after inlining exposes constants.
 * Tests that DCE can remove a cascade of dependent dead instructions.
 *
 * Expected optimizations:
 *   1. Inlining   → offset() inlined with constants 10, 20
 *   2. SCCP       → a = 30, b = 30 + 5 = 35, c = 30 * 2 = 60
 *   3. SimplifyCFG → no conditional branches to simplify here
 *   4. DCE        → dead1, dead2, dead3 are all unused → eliminated
 *
 * Final expected result: returns 125 (= 30 + 35 + 60)
 */

int offset(int x, int y) {
    return x + y;
}

int test_multi_dead() {
    int a = offset(10, 20);      /* Inline → 30 */
    int b = a + 5;               /* Live: used in return → 35 */
    int c = a * 2;               /* Live: used in return → 60 */

    /* Cascade of dead computations — none are read */
    int dead1 = a * a;           /* Dead → DCE */
    int dead2 = dead1 + b;       /* Dead (depends on dead1) → DCE */
    int dead3 = dead2 * c;       /* Dead (depends on dead2) → DCE */

    return a + b + c;            /* Only live path: 30 + 35 + 60 = 125 */
}

int main() {
    return test_multi_dead();
}
