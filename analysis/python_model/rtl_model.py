"""
rtl_model.py  (v2 — RTL-accurate)
===================================
Bit-exact Python model of the supplied SystemVerilog arithmetic.

RTL INSPECTION FINDINGS (do not change without re-inspecting the .sv files):
--------------------------------------------------------------------------
MULTIPLIER (approximate_multiplier_8bit.sv):
  1. Partial products:  pp[i][j] = A[i] & B[j]          (lines 55-59)
  2. Truncation:        pp_t[i][j] = 0 if (i+j) < approx_level  (lines 69-78)
  3. For approx_level=3 ONLY: compressor block (lines 114-133)
     CRITICAL: The compressor reads pp_t[0][2], pp_t[1][1], pp_t[2][0].
     These are the column-2 terms.  Column index of pp[i][j] = i+j = 2,
     which is < approx_level=3, so they were ALREADY ZEROED by the truncation
     loop.  Therefore t0=t1=t2=0, s_bit=0, c_bit=0, and col_sum[2] and
     col_sum[3] are both unchanged from the truncation result.
     CONCLUSION: at L3, the compressor has NO effect.  The behavior is
     identical to truncating columns 0, 1, and 2 (i.e., zeroing all
     partial products with column index < 3).
  4. Final ripple-carry: sums column carry chains, outputs 16-bit P  (lines 139-145)

  CORRECTION from old model: the old model used pre-truncation pp values
  inside the L3 compressor, introducing a spurious positive bias (+2.125).
  The RTL-accurate model has L3 purely negative-biased (mean = -4.25).

ADDER (approx_adder_16bit.sv):
  XOR-only boundary per level (lines 47-53):
    L0: xor_bound = 0   (all bits exact ripple-carry)
    L1: xor_bound = 2   (bits 0-1 XOR-only, carry frozen at 0 through boundary)
    L2: xor_bound = 4   (bits 0-3 XOR-only)
    L3: xor_bound = 8   (bits 0-7 XOR-only)
  For k < xor_bound:  Sum[k] = A[k] ^ B[k], carry unchanged (stays 0)
  For k >= xor_bound: standard ripple-carry with carry-in = 0 from boundary
  (lines 57-73)

MAC WRAPPER (approx_mac_8bit.sv):
  Both sub-blocks share approx_level.
  Acc <= Acc + product on posedge clk when en=1
  Async active-low reset sets Acc = 0  (lines 49-54)

VALIDATION STATUS:
  - L0 mult: confirmed exact for all 65,536 pairs (exact match 100%)
  - L1 mult: confirmed by exhaustive characterization
  - L2 mult: confirmed by exhaustive characterization
  - L3 mult: RTL-accurate model confirmed by code trace; old model was wrong
  - L0 adder: confirmed exact
  - L1-L3 adder: confirmed by directed + sampled characterization
  - No HDL simulator available: RTL vs Python confirmed by code reading only.
"""

# ============================================================
# MULTIPLIER
# ============================================================

def approx_multiply(A: int, B: int, level: int) -> int:
    """
    RTL-accurate 8x8 -> 16-bit unsigned approximate multiplier.

    Matches approximate_multiplier_8bit.sv exactly.
    L3 compressor reads pp_t (already zeroed by truncation) -> no effect.
    """
    assert 0 <= A <= 255 and 0 <= B <= 255
    assert 0 <= level <= 3
    level = int(level)

    # Step 1: generate partial products
    pp = [[(( A>>i)&1)&((B>>j)&1) for j in range(8)] for i in range(8)]

    # Step 2: column-wise truncation  (i+j < level => 0)
    pp_t = [[pp[i][j] if (i+j) >= level else 0 for j in range(8)]
            for i in range(8)]

    # Step 3: accumulate column sums from pp_t
    col_sum = [0] * 15
    for i in range(8):
        for j in range(8):
            if i + j < 15:
                col_sum[i + j] += pp_t[i][j]

    # Step 4: approximate compressor at level 3
    # RTL reads pp_t[0][2], pp_t[1][1], pp_t[2][0] — all already zero.
    # The compressor therefore has no effect; result is pure truncation.
    if level == 3:
        t0 = pp_t[0][2]   # 0 (already zeroed by truncation)
        t1 = pp_t[1][1]   # 0
        t2 = pp_t[2][0]   # 0
        s_bit = t0 ^ t1 ^ t2          # 0
        c_bit = t0 | t1 | t2          # 0
        col_sum[2] = s_bit             # still 0
        col_sum[3] = col_sum[3] - pp_t[0][2] - pp_t[1][1] - pp_t[2][0] + c_bit
        # col_sum[3] unchanged

    # Step 5: ripple-carry reduction
    result = 0
    carry  = 0
    for k in range(15):
        total     = col_sum[k] + carry
        result   |= (total & 1) << k
        carry     = total >> 1
    result |= (carry & 1) << 15
    return result & 0xFFFF


# ============================================================
# ADDER
# ============================================================

XOR_BOUND = {0: 0, 1: 2, 2: 4, 3: 8}

def approx_add(A: int, B: int, level: int) -> int:
    """
    RTL-accurate 16-bit approximate adder.

    Matches approx_adder_16bit.sv exactly.
    """
    assert 0 <= A <= 65535 and 0 <= B <= 65535
    assert 0 <= level <= 3
    xb = XOR_BOUND[int(level)]
    result = 0
    carry  = 0
    for k in range(16):
        a_bit = (A >> k) & 1
        b_bit = (B >> k) & 1
        if k < xb:
            # XOR-only: no carry in or out
            result |= (a_bit ^ b_bit) << k
            # carry stays 0
        else:
            s      = a_bit ^ b_bit ^ carry
            carry  = (a_bit & b_bit) | (a_bit & carry) | (b_bit & carry)
            result |= s << k
    return result & 0xFFFF


# ============================================================
# EXACT REFERENCE
# ============================================================

def exact_multiply(A: int, B: int) -> int:
    return (A * B) & 0xFFFF


def exact_add(A: int, B: int) -> int:
    return (A + B) & 0xFFFF


# ============================================================
# MAC STEP
# ============================================================

def approx_mac_step(Acc: int, A: int, B: int,
                    mult_level: int, add_level: int,
                    en: bool = True) -> int:
    """One clock-edge MAC step.  Returns new Acc."""
    if not en:
        return Acc & 0xFFFF
    product  = approx_multiply(A, B, mult_level)
    acc_next = approx_add(product, Acc, add_level)
    return acc_next & 0xFFFF


def exact_mac_step(Acc: int, A: int, B: int, en: bool = True) -> int:
    """One clock-edge exact MAC step."""
    if not en:
        return Acc & 0xFFFF
    return (Acc + A * B) & 0xFFFF


# ============================================================
# SEQUENCE RUNNERS
# ============================================================

def run_approx_sequence(operands, mult_levels, add_levels,
                        enable_mask=None, reset_mask=None,
                        initial_acc: int = 0):
    """
    Run a complete approximate MAC sequence.

    mult_levels / add_levels: int (constant) or list (per-step).
    Returns dict with traces and final_acc.
    """
    n = len(operands)
    en_mask  = enable_mask if enable_mask is not None else [True] * n
    rst_mask = reset_mask  if reset_mask  is not None else [False] * n
    mls = [mult_levels] * n if isinstance(mult_levels, int) else list(mult_levels)
    als = [add_levels]  * n if isinstance(add_levels,  int) else list(add_levels)

    acc = initial_acc & 0xFFFF
    acc_trace, prod_trace, ml_used, al_used = [], [], [], []

    for idx in range(n):
        A, B = operands[idx]
        if rst_mask[idx]:
            acc = 0
        product = approx_multiply(A, B, mls[idx])
        prod_trace.append(product)
        if en_mask[idx]:
            acc = approx_add(product, acc, als[idx])
        acc_trace.append(acc)
        ml_used.append(mls[idx])
        al_used.append(als[idx])

    return {'acc_trace': acc_trace, 'product_trace': prod_trace,
            'mult_levels': ml_used, 'add_levels': al_used,
            'final_acc': acc}


def run_exact_sequence(operands, enable_mask=None, reset_mask=None,
                       initial_acc: int = 0):
    """Run exact MAC reference sequence."""
    n = len(operands)
    en_mask  = enable_mask if enable_mask is not None else [True] * n
    rst_mask = reset_mask  if reset_mask  is not None else [False] * n

    acc = initial_acc & 0xFFFF
    unbounded = initial_acc
    acc_trace, prod_trace, unb_trace = [], [], []

    for idx in range(n):
        A, B = operands[idx]
        if rst_mask[idx]:
            acc = 0
            unbounded = 0
        product = A * B
        prod_trace.append(product)
        if en_mask[idx]:
            acc       = (acc + product) & 0xFFFF
            unbounded += product
        acc_trace.append(acc)
        unb_trace.append(unbounded)

    return {'acc_trace': acc_trace, 'product_trace': prod_trace,
            'unbounded_trace': unb_trace, 'final_acc': acc}


# ============================================================
# SELF-TEST  (run with:  python rtl_model.py)
# ============================================================

if __name__ == '__main__':
    import random, sys

    errs = 0

    # --- Multiplier L0: exhaustive
    for A in range(256):
        for B in range(256):
            got = approx_multiply(A, B, 0)
            want = A * B
            if got != want:
                print(f'FAIL mult L0: A={A} B={B} want={want} got={got}')
                errs += 1
    print(f'Mult L0 exhaustive: {"PASS" if errs==0 else "FAIL"} ({errs} errors)')

    # --- Adder L0: exhaustive subset
    add_errs = 0
    rng = random.Random(42)
    for _ in range(50_000):
        a = rng.randint(0, 65535)
        b = rng.randint(0, 65535)
        want = (a + b) & 0xFFFF
        got  = approx_add(a, b, 0)
        if got != want:
            add_errs += 1
    print(f'Adder L0 50k random: {"PASS" if add_errs==0 else "FAIL"} ({add_errs} errors)')

    # --- L3 multiplier: must be purely negative or zero error
    l3_pos = 0
    for A in range(256):
        for B in range(256):
            err = approx_multiply(A, B, 3) - A*B
            if err > 0:
                l3_pos += 1
    print(f'L3 mult positive errors (must be 0): {l3_pos}  {"PASS" if l3_pos==0 else "FAIL-check RTL"}')

    # --- MAC sequence L0/L0 must match exact
    ops = [(10, 20), (30, 40), (50, 60), (255, 255)]
    res_approx = run_approx_sequence(ops, 0, 0)
    res_exact  = run_exact_sequence(ops)
    match = res_approx['final_acc'] == res_exact['final_acc']
    print(f'MAC L0/L0 vs exact: {"PASS" if match else "FAIL"} '
          f'(approx={res_approx["final_acc"]} exact={res_exact["final_acc"]})')

    if errs + add_errs + l3_pos > 0 or not match:
        print('SELF-TEST FAILED')
        sys.exit(1)
    print('SELF-TEST PASSED')
