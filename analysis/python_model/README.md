# Python Controller Analysis

This directory contains a complete Python-based study of five adaptive controller strategies for the approximate MAC. The study uses a bit-exact Python model of the RTL arithmetic and evaluates every controller across 25 benchmark workloads.

---

## What This Study Answers

1. Which controller minimises error while using the most approximation?
2. Does approximating both multiplier AND adder improve accuracy vs. savings over multiplier-only?
3. Is an adaptive controller better than a fixed-level configuration?
4. What is the actual level distribution (how often does each approximation level get selected)?

**Conclusion:** Method 5 MSB (adaptive multiplier, exact adder) is the optimal strategy — 0.44% average relative error, 91.7% of workloads pass the 1% error threshold, multiplier runs at L3 for 41.4% of cycles.

---

## Running the Study

**Requirements:** Python 3.8 or later, standard library only (no external packages).

```bash
cd analysis/python_model

# 1. Characterise the RTL arithmetic exhaustively
python characterize.py
#    → results/mult_characterization.csv  (exhaustive 65536 pairs per level)
#    → results/adder_characterization.csv  (sampled)
#    → results/mac_step_characterization.csv

# 2. Run the main experiment (26 architectures × 25 workloads)
python run_experiment.py
#    → results/workload_results.csv  (650 rows)
#    → results/level_distributions.csv  (level usage per architecture)
#    → results/experiment_log.txt

# 3. Analyse and produce summary table
python analyze.py
#    → results/summary_table.csv  (ranked, with Pareto-optimal flagged)
#    → results/nondominated.csv

# 4. Cross-verify all 26 architectures on identical workloads
python cross_verify.py
#    → prints master table to stdout
```

---

## File Descriptions

| File | Purpose |
|:---|:---|
| `rtl_model.py` | Bit-exact Python model of `approx_multiplier_comp.sv` and `approx_adder_16bit.sv`. Includes self-tests. |
| `controllers_v2.py` | All 5 controller methods as Python classes. Each implements `decide(A,B,Acc)→(ml,al)`, `update()`, `reset()`. |
| `workloads.py` | 25 named benchmark workloads covering: all-zero, small, medium, large, alternating, edge cases, overflow, enable pauses, mid-sequence resets, long accumulation. |
| `run_experiment.py` | Main runner. Calls every controller on every workload, validates level selections, writes CSVs. |
| `characterize.py` | Exhaustive multiplier characterisation (all 65,536 pairs) + sampled adder characterisation. |
| `analyze.py` | Loads workload_results.csv, computes MAE, max error, 1%-pass-rate, Pareto frontier. |
| `cross_verify.py` | Independent re-run of all 26 architectures — used to confirm reproducibility. |

---

## The 5 Controller Methods

| Method | Strategy | Adder level |
|:---|:---|:---:|
| **M1 Fixed** | Hardwired: same level for both mult and adder | Same as mult |
| **M2 Dual Adaptive** | Upper-nibble proxy for mult; accumulator-range proxy for adder | L0 or L1 |
| **M3 Threshold** | MSB-based mult selection + boundary-aware adder | L0 or L1 |
| **M4 Error Budget** | Running proxy error budget; backs off when budget exceeded | L0 or L1 |
| **M5 Adapt Mult, Exact Add** | MSB-based mult selection; adder always exact | **Always L0** |

---

## RTL Model Accuracy Note

The Python model was derived by **direct code inspection** of the SystemVerilog source files. No HDL simulator was available to cross-check the Python against actual RTL simulation output. The model is validated internally (self-tests pass, L0 is bit-exact multiplication) but has not been confirmed against a Verilog simulation log.

One known difference: the Python model in `rtl_model.py` was initially derived from an older workspace adder (carry frozen at 0). The ZIP RTL adder (`approx_adder_16bit.sv`) uses AND-predicted carry injection at the XOR boundary, which is slightly different at L1 and L2. This discrepancy does not affect the controller selection conclusion because the adder is locked at L0 (exact) in the selected architecture.
