"""
controllers_v2.py
=================
All five required control methods.

Each method is a Python class with:
  decide(A, B, Acc) -> (mult_level, add_level)
  update(ml, al, en)  -- called AFTER the MAC step (for stateful controllers)
  reset()             -- called at workload start / on rst_n
  info()              -- returns metadata dict

INFORMATION VISIBILITY RULES (enforced below):
  Observable at runtime by any controller:
    A [7:0], B [7:0], Acc [15:0], en, rst_n
  Observable only offline (Python evaluator, not a real controller):
    exact product A*B, exact next acc
  Calibration data (measured beforehand, stored as constants):
    pre-computed error bounds per level

METHOD 1: Fixed shared level (4 instances: L0,L1,L2,L3)
METHOD 2: Adaptive dual-level (mult_level AND add_level chosen independently)
METHOD 3: Threshold-based controller (mult AND adder, explicit thresholds)
METHOD 4: Error-budget controller (mult AND adder, no exact runtime computation)
METHOD 5: Adaptive mult, exact adder

See individual class docstrings for decision rules and RTL translation guide.
"""

# ============================================================
# CALIBRATION DATA  (derived from characterize.py output)
# These are empirical, not mathematically guaranteed bounds.
# ============================================================

# Multiplier: exhaustive 65536-pair results per level
MULT_STATS = {
    # level: (mean_signed, MAE, max_abs)
    0: (  0.0000,  0.0000,  0),
    1: ( -0.2500,  0.2500,  1),
    2: ( -1.2500,  1.2500,  5),
    3: ( -4.2500,  4.2500, 17),
}
# Note: L3 max_abs=17 (RTL-accurate). Old model had max_abs=8 (wrong).

# Adder: MAC-reachable sampled 50k per level (max observed — NOT proven bounds)
ADDER_MAC_MAX_SAMPLED = {0: 0, 1: 6, 2: 65535, 3: 65535}

# Adder: XOR region widths (from RTL)
ADDER_XOR_BITS = {0: 0, 1: 2, 2: 4, 3: 8}

# Multiplier: max absolute error per level (exhaustive — proven)
MULT_MAX_ABS = {0: 0, 1: 1, 2: 5, 3: 17}

# ============================================================
# METHOD 1: Fixed Shared Level
# ============================================================

class Method1Fixed:
    """
    Fixed universal approximation level: both mult and adder at the same level.
    No decision logic — level is a construction parameter.
    This is the baseline, not an adaptive controller.

    RTL translation: hardwire approx_level = constant.
    """
    def __init__(self, level: int):
        assert 0 <= level <= 3
        self.level = level
        self._ops  = 0

    def decide(self, A: int, B: int, Acc: int):
        self._ops += 1
        return self.level, self.level

    def update(self, ml: int, al: int, en: bool = True):
        pass

    def reset(self):
        self._ops = 0

    def info(self):
        return dict(name=f'Fixed_L{self.level}_{self.level}',
                    method=1, state_bits=0,
                    adder_exact=(self.level == 0),
                    description=f'Both blocks fixed at L{self.level}. No decision logic.')


# ============================================================
# METHOD 2: Adaptive Dual-Level Controller
# ============================================================

class Method2DualAdaptive:
    """
    Adaptive controller that independently chooses mult_level AND add_level.

    Observable inputs: A, B, Acc  (no exact computation of A*B at runtime).
    Proxy: proxy = (A >> 4) * (B >> 4)  -- 4x4 product, upper nibbles only.
    This is a cheap hardware operation (4-bit multiplier, ~16 AND + adder tree).

    MULTIPLIER LEVEL DECISION:
    ---------------------------
    We need the mult approximation error to stay < 1% of the expected product.
    Worst-case errors (exhaustive, proven): L1=1, L2=5, L3=17.
    Proxy estimates product magnitude in [0, 225] (for upper nibbles 0..15 each).
    Actual product <= proxy * 256.

    Thresholds (derived from: max_abs[level] / (proxy * 256) <= 0.01):
      L3 allowed if proxy >= ceil(17/(256*0.01)) = ceil(6.6) = 7  => proxy >= 7
      L2 allowed if proxy >= ceil(5/(256*0.01))  = ceil(1.95) = 2 => proxy >= 2
      L1 always allowed (max error 1; even proxy=1 => product~256 => 1/256=0.4%)
      L0 (exact) as fallback.

    Policy (most aggressive first):
      proxy >= 7  -> mult_level = 3
      proxy >= 2  -> mult_level = 2
      proxy >= 1  -> mult_level = 1
      else        -> mult_level = 0

    ADDER LEVEL DECISION:
    ---------------------
    The adder receives: product (≤ 65025) + Acc (≤ 65535).
    Adder error propagates directly into Acc, accumulating over many cycles.
    To bound the single-step adder error to < 1% of (Acc + product):
      estimated_sum_proxy = Acc + proxy * 256  (uses proxy, not exact A*B)

    Max adder error (sampled, not proven): L0=0, L1=6.
    L2 and L3 adder errors are unbounded (max observed 65535) → never safe.

    Adder policy:
      if estimated_sum_proxy > 0 and ADDER_L1_MAX / estimated_sum_proxy <= 0.01:
        add_level = 1
      else:
        add_level = 0  (exact accumulation)

    Threshold: estimated_sum_proxy >= 600  (6/0.01 = 600)

    COMBINED RULES (RTL table):
    ---------------------------
    proxy = (A[7:4] * B[7:4])                      [4x4 unsigned mult]
    sum_proxy = Acc + proxy * 256                   [16-bit addition]

    mult_level:
      proxy >= 7  -> 3
      proxy >= 2  -> 2
      proxy >= 1  -> 1
      else        -> 0

    add_level:
      sum_proxy >= 600 -> 1
      else             -> 0

    STATE: none (stateless).
    DECISION COST: 1 × 4-bit multiply, 2 comparators (mult), 1 addition + 1 comparator (add).
    """
    def __init__(self):
        self._ops = 0
        self.level_pair_counts = {}

    def decide(self, A: int, B: int, Acc: int):
        proxy = (A >> 4) * (B >> 4)  # 0..225, hardware-computable

        # Multiplier level
        if proxy >= 7:
            ml = 3
        elif proxy >= 2:
            ml = 2
        elif proxy >= 1:
            ml = 1
        else:
            ml = 0

        # Adder level — use proxy-based sum estimate (no exact A*B)
        sum_proxy = Acc + proxy * 256  # upper bound estimate
        if sum_proxy >= 600:
            al = 1
        else:
            al = 0

        self._ops += 1
        self.level_pair_counts[(ml, al)] = self.level_pair_counts.get((ml, al), 0) + 1
        return ml, al

    def update(self, ml: int, al: int, en: bool = True):
        pass  # stateless

    def reset(self):
        self._ops = 0
        self.level_pair_counts = {}

    def info(self):
        return dict(name='DualAdaptive',
                    method=2, state_bits=0,
                    adder_exact=False,
                    description=(
                        'Proxy-based dual controller. '
                        'Mult: upper-nibble proxy product thresholds. '
                        'Adder: L1 when estimated sum >= 600, else L0. '
                        'No exact A*B computed by controller. '
                        'Adder never uses L2 or L3 (unbounded sampled errors).'))


# ============================================================
# METHOD 3: Threshold-Based Controller (Explicit Bit-Pattern Checks)
# ============================================================

class Method3Threshold:
    """
    Threshold-based controller using simple comparisons and bit patterns.
    Independently selects mult_level and add_level.

    Observable inputs: A, B, Acc.
    No arithmetic more expensive than a right-shift and comparison.

    MULTIPLIER LEVEL DECISION (using leading-bit detection):
    --------------------------------------------------------
    Classify operand pair by the highest set bit position of each operand.
    Hardware: leading-one detector (log2-approximation).

    msb_A = highest set bit of A (0 if A=0)
    msb_B = highest set bit of B (0 if B=0)
    min_msb = min(msb_A, msb_B)

    Rationale: the product has at most msb_A + msb_B + 2 significant bits.
    Truncating lower partial-product columns is safer when the product is large.

    Thresholds (derived from max error / min_product analysis):
      L3 (max error 17): safe when min_msb >= 4  (product >= 2^8 = 256, 17/256 = 6.6%)
                         — actually 17/256 > 1%, so L3 is only used when product >= 1700
                         — conservative: min_msb >= 5 (product >= 2^10 = 1024, 17/1024 = 1.7%)
                         — min_msb >= 6 => product >= 2^12 = 4096, 17/4096 = 0.4%  [safe]
      L2 (max error 5):  safe when product >= 500, min_msb >= 4 (product >= 256, 5/256=2%) 
                         — min_msb >= 5 => product >= 1024, 5/1024=0.5% [safe]
      L1 (max error 1):  safe when product >= 100, min_msb >= 3 (product >= 64, 1/64=1.6%)
                         — min_msb >= 4 => product >= 256, 1/256=0.4% [safe]
      L0: always safe.

    Policy:
      if min(msb_A, msb_B) >= 6 -> L3
      if min(msb_A, msb_B) >= 5 -> L2
      if min(msb_A, msb_B) >= 4 -> L1
      else                       -> L0

    ADDER LEVEL DECISION (accumulator boundary check):
    ---------------------------------------------------
    Risk: when Acc is near 65535 (or near 0 after wraparound), a carry-suppression
    error from the adder XOR region can cause large relative errors.

    Also: when Acc is large (far from 0 and 65535), adder L1 error (max 6) is tiny
    relative to Acc.

    Safe-to-use-L1 condition:
      The XOR region suppresses carries. For L1, bits 0-1 are XOR-only, max error = 6.
      Relative error = 6 / (Acc + product).
      For 1% safety: Acc + product_estimate >= 600.
      Product estimate using msb: upper_product_bound = 2^(msb_A + msb_B + 2).
      Conservative sum estimate = Acc (we have this exactly).

    Wraparound risk: if Acc > 65000, the upper sum may wrap.
    We use a simple check: add_level = 0 (exact) if Acc > 64900 OR Acc < 100.
    Otherwise add_level = 1 if Acc >= 600.

    RTL translation:
      msb_A = clog2(A) -- leading-one position (7 gates deep)
      msb_B = clog2(B)
      min_msb = (msb_A < msb_B) ? msb_A : msb_B
      mult_level = (min_msb>=6) ? 3 : (min_msb>=5) ? 2 : (min_msb>=4) ? 1 : 0
      boundary   = (Acc > 64900) || (Acc < 100)
      add_level  = (!boundary && Acc >= 600) ? 1 : 0
    """

    @staticmethod
    def _msb(x):
        """Position of the highest set bit (0 if x=0)."""
        if x == 0:
            return 0
        m = 0
        while x >> (m + 1):
            m += 1
        return m

    def __init__(self):
        self._ops = 0
        self.level_pair_counts = {}

    def decide(self, A: int, B: int, Acc: int):
        msb_a = self._msb(A)
        msb_b = self._msb(B)
        min_msb = min(msb_a, msb_b)

        if min_msb >= 6:
            ml = 3
        elif min_msb >= 5:
            ml = 2
        elif min_msb >= 4:
            ml = 1
        else:
            ml = 0

        near_boundary = (Acc > 64900) or (Acc < 100)
        if not near_boundary and Acc >= 600:
            al = 1
        else:
            al = 0

        self._ops += 1
        self.level_pair_counts[(ml, al)] = self.level_pair_counts.get((ml, al), 0) + 1
        return ml, al

    def update(self, ml: int, al: int, en: bool = True):
        pass  # stateless

    def reset(self):
        self._ops = 0
        self.level_pair_counts = {}

    def info(self):
        return dict(name='ThresholdBased',
                    method=3, state_bits=0,
                    adder_exact=False,
                    description=(
                        'MSB-position operand classification for mult level. '
                        'Boundary check on Acc for adder level (L1 when safe, L0 near boundaries). '
                        'Thresholds: mult: min_msb>=6->L3, >=5->L2, >=4->L1, else L0. '
                        'Adder: L1 if Acc in [600,64900], else L0. '
                        'No arithmetic beyond shifts and comparisons.'))


# ============================================================
# METHOD 4: Error-Budget Controller
# ============================================================

class Method4ErrorBudget:
    """
    Error-budget controller with independently chosen mult and adder levels.

    CRITICAL DESIGN CONSTRAINT: the controller must NOT compute the exact
    product A*B at runtime.  A real hardware controller would need an extra
    exact multiplier to do this, which defeats the purpose of approximation.

    Instead, this controller uses:
      - A pre-computed calibration table of PROVEN multiplier max errors.
      - A proxy product estimate: proxy = (A >> 4) * (B >> 4) * 256
        (upper-nibble product scaled to approximate the actual product).
      - Current accumulator Acc (observable).
      - Conservative sampled adder error bounds (LABELED as sampled, not proven).

    CANDIDATE EVALUATION ORDER:
      Most aggressive -> least aggressive:
      (mult=3, add=1), (mult=3, add=0), (mult=2, add=1), (mult=2, add=0),
      (mult=1, add=1), (mult=1, add=0), (mult=0, add=1), (mult=0, add=0)

    SELECTION RULE per candidate (ml, al):
      estimated_error = MULT_MAX_ABS[ml] + ADDER_MAX_SAMPLED[al]
      estimated_next  = Acc + proxy       [proxy = (A>>4)*(B>>4)*256]
      if estimated_next == 0: skip (zero ref: use exact)
      ratio = estimated_error / estimated_next
      if ratio <= target_pct/100: ACCEPT this candidate

    The adder L2 and L3 candidates are excluded because their sampled max errors
    are 65535, making them never acceptable under any 1% target.
    This is honest: those bounds are not proven but the samples reveal high risk.

    LIMITATIONS (must be stated):
      1. proxy can underestimate the actual product by up to 256x for small operands.
      2. Adder error bounds are sampled (50k), not exhaustive — they could be exceeded.
      3. The ratio check uses estimated_next which may be smaller than the true next acc.
         This means the controller is conservative (may use lower approximation than needed).

    RTL translation:
      proxy = (A[7:4] * B[7:4]) << 8  [shift by 8]
      est_next = Acc + proxy           [16-bit adder]
      For each candidate: compare MULT_MAX + ADD_MAX against est_next * TARGET.
      This is implementable as a LUT + comparator chain.
    """

    CANDIDATES = [(3, 1), (3, 0), (2, 1), (2, 0), (1, 1), (1, 0), (0, 0)]
    MULT_MAX   = {0: 0, 1: 1, 2: 5, 3: 17}  # proven exhaustive bounds
    ADD_SAMP   = {0: 0, 1: 6}                # sampled; L2/L3 excluded as unbounded

    def __init__(self, target_pct: float = 1.0):
        self.target = target_pct / 100.0
        self._ops  = 0
        self.level_pair_counts = {}
        self.exact_fallbacks   = 0

    def decide(self, A: int, B: int, Acc: int):
        proxy       = (A >> 4) * (B >> 4) * 256  # proxy product estimate
        est_next    = Acc + proxy

        if est_next == 0:
            ml, al = 0, 0
            self.exact_fallbacks += 1
        else:
            ml, al = 0, 0  # default: exact
            found  = False
            for cml, cal in self.CANDIDATES:
                if cml not in self.MULT_MAX or cal not in self.ADD_SAMP:
                    continue  # skip L2/L3 adder (unbounded)
                e_bound = self.MULT_MAX[cml] + self.ADD_SAMP[cal]
                if e_bound / est_next <= self.target:
                    ml, al = cml, cal
                    found  = True
                    break
            if not found:
                self.exact_fallbacks += 1

        self._ops += 1
        self.level_pair_counts[(ml, al)] = self.level_pair_counts.get((ml, al), 0) + 1
        return ml, al

    def update(self, ml: int, al: int, en: bool = True):
        pass  # stateless

    def reset(self):
        self._ops = 0
        self.level_pair_counts = {}
        self.exact_fallbacks   = 0

    def info(self):
        return dict(name='ErrorBudget',
                    method=4, state_bits=0,
                    adder_exact=False,
                    description=(
                        'Budget controller. Proxy product = upper-nibble estimate (no exact A*B). '
                        'Candidates: (3,1),(3,0),(2,1),(2,0),(1,1),(1,0),(0,0). '
                        'Adder L2/L3 excluded (sampled max=65535). '
                        'Accept most aggressive candidate where MULT_MAX+ADD_MAX <= 1% of est_next. '
                        'est_next = Acc + proxy (proxy may underestimate small products). '
                        'Mult bounds proven; adder L1 bound sampled (6 from 50k), not exhaustive.'))


# ============================================================
# METHOD 5: Adaptive Multiplier, Exact Adder
# ============================================================

class Method5AdaptMultExactAdd:
    """
    Adaptive multiplier level, accumulator adder always L0 (exact).

    Two sub-variants implemented:
      variant='magnitude' : upper-nibble proxy thresholds (same as Method2's mult logic)
      variant='msb'       : MSB-position thresholds (same as Method3's mult logic)

    The adder is hardwired to L0.  This deliberately isolates multiplier error
    and eliminates carry-suppression risk from adder approximation.

    This is the required comparison to determine whether keeping the adder
    exact is a better practical choice than independently approximating both.

    RTL translation: mult_level selected by chosen sub-variant; add_level = 2'b00.
    """
    def __init__(self, variant: str = 'magnitude'):
        assert variant in ('magnitude', 'msb')
        self.variant = variant
        self._ops    = 0
        self.level_pair_counts = {}

    @staticmethod
    def _msb(x):
        if x == 0: return 0
        m = 0
        while x >> (m + 1): m += 1
        return m

    def decide(self, A: int, B: int, Acc: int):
        if self.variant == 'magnitude':
            proxy = (A >> 4) * (B >> 4)
            if proxy >= 7:   ml = 3
            elif proxy >= 2: ml = 2
            elif proxy >= 1: ml = 1
            else:            ml = 0
        else:  # msb
            min_msb = min(self._msb(A), self._msb(B))
            if min_msb >= 6:   ml = 3
            elif min_msb >= 5: ml = 2
            elif min_msb >= 4: ml = 1
            else:              ml = 0

        al = 0  # exact adder always
        self._ops += 1
        self.level_pair_counts[(ml, al)] = self.level_pair_counts.get((ml, al), 0) + 1
        return ml, al

    def update(self, ml: int, al: int, en: bool = True):
        pass  # stateless

    def reset(self):
        self._ops = 0
        self.level_pair_counts = {}

    def info(self):
        return dict(name=f'AdaptMult_ExactAdd_{self.variant}',
                    method=5, state_bits=0,
                    adder_exact=True,
                    description=(
                        f'Adaptive multiplier ({self.variant} variant), adder hardwired L0. '
                        'Eliminates adder carry-suppression risk entirely.'))


# ============================================================
# FIXED INDEPENDENT BASELINES (all 16 pairs and 4 mult-only)
# ============================================================

class FixedIndependent:
    """Fixed mult_level and add_level, independently specified."""
    def __init__(self, ml: int, al: int):
        self.ml = ml; self.al = al
        self._ops = 0

    def decide(self, A: int, B: int, Acc: int):
        self._ops += 1
        return self.ml, self.al

    def update(self, ml, al, en=True): pass
    def reset(self): self._ops = 0

    def info(self):
        return dict(name=f'Fixed_M{self.ml}_A{self.al}',
                    method='baseline_fixed', state_bits=0,
                    adder_exact=(self.al == 0),
                    description=f'Fixed: mult=L{self.ml}, adder=L{self.al}')


# ============================================================
# FACTORY: build all controllers for the experiment
# ============================================================

def build_all_controllers():
    """Return ordered list of (arch_id, controller) for the full experiment."""
    controllers = []

    # Exact MAC
    controllers.append(('Exact', FixedIndependent(0, 0)))

    # Method 1: four universal fixed levels
    for lv in range(4):
        controllers.append((f'M1_L{lv}{lv}', Method1Fixed(lv)))

    # All 16 fixed independent pairs
    for ml in range(4):
        for al in range(4):
            if not (ml == al):  # avoid duplicating the 4 shared-level ones
                controllers.append((f'Fix_M{ml}A{al}', FixedIndependent(ml, al)))
    # Add the 4 diagonal ones too (under different key to keep fixed baselines separate)
    for lv in range(4):
        controllers.append((f'Fix_M{lv}A{lv}', FixedIndependent(lv, lv)))

    # Method 2: dual adaptive
    controllers.append(('M2_DualAdaptive', Method2DualAdaptive()))

    # Method 3: threshold-based
    controllers.append(('M3_Threshold', Method3Threshold()))

    # Method 4: error budget
    controllers.append(('M4_ErrorBudget', Method4ErrorBudget(target_pct=1.0)))

    # Method 5: adaptive mult, exact adder (two variants)
    controllers.append(('M5_AdaptMult_Mag', Method5AdaptMultExactAdd('magnitude')))
    controllers.append(('M5_AdaptMult_MSB', Method5AdaptMultExactAdd('msb')))

    return controllers
