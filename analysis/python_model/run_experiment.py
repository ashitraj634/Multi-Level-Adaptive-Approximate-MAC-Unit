"""
run_experiment.py
=================
Main experiment runner.  Runs all controllers against all workloads.
Outputs:
  v2/results/workload_results.csv    -- one row per (arch, workload)
  v2/results/level_distributions.csv -- approximation-level usage per arch
  v2/results/experiment_log.txt      -- validation log
"""
import sys, os, csv, math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rtl_model      import approx_multiply, approx_add, exact_mac_step
from controllers_v2 import build_all_controllers
from workloads      import build_workloads

OUTDIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results'))
os.makedirs(OUTDIR, exist_ok=True)

LOG_LINES = []
def log(msg):
    print(msg)
    LOG_LINES.append(msg)

# ============================================================
# Helpers
# ============================================================

def run_arch(controller, workload):
    """
    Run one controller over one workload.  Returns result dict.
    controller.reset() is called FIRST.
    """
    controller.reset()
    ops   = workload['operands']
    n     = len(ops)
    en_m  = workload.get('enable_mask')  or ([True] * n)
    rst_m = workload.get('reset_mask')   or ([False] * n)
    init  = workload.get('initial_acc', 0)

    acc   = init & 0xFFFF
    ml_list, al_list = [], []
    approx_acc_trace = []
    step_errors = []

    for idx in range(n):
        A, B = ops[idx]
        if rst_m[idx]:
            acc = 0
            controller.reset()

        ml, al = controller.decide(A, B, acc)
        # Validate level selections
        assert 0 <= ml <= 3, f"Invalid mult_level {ml}"
        assert 0 <= al <= 3, f"Invalid add_level {al}"

        if en_m[idx]:
            product  = approx_multiply(A, B, ml)
            acc      = approx_add(product, acc, al)
        # disabled: acc unchanged, product computed but not accumulated

        controller.update(ml, al, en_m[idx])
        ml_list.append(ml)
        al_list.append(al)
        approx_acc_trace.append(acc)

    return dict(final_approx=acc, ml_list=ml_list, al_list=al_list,
                approx_trace=approx_acc_trace, n_ops=n, n_enabled=sum(en_m))


def run_exact(workload):
    """Exact MAC reference for a workload."""
    ops   = workload['operands']
    n     = len(ops)
    en_m  = workload.get('enable_mask')  or ([True] * n)
    rst_m = workload.get('reset_mask')   or ([False] * n)
    init  = workload.get('initial_acc', 0)

    acc       = init & 0xFFFF
    unbounded = init
    exact_trace = []
    unb_trace   = []
    for idx in range(n):
        A, B = ops[idx]
        if rst_m[idx]:
            acc = 0; unbounded = 0
        if en_m[idx]:
            prod       = A * B
            acc        = (acc + prod) & 0xFFFF
            unbounded += prod
        exact_trace.append(acc)
        unb_trace.append(unbounded)
    return dict(final_exact=acc, exact_trace=exact_trace,
                unbounded_trace=unb_trace)


def code_diff(a, b):
    return abs(int(a) - int(b))

def circ_dist(a, b):
    d = abs(int(a) - int(b))
    return min(d, 65536 - d)

def rel_err_pct(approx, exact):
    if exact == 0:
        return None  # undefined
    return 100.0 * abs(approx - exact) / abs(exact)


def level_freqs(lst, n):
    counts = [lst.count(k) for k in range(4)]
    return [c/n if n > 0 else 0.0 for c in counts]


# ============================================================
# Main Experiment
# ============================================================

def main():
    controllers = build_all_controllers()
    workloads   = build_workloads()

    log(f"Architectures: {len(controllers)}")
    log(f"Workloads:     {len(workloads)}")
    log(f"Total rows:    {len(controllers) * len(workloads)}")
    log("")

    # Validation checks
    arch_ids = [a for a, _ in controllers]
    if len(arch_ids) != len(set(arch_ids)):
        log("WARNING: duplicate arch_ids detected")

    wl_ids = [w['id'] for w in workloads]
    assert len(wl_ids) == len(set(wl_ids)), "Duplicate workload IDs"
    assert len(workloads) >= 15, f"Need >= 15 workloads, got {len(workloads)}"
    log(f"Validation: {len(workloads)} workloads (>= 15 required) — OK")
    log(f"Validation: all workload IDs unique — OK")

    # Pre-compute exact results for all workloads
    exact_results = {w['id']: run_exact(w) for w in workloads}

    wl_rows  = []  # workload_results.csv
    lv_rows  = []  # level_distributions.csv

    for arch_id, ctrl in controllers:
        ctrl_info = ctrl.info()
        wl_errs   = []  # for summary stats

        for wl in workloads:
            wid  = wl['id']
            er   = exact_results[wid]
            n_ops = len(wl['operands'])

            try:
                res = run_arch(ctrl, wl)
            except Exception as e:
                log(f"FAIL {arch_id} {wid}: {e}")
                continue

            final_approx = res['final_approx']
            final_exact  = er['final_exact']

            cd   = code_diff(final_approx, final_exact)
            circ = circ_dist(final_approx, final_exact)
            rp   = rel_err_pct(final_approx, final_exact)
            zero_ref = (final_exact == 0)
            meets_1pct = (cd == 0) if zero_ref else (rp is not None and rp <= 1.0)

            # Per-step errors for RMSE and mean
            step_cds  = [code_diff(a, e) for a, e in
                         zip(res['approx_trace'], er['exact_trace'])]

            n_en = res['n_enabled']
            ml_f = level_freqs(res['ml_list'], n_ops)
            al_f = level_freqs(res['al_list'], n_ops)

            n_lv_changes = sum(1 for i in range(1, len(res['ml_list']))
                                if res['ml_list'][i] != res['ml_list'][i-1] or
                                   res['al_list'][i] != res['al_list'][i-1])

            pair_counts = {}
            for ml, al in zip(res['ml_list'], res['al_list']):
                pair_counts[(ml, al)] = pair_counts.get((ml, al), 0) + 1

            row = dict(
                arch_id=arch_id, method=ctrl_info['method'],
                adder_exact=ctrl_info['adder_exact'],
                wl_id=wid, wl_desc=wl['description'],
                n_steps=n_ops, n_enabled=n_en,
                final_exact=final_exact, final_approx=final_approx,
                code_diff=cd, circ_dist=circ,
                rel_err_pct=round(rp, 6) if rp is not None else 'undefined',
                zero_ref=zero_ref,
                meets_1pct=meets_1pct,
                step_mean_cd=round(sum(step_cds)/len(step_cds), 4) if step_cds else 0,
                step_max_cd=max(step_cds) if step_cds else 0,
                step_rmse=round(math.sqrt(sum(e*e for e in step_cds)/len(step_cds)), 4) if step_cds else 0,
                n_level_changes=n_lv_changes,
                ml_L0_freq=round(ml_f[0], 4), ml_L1_freq=round(ml_f[1], 4),
                ml_L2_freq=round(ml_f[2], 4), ml_L3_freq=round(ml_f[3], 4),
                al_L0_freq=round(al_f[0], 4), al_L1_freq=round(al_f[1], 4),
                al_L2_freq=round(al_f[2], 4), al_L3_freq=round(al_f[3], 4),
            )
            wl_rows.append(row)
            wl_errs.append(cd)

        # Per-arch level distribution summary
        # Aggregate across all workloads
        all_ml = []
        all_al = []
        all_pairs = {}
        for wl in workloads:
            try:
                res = run_arch(ctrl, wl)
            except:
                continue
            all_ml.extend(res['ml_list'])
            all_al.extend(res['al_list'])
            for ml, al in zip(res['ml_list'], res['al_list']):
                all_pairs[(ml,al)] = all_pairs.get((ml,al), 0) + 1

        tot = len(all_ml) or 1
        ml_f = level_freqs(all_ml, tot)
        al_f = level_freqs(all_al, tot)
        pct_both_exact = 100.0 * all_pairs.get((0,0), 0) / tot

        lv_row = dict(
            arch_id=arch_id, method=ctrl_info['method'],
            name=ctrl_info['name'], adder_exact=ctrl_info['adder_exact'],
            n_total_decisions=tot,
            ml_L0_pct=round(100*ml_f[0],2), ml_L1_pct=round(100*ml_f[1],2),
            ml_L2_pct=round(100*ml_f[2],2), ml_L3_pct=round(100*ml_f[3],2),
            al_L0_pct=round(100*al_f[0],2), al_L1_pct=round(100*al_f[1],2),
            al_L2_pct=round(100*al_f[2],2), al_L3_pct=round(100*al_f[3],2),
            pct_both_exact=round(pct_both_exact, 2),
            state_bits=ctrl_info.get('state_bits', 'N/A'),
        )
        lv_rows.append(lv_row)

        # Quick summary for log
        log(f"{arch_id:30s} MAE={sum(wl_errs)/len(wl_errs):.1f} "
            f"max={max(wl_errs)} "
            f"mlL3={100*ml_f[3]:.0f}%  alL0={100*al_f[0]:.0f}%")

    # Write CSVs
    with open(os.path.join(OUTDIR, 'workload_results.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(wl_rows[0].keys()))
        w.writeheader(); w.writerows(wl_rows)
    log(f"\nSaved workload_results.csv ({len(wl_rows)} rows)")

    with open(os.path.join(OUTDIR, 'level_distributions.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(lv_rows[0].keys()))
        w.writeheader(); w.writerows(lv_rows)
    log(f"Saved level_distributions.csv ({len(lv_rows)} rows)")

    # Validation cross-checks
    log("\n--- Validation ---")
    # 1. Exact arch must have 0 error everywhere
    exact_rows = [r for r in wl_rows if r['arch_id'] == 'Exact']
    nonzero_exact = [r for r in exact_rows if r['code_diff'] != 0]
    log(f"Exact arch zero-error check: {len(nonzero_exact)} failures "
        f"(must be 0) {'PASS' if not nonzero_exact else 'FAIL'}")

    # 2. Fixed L0L0 and Exact must match
    l00_rows = [r for r in wl_rows if r['arch_id'] == 'M1_L00']
    mismatch = [r for r in l00_rows if r['code_diff'] != 0]
    log(f"M1_L00 vs Exact zero-error: {len(mismatch)} failures "
        f"(must be 0) {'PASS' if not mismatch else 'FAIL'}")

    # 3. Level distributions sum to 100%
    for row in lv_rows[:3]:
        ml_sum = row['ml_L0_pct'] + row['ml_L1_pct'] + row['ml_L2_pct'] + row['ml_L3_pct']
        al_sum = row['al_L0_pct'] + row['al_L1_pct'] + row['al_L2_pct'] + row['al_L3_pct']
        ok = abs(ml_sum - 100) < 0.1 and abs(al_sum - 100) < 0.1
        log(f"  {row['arch_id']}: ml_sum={ml_sum:.1f}% al_sum={al_sum:.1f}% {'OK' if ok else 'WARN'}")

    # 4. Adaptive methods M2/M3/M4 must sometimes use al > 0
    for aid in ['M2_DualAdaptive', 'M3_Threshold', 'M4_ErrorBudget']:
        lr = [r for r in lv_rows if r['arch_id'] == aid]
        if lr:
            nonzero_al = lr[0]['al_L0_pct'] < 100
            log(f"  {aid}: ever uses non-zero adder level? {'YES' if nonzero_al else 'NO (all-exact-adder)'}")

    # Write log
    with open(os.path.join(OUTDIR, 'experiment_log.txt'), 'w') as f:
        f.write('\n'.join(LOG_LINES))
    log("Saved experiment_log.txt")


if __name__ == '__main__':
    main()
