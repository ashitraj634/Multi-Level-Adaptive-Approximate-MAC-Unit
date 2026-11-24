"""
characterize.py
===============
Exhaustive characterization of the RTL-accurate approximate arithmetic.

Multiplier: all 65,536 pairs × 4 levels = 262,144 evaluations (exhaustive).
Adder:      standalone L0 exhaustive (2^32 pairs -- infeasible) → 200k random + targeted.
            MAC-reachable adder: 50k random (A,B,Acc) per config.

Outputs:
  v2/results/mult_characterization.csv
  v2/results/adder_characterization.csv
  v2/results/mac_step_characterization.csv
"""
import sys, os, csv, random, math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rtl_model import approx_multiply, approx_add, exact_mac_step, approx_mac_step

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
os.makedirs(OUTDIR, exist_ok=True)

def pct(n, d):
    return 100.0 * n / d if d else 0.0

def percentile(sorted_list, p):
    idx = int(p * len(sorted_list))
    return sorted_list[min(idx, len(sorted_list)-1)]

# ============================================================
# MULTIPLIER: exhaustive 65536 × 4 levels
# ============================================================
print("=== Multiplier: exhaustive 65536 pairs × 4 levels ===")
mult_rows = []
for level in range(4):
    exact_matches = 0
    abs_errors = []
    signed_errors = []
    worst = (0, 0, 0)  # (abs_err, A, B)
    for A in range(256):
        for B in range(256):
            exact   = A * B
            approx  = approx_multiply(A, B, level)
            se      = approx - exact
            ae      = abs(se)
            signed_errors.append(se)
            abs_errors.append(ae)
            if exact == approx:
                exact_matches += 1
            if ae > worst[0]:
                worst = (ae, A, B)
    n = len(abs_errors)
    sorted_ae = sorted(abs_errors)
    mae  = sum(abs_errors) / n
    mse  = sum(e*e for e in signed_errors) / n
    rmse = math.sqrt(mse)
    msigned = sum(signed_errors) / n
    nz_within_1pct = sum(1 for A2 in range(256) for B2 in range(256)
                         if A2*B2 > 0 and abs(approx_multiply(A2,B2,level) - A2*B2) / (A2*B2) <= 0.01)
    nz_total = sum(1 for A2 in range(256) for B2 in range(256) if A2*B2 > 0)
    row = dict(
        level=level, n_pairs=n, test_domain='exhaustive_65536',
        exact_matches=exact_matches,
        exact_match_pct=pct(exact_matches, n),
        mean_signed=round(msigned, 6),
        mae=round(mae, 6),
        rmse=round(rmse, 6),
        max_abs=worst[0], worst_A=worst[1], worst_B=worst[2],
        p50=percentile(sorted_ae, 0.50),
        p90=percentile(sorted_ae, 0.90),
        p95=percentile(sorted_ae, 0.95),
        p99=percentile(sorted_ae, 0.99),
        nz_within_1pct=nz_within_1pct,
        nz_total=nz_total,
        nz_1pct_rate=pct(nz_within_1pct, nz_total),
    )
    mult_rows.append(row)
    print(f"  L{level}: exact={pct(exact_matches,n):.1f}%  mean_signed={msigned:+.4f}"
          f"  MAE={mae:.4f}  max_abs={worst[0]} (A={worst[1]},B={worst[2]})")

with open(os.path.join(OUTDIR, 'mult_characterization.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(mult_rows[0].keys()))
    w.writeheader(); w.writerows(mult_rows)
print(f"  Saved mult_characterization.csv")

# ============================================================
# ADDER: L0 targeted + 200k random per level
# ============================================================
print("\n=== Adder: 200k random pairs × 4 levels ===")
rng = random.Random(42)

adder_rows = []
for level in range(4):
    # Targeted boundary pairs
    targeted_pairs = []
    for v in [0, 1, 2, 3, 0x00FF, 0x01FF, 0x7FFF, 0x8000, 0xFFFE, 0xFFFF]:
        for u in [0, 1, 0x7FFF, 0x8000, 0xFFFF]:
            targeted_pairs.append((v, u))
    # Random pairs
    rand_pairs = [(rng.randint(0, 65535), rng.randint(0, 65535)) for _ in range(200_000)]
    all_pairs = targeted_pairs + rand_pairs
    n = len(all_pairs)

    exact_matches = 0
    abs_errors    = []
    signed_errors = []
    circ_errors   = []
    for A, B in all_pairs:
        exact  = (A + B) & 0xFFFF
        approx = approx_add(A, B, level)
        se  = approx - exact
        ae  = abs(se)
        ce  = min(ae, 65536 - ae)
        signed_errors.append(se)
        abs_errors.append(ae)
        circ_errors.append(ce)
        if exact == approx:
            exact_matches += 1
    sorted_ae = sorted(abs_errors)
    sorted_ce = sorted(circ_errors)
    mae  = sum(abs_errors) / n
    rmse = math.sqrt(sum(e*e for e in signed_errors) / n)
    row = dict(
        level=level, n_pairs=n, test_domain=f'targeted+200k_random_seed42',
        exact_matches=exact_matches,
        exact_match_pct=pct(exact_matches, n),
        mean_signed=round(sum(signed_errors)/n, 6),
        mae=round(mae, 6),
        rmse=round(rmse, 6),
        max_abs_code_diff=sorted_ae[-1],
        max_circ_dist=sorted_ce[-1],
        p50_code=percentile(sorted_ae, 0.50),
        p90_code=percentile(sorted_ae, 0.90),
        p99_code=percentile(sorted_ae, 0.99),
        p50_circ=percentile(sorted_ce, 0.50),
        p99_circ=percentile(sorted_ce, 0.99),
    )
    adder_rows.append(row)
    print(f"  L{level}: exact={pct(exact_matches,n):.1f}%  MAE={mae:.2f}"
          f"  max_code_diff={sorted_ae[-1]}  max_circ={sorted_ce[-1]}")

with open(os.path.join(OUTDIR, 'adder_characterization.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(adder_rows[0].keys()))
    w.writeheader(); w.writerows(adder_rows)
print(f"  Saved adder_characterization.csv")

# ============================================================
# MAC-step: 50k random (A, B, Acc) per (mult_level, add_level)
# ============================================================
print("\n=== MAC step: 50k random × 16 configs ===")
rng2 = random.Random(123)
mac_rows = []
for ml in range(4):
    for al in range(4):
        exact_matches = 0
        abs_errors    = []
        circ_errors   = []
        signed_errors = []
        for _ in range(50_000):
            A   = rng2.randint(0, 255)
            B   = rng2.randint(0, 255)
            Acc = rng2.randint(0, 65535)
            exact  = (Acc + A*B) & 0xFFFF
            approx = approx_mac_step(Acc, A, B, ml, al)
            se = approx - exact
            ae = abs(se)
            ce = min(ae, 65536 - ae)
            signed_errors.append(se)
            abs_errors.append(ae)
            circ_errors.append(ce)
            if exact == approx:
                exact_matches += 1
        n = 50_000
        sorted_ae = sorted(abs_errors)
        row = dict(
            mult_level=ml, add_level=al, n_samples=n,
            exact_matches=exact_matches,
            exact_match_pct=pct(exact_matches, n),
            mean_signed=round(sum(signed_errors)/n, 6),
            mae=round(sum(abs_errors)/n, 6),
            rmse=round(math.sqrt(sum(e*e for e in signed_errors)/n), 4),
            max_abs=sorted_ae[-1],
            max_circ=sorted(circ_errors)[-1],
            p99_abs=percentile(sorted_ae, 0.99),
        )
        mac_rows.append(row)
        print(f"  M{ml}/A{al}: exact={pct(exact_matches,n):.1f}%"
              f"  MAE={row['mae']:.3f}  max_abs={row['max_abs']}")

with open(os.path.join(OUTDIR, 'mac_step_characterization.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(mac_rows[0].keys()))
    w.writeheader(); w.writerows(mac_rows)
print(f"  Saved mac_step_characterization.csv")
print("\nCharacterization complete.")
