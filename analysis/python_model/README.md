# Python Controller Analysis

This directory contains a complete Python-based study of five adaptive controller strategies for the approximate MAC across 25 benchmark workloads (`707` MAC steps total per architecture).

---

## Important Note on RTL Correspondence

This Python study (`rtl_model.py`) was written against an **earlier workspace RTL revision** rather than the final archive RTL in `rtl/`:
- **Multiplier L3:** `rtl_model.py` models pure truncation of columns `0–2` (where the column-2 compressor block evaluates to zero). The final archive's `rtl/arithmetic/approx_multiplier_comp.sv` applies the MLAPC 6:3 approximate compressor to **column 5**.
- **Adder L1–L3:** `rtl_model.py` freezes carry at `0` across the XOR boundary, whereas `rtl/arithmetic/approx_adder_16bit.sv` uses AND-predicted carry (`A[L-1] & B[L-1]`) at the boundary.

Because the winning **Method 5 MSB** controller locks the adder at `L0` (exact), this discrepancy does not change the controller selection conclusion. No HDL simulator was run in the Python study environment.

---

## Running the Study

**Requirements:** Python 3.8+, standard library only.

```bash
cd analysis/python_model
python characterize.py    # Exhaustive mult (65,536 pairs/level) + sampled adder stats
python run_experiment.py  # 26 architectures x 25 workloads -> ../results/workload_results.csv
python analyze.py         # Summary metrics & Pareto frontier -> ../results/summary_table.csv
python cross_verify.py    # Independent cross-check across identical workloads
```

---

## The 5 Controller Methods Evaluated

| Method | Strategy | Adder Level |
|:---|:---|:---:|
| **M1 Fixed** | Hardwired: same level for both mult and adder (`L0–L3`) | Same as mult |
| **M2 Dual Adaptive** | Upper-nibble proxy for mult; accumulator-range proxy for adder | L0 or L1 |
| **M3 Threshold** | MSB-based mult selection + boundary-aware adder | L0 or L1 |
| **M4 Error Budget** | Running proxy error budget; backs off when budget exceeded | L0 or L1 |
| **M5 Adapt Mult, Exact Add** | MSB-based (or magnitude-based) mult selection; adder exact | **Always L0** |
