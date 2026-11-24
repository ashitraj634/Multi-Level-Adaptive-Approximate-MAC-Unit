import sys, os, csv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rtl_model import approx_multiply, approx_add, exact_mac_step
from controllers_v2 import build_all_controllers
from workloads import build_workloads

workloads = build_workloads()
controllers = build_all_controllers()

print(f"Total architectures: {len(controllers)}")
print(f"Total workloads:     {len(workloads)}")

results = []
for c_id, c in controllers:
    info = c.info()
    method = info.get('method', 'fixed')
    
    total_steps = 0
    exact_matches = 0
    total_abs_err = 0
    max_err = 0
    ml_counts = [0]*4
    al_counts = [0]*4
    
    for wl in workloads:
        c.reset()
        ops = wl['operands']
        en_m = wl.get('enable_mask') or ([True]*len(ops))
        rst_m = wl.get('reset_mask') or ([False]*len(ops))
        init = wl.get('initial_acc', 0)
        
        acc = init & 0xFFFF
        exact_acc = init & 0xFFFF
        
        for idx in range(len(ops)):
            A, B = ops[idx]
            if rst_m[idx]:
                acc = 0
                exact_acc = 0
                c.reset()
            
            ml, al = c.decide(A, B, acc)
            ml_counts[ml] += 1
            al_counts[al] += 1
            total_steps += 1
            
            if en_m[idx]:
                p_approx = approx_multiply(A, B, ml)
                acc = approx_add(p_approx, acc, al)
                
                p_exact = A * B
                exact_acc = (exact_acc + p_exact) & 0xFFFF
            
            c.update(ml, al, en_m[idx])
            
        err = abs(acc - exact_acc)
        total_abs_err += err
        if err > max_err:
            max_err = err
        if acc == exact_acc:
            exact_matches += 1
            
    avg_err = total_abs_err / len(workloads)
    exact_match_pct = (exact_matches / len(workloads)) * 100.0
    
    results.append({
        'id': c_id,
        'method': str(method),
        'avg_err': avg_err,
        'max_err': max_err,
        'exact_match_pct': exact_match_pct,
        'ml_dist': [round(x/total_steps*100, 1) for x in ml_counts],
        'al_dist': [round(x/total_steps*100, 1) for x in al_counts]
    })

print("=" * 130)
print(f"{'Arch ID':<18} | {'Method':<16} | {'Avg Error':<10} | {'Max Error':<10} | {'ExactMatch%':<12} | {'Mult [L0,L1,L2,L3] %':<24} | {'Adder [L0,L1,L2,L3] %'}")
print("=" * 130)
for r in results:
    ml_s = str(r['ml_dist'])
    al_s = str(r['al_dist'])
    print(f"{r['id']:<18} | {r['method']:<16} | {r['avg_err']:10.2f} | {r['max_err']:10d} | {r['exact_match_pct']:11.1f}% | {ml_s:<24} | {al_s}")
print("=" * 130)
