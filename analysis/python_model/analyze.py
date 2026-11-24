"""
analyze.py
==========
Compute trade-off tables and identify non-dominated candidates.
Outputs:
  v2/results/summary_table.csv
  v2/results/nondominated.csv
"""
import sys, os, csv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')

def load_csv(fname):
    with open(os.path.join(OUTDIR, fname)) as f:
        return list(csv.DictReader(f))

wl_rows = load_csv('workload_results.csv')
lv_rows = load_csv('level_distributions.csv')

# ---- Build per-arch summary ----
from collections import defaultdict
arch_wl = defaultdict(list)
for r in wl_rows:
    arch_wl[r['arch_id']].append(r)

summary = []
for arch_id, rows in arch_wl.items():
    cds   = [int(r['code_diff']) for r in rows]
    circs = [int(r['circ_dist']) for r in rows]

    # exclude zero-reference rows from relative metrics
    nonzero_rows = [r for r in rows if r['zero_ref'] == 'False']
    zero_rows    = [r for r in rows if r['zero_ref'] == 'True']

    meets_1pct_nz = sum(1 for r in nonzero_rows if r['meets_1pct'] == 'True')
    total_nz      = len(nonzero_rows)

    # MAE on code_diff (all workloads)
    mae_all = sum(cds) / len(cds)
    max_all = max(cds)

    # MAE on circ_dist (all workloads)
    mae_circ = sum(circs) / len(circs)

    # Approximation proxy: fraction of steps NOT using exact (ml>0 or al>0)
    lv = next((x for x in lv_rows if x['arch_id'] == arch_id), None)
    ml_l0 = float(lv['ml_L0_pct']) if lv else 100.0
    al_l0 = float(lv['al_L0_pct']) if lv else 100.0
    pct_both_exact = float(lv['pct_both_exact']) if lv else 100.0
    # approx_effort: fraction where either mult or adder is approximate
    # (complementary to pct_both_exact, roughly)
    ml_l3  = float(lv['ml_L3_pct']) if lv else 0.0
    method = rows[0]['method']

    summary.append(dict(
        arch_id=arch_id, method=method,
        mae_code_diff=round(mae_all, 2),
        max_code_diff=max_all,
        mae_circ_dist=round(mae_circ, 2),
        meets_1pct_nz=meets_1pct_nz,
        total_nz=total_nz,
        meets_1pct_rate_pct=round(100*meets_1pct_nz/total_nz, 1) if total_nz else 0,
        pct_both_exact=pct_both_exact,
        ml_L0_pct=round(ml_l0, 1),
        ml_L3_pct=round(ml_l3, 1),
        al_L0_pct=round(al_l0, 1),
        adder_exact=(rows[0]['adder_exact'] == 'True'),
    ))

# Sort by MAE ascending
summary.sort(key=lambda r: r['mae_code_diff'])

with open(os.path.join(OUTDIR, 'summary_table.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
    w.writeheader(); w.writerows(summary)
print(f"Saved summary_table.csv")

# ---- Non-dominated analysis ----
# Two objectives to minimize: mae_code_diff (accuracy), pct_both_exact (lower = more approx effort)
# Better = lower MAE AND lower pct_both_exact (= more approximation used for given accuracy)
# A candidate A dominates B if A.mae <= B.mae AND A.pct_both_exact <= B.pct_both_exact (strictly one)

def dominated(a, b, rows):
    ra = next(r for r in rows if r['arch_id'] == a)
    rb = next(r for r in rows if r['arch_id'] == b)
    # a dominates b if at least as good on both, strictly better on one
    mae_ok  = ra['mae_code_diff'] <= rb['mae_code_diff']
    apx_ok  = ra['pct_both_exact'] <= rb['pct_both_exact']
    strict  = (ra['mae_code_diff'] < rb['mae_code_diff']) or (ra['pct_both_exact'] < rb['pct_both_exact'])
    return mae_ok and apx_ok and strict

nd_ids = []
for r in summary:
    aid = r['arch_id']
    is_dominated = any(dominated(other['arch_id'], aid, summary)
                       for other in summary if other['arch_id'] != aid)
    if not is_dominated:
        nd_ids.append(aid)

nd_rows = [r for r in summary if r['arch_id'] in nd_ids]
with open(os.path.join(OUTDIR, 'nondominated.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(nd_rows[0].keys()))
    w.writeheader(); w.writerows(nd_rows)
print(f"Saved nondominated.csv ({len(nd_rows)} candidates)")

# Print summary table to console
print("\n{:30s} {:>10s} {:>10s} {:>12s} {:>10s} {:>10s} {:>10s}".format(
    "arch_id", "MAE_code", "max_code", "1pct_rate%", "ml_L3%", "al_L0%", "both_ex%"))
for r in summary:
    marker = " <-- ND" if r['arch_id'] in nd_ids else ""
    print("{:30s} {:>10.1f} {:>10d} {:>12.1f} {:>10.1f} {:>10.1f} {:>10.1f}{}".format(
        r['arch_id'], r['mae_code_diff'], r['max_code_diff'],
        r['meets_1pct_rate_pct'], r['ml_L3_pct'], r['al_L0_pct'],
        r['pct_both_exact'], marker))

print("\nNon-dominated (lower MAE AND more approximation used):")
for r in nd_rows:
    print(f"  {r['arch_id']:30s}  MAE={r['mae_code_diff']:7.1f}  pct_both_exact={r['pct_both_exact']:.1f}%  ml_L3={r['ml_L3_pct']:.1f}%  al_L0={r['al_L0_pct']:.1f}%")
