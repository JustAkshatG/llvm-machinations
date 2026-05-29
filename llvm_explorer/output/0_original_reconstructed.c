/* ═══ Reconstructed C (educational — not compilable) ═══ */

int add_offset(int arg0, int arg1) {
    int t3 = arg0 + arg1;
    return t3;
}

int compute() {
    int t1 = add_offset(10, 5);
    int t2 = t1 * 42;
    bool t3 = (t1 > 0);
    if (t3) goto lbl_4; else goto lbl_6;

lbl_4:
    int t5 = t1 + 1;
    goto lbl_8;

lbl_6:
    int t7 = t1 - 100;
    goto lbl_8;

lbl_8:
    int .0 = φ(t5 from lbl_4, t7 from lbl_6);
    return .0;
}

int main() {
    int t1 = compute();
    return t1;
}
