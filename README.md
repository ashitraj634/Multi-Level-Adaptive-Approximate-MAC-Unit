# Adaptive Approximate MAC Unit for Energy-Efficient Edge AI

[![SystemVerilog](https://img.shields.io/badge/RTL-SystemVerilog-blue)](#)
[![Synthesis](https://img.shields.io/badge/Synthesis-Synopsys%20DC-green)](#synthesis)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An adaptive, multi-level approximate **Multiply-Accumulate (MAC)** unit implemented in SystemVerilog. The design dynamically selects the multiplier approximation level at runtime based on operand magnitude, achieving up to **26.9% power reduction** compared to an exact MAC while keeping arithmetic error below **0.5% on average**.

> **Target application:** Error-tolerant workloads such as CNN inference, digital filters, and signal processing at the edge.

---

## Table of Contents

1. [What This Project Does](#1-what-this-project-does)
2. [Architecture Overview](#2-architecture-overview)
3. [Approximation Levels](#3-approximation-levels)
4. [Adaptive Controller](#4-adaptive-controller)
5. [Design Variants](#5-design-variants)
6. [Verification](#6-verification)
7. [Synthesis Results](#7-synthesis-results)
8. [Python Controller Analysis](#8-python-controller-analysis)
9. [Repository Navigation](#9-repository-navigation)
10. [Tool Requirements](#10-tool-requirements)
11. [Known Issues and Limitations](#11-known-issues-and-limitations)

---

## 1. What This Project Does

A MAC unit computes:

```
Acc_next = Acc + (A × B)
```

Exact arithmetic uses full carry chains and all partial products, which costs power. This project asks: **can we selectively drop low-weight partial products during multiplication and still get useful results?**

The answer is yes — if the controller is smart about *when* to approximate. When input operands are large (high MSB), the dropped low-weight bits contribute negligibly to the final product relative to the dominant high-weight bits. When inputs are small, those low-weight bits matter and the controller keeps the multiplier exact.

The adder (accumulator update) is **always kept exact** — approximating it corrupts carry chains across the 16-bit accumulator, compounding errors uncontrollably over long accumulation sequences.

---

## 2. Architecture Overview

```
        A [7:0]        B [7:0]
            │               │
            ├───────────────┤
            │  MSB Controller│◄── Combinational
            │  (pure logic)  │    priority encoder
            └──┬────────────┘
               │
         mul_approx_level [1:0]    add_approx_level = 0 (hardwired exact)
               │                              │
               ▼                              │
   ┌──────────────────────┐                   │
   │  Approx Multiplier   │                   │
   │  8×8 → 16-bit        │                   │
   │  (column truncation  │                   │
   │   + MLAPC compressor)│                   │
   └──────────┬───────────┘                   │
              │ product [15:0]                │
              ▼                              ▼
   ┌──────────────────────────────────────────┐
   │      Exact 16-bit Adder (L0 always)      │
   └──────────────────────┬───────────────────┘
                          │ acc_next [15:0]
                          ▼
              ┌────────────────────┐
              │  D flip-flop (reg) │◄── clk, rst_n, en, clear
              └────────┬───────────┘
                       │
                   Acc [15:0]
```

**Key design decision:** Only the multiplier is approximated. The accumulator adder is locked at Level 0 (exact ripple-carry). This eliminates carry-suppression failures that caused unacceptable error accumulation in dual-approximate configurations.

---

## 3. Approximation Levels

### Multiplier (`approx_multiplier_comp.sv`)

Partial products `pp[i][j] = A[i] & B[j]` contribute to output column `(i + j)`. Truncation zeroes the lowest-weight columns before the reduction tree.

| Level | Action | Max error per product | Bias |
|:---:|:---|:---:|:---|
| **L0** | Exact (all 64 partial products) | 0 | None |
| **L1** | Zero column 0 (bit weight 1) | 1 | Always negative |
| **L2** | Zero columns 0–1 (bit weights 1, 2) | 5 | Always negative |
| **L3** | Zero columns 0–2 + MLAPC 6:3 compressor on column 5 | 17 | Negative (can be +ve with compressor) |

> **L3 compressor detail:** At Level 3, the six partial products contributing to column 5 (weight 32) are compressed using an approximate MLAPC 6:3 compressor (`Cout = x4 | x6` instead of exact majority), saving area in the reduction tree. This compressor can slightly overestimate the carry, introducing rare positive bias.

### Adder (`approx_adder_16bit.sv`)

| Level | XOR region (no carry) | Carry injection at boundary |
|:---:|:---|:---|
| **L0** | None — full ripple-carry | — |
| **L1** | Bits [1:0] | `A[1] & B[1]` (AND-predicted) |
| **L2** | Bits [3:0] | `A[3] & B[3]` |
| **L3** | Bits [7:0] | `A[7] & B[7]` |

> **Why adder L3 is dangerous:** Isolating the lower 8 bits from carry propagation on a 16-bit accumulator can cause ≥32,768-count errors when carries should have crossed bit 8. The adaptive controller therefore fixes the adder at L0.

---

## 4. Adaptive Controller

**Module:** `rtl/controller/msb_approx_controller.sv`

The controller detects the position of the most-significant `1` bit (MSB position) in each operand using a priority loop, then selects the multiplier level based on `min(msb_A, msb_B)`:

| Smaller operand's MSB position | Multiplier level | Adder level | Rationale |
|:---:|:---:|:---:|:---|
| ≥ 6 (operand ≥ 64) | **L3** | L0 | Product ≥ 4096 — dropping 3 columns costs < 0.4% |
| ≥ 5 (operand ≥ 32) | **L2** | L0 | Product ≥ 1024 — dropping 2 columns is safe |
| ≥ 4 (operand ≥ 16) | **L1** | L0 | Product ≥ 256 — dropping 1 column is safe |
| < 4 or either = 0 | **L0** | L0 | Small product — exact arithmetic required |

This policy runs at **L3 approximation 41.4% of cycles**, L2 for 15.0%, L1 for 7.9%, and exact L0 for 35.6% — based on the Python benchmark study across 25 representative workloads.

**Controller is fully combinational** — no state, no latency, output valid the same cycle as inputs.

A cleaner priority-encoder implementation is provided at `rtl/controller/msb_approx_controller_pe_variant.sv` (this variant was developed during the controller selection study; the loop-based version above was the one actually synthesized).

---

## 5. Design Variants

| File | Description | Multiplier | Controller | `clear` port |
|:---|:---|:---|:---|:---:|
| `rtl/top/approx_mac_with_comp_ctrl.sv` | **Final adaptive MAC** | Compressor-based (MLAPC) | MSB controller | ✓ |
| `rtl/top/approx_mac_wo_comp.sv` | Adaptive MAC, no compressor | Behavioural `+` reduction | Via external `mul/add_level` | ✓ |
| `rtl/top/approx_mac_wo_comp_ctrl.sv` | Non-compressor MAC + controller integrated | Non-compressor | MSB controller | ✓ |
| `rtl/top/approx_mac_with_comp_no_clear.sv` | Compressor MAC, no `clear` port | Compressor-based | MSB controller | ✗ |
| `rtl/top/approx_mac_fixed_level.sv` | Fixed-level baseline (mul L2, add L1) | Fixed L2 | None | ✓ |
| `rtl/arithmetic/exact_mac_hierarchy.sv` | Golden exact reference | Exact array multiplier | None | ✓ |

---

## 6. Verification

Three SystemVerilog testbenches are provided in `verification/`. All were run on **Cadence Incisive** (`$shm_open` waveform format). They cannot be run without a commercial HDL simulator.

### `tb_adaptive_mac_exhaustive.sv`
- **DUT:** Controller-driven adaptive MAC
- **Vectors:** All 65,536 (A, B) combinations, cleared every 16 steps
- **Checks:** Circular error (wraps correctly at 65,535→0), MAE, max absolute error, error count
- **DUT selection:** Compile-time `` `ifdef USE_COMP_WRAPPER `` selects between port styles

### `tb_fixed_mac_directed.sv`
- **DUT:** Fixed-level MAC (mul L2, add L1)
- **Vectors:** 11 directed test cases + 300 random
- **Checks:** Synchronous clear, en=0 hold, async reset mid-operation, all self-checking with pass/fail

### `tb_fixed_mac_exhaustive.sv`
- **DUT:** Fixed-level MAC (mul L2, add L1)
- **Vectors:** All 65,536 (A, B) pairs, same batching as exhaustive adaptive TB
- **Purpose:** PPA comparison baseline — same coverage as the adaptive TB

Simulation screenshots are in `verification/sim_screenshots/`.

---

## 7. Synthesis Results

All synthesis performed with **Synopsys Design Compiler**. Screenshots are in `synthesis/`.

| Configuration | Area (µm²) | Total Power (µW) | Power vs. Exact | Timing |
|:---|---:|---:|:---:|:---:|
| **Exact MAC** | 625.52 | 25.41 | — (baseline) | Met |
| Fixed-Level (mul L2, add L1) | 692.93 | 29.52 | **+16.2% ⚠️** | Met |
| **Adaptive MAC — no compressor** | 651.17 | 21.38 | **−15.9% ✓** | Met |
| **Adaptive MAC — with compressor + clock gating** | 704.18 | 18.58 | **−26.9% ✓✓** | Met |

> **Why is fixed-level *larger and more power-hungry* than exact?** The fixed-level design includes the approximation level mux logic (which adds gates) but the fixed L2 multiplier still computes columns 2–14, so only modest area is saved. The adder at L1 adds no area saving. The adaptive design benefits from real partial-product elimination and the MLAPC compressor shrinks the reduction tree structurally.

> **Source:** Reported from PPT slides, confirmed by synthesis screenshots in `synthesis/`. Synthesis conditions (library, PVT corner, timing constraint) are visible in the QOR screenshots.

---

## 8. Python Controller Analysis

A complete Python-based controller selection study is provided in `analysis/python_model/`. It models the RTL arithmetic in bit-exact Python and evaluates 5 controller strategies across 25 benchmark workloads.

**To run the full study:**
```bash
cd analysis/python_model
python run_experiment.py    # generates workload_results.csv and level_distributions.csv
python analyze.py           # generates summary_table.csv and nondominated.csv
python cross_verify.py      # re-runs all 26 architectures and prints the master table
```

**Key results (26 architectures × 25 workloads = 650 data points):**

| Controller | Avg Error | Max Spike | Exact-match workloads | Mult at L3 | Adder exact |
|:---|:---:|:---:|:---:|:---:|:---:|
| Exact (baseline) | 0 | 0 | 100% | 0% | 100% |
| Fixed mul-L1, add-exact | 10.2 | 40 | 4% | 0% | 100% |
| Fixed mul-L2, add-exact | 45.1 | 139 | 4% | 0% | 100% |
| **Method 5 MSB (selected)** | **74.8** | **340** | **36%** | **41%** | **100%** |
| Method 3 Threshold (dual) | 81.8 | 340 | 20% | 41% | 21% |
| Method 5 Magnitude | 95.4 | 375 | 36% | 60% | 100% |
| Method 2 Dual Adaptive | 101.0 | 395 | 20% | 60% | 18% |
| Method 4 Error Budget | 124.4 | 459 | 16% | 76% | 24% |
| Fixed mul-L3, add-exact | 147.2 | 459 | 4% | 100% | 100% |

Errors are 16-bit integer distances. The average error of 74.8 on a 16-bit output (max 65,535) corresponds to **~0.44% average relative error** on typical workloads.

---

## 9. Repository Navigation

```
adaptive-approximate-mac/
│
├── rtl/
│   ├── arithmetic/      ← Multiplier (comp & non-comp), adder, exact hierarchy
│   ├── controller/      ← MSB adaptive controller (loop & PE variants)
│   └── top/             ← 7 integration top-levels (all variants)
│
├── verification/
│   ├── *.sv             ← 3 testbenches (exhaustive & directed)
│   └── sim_screenshots/ ← Cadence waveform captures
│
├── synthesis/
│   ├── exact_mac/                       ← Exact MAC PPA evidence
│   ├── fixed_level_mac/                 ← Fixed-level PPA evidence
│   ├── adaptive_mac_wo_compressor/      ← Adaptive no-comp PPA evidence
│   └── adaptive_mac_with_compressor/    ← Adaptive comp + clock-gate PPA
│
├── analysis/
│   ├── python_model/    ← Bit-exact Python models + 5-method controller study
│   └── results/         ← CSV outputs (650-row experiment, characterisation)
│
├── figures/             ← PNG images for documentation
├── docs/                ← Supplementary technical Markdown documents
├── presentation/        ← Final project PPT (preserved)
└── reports/             ← Full report and low-power document (preserved)
```

---

## 10. Tool Requirements

| Task | Tool | Availability |
|:---|:---|:---|
| RTL simulation | Cadence Incisive or Questa/ModelSim | Commercial — required for testbenches |
| Synthesis | Synopsys Design Compiler | Commercial — results as screenshots |
| Python analysis | Python 3.8+ (stdlib only) | Free — `run_experiment.py` etc. |

> No open-source simulation flow has been tested. The testbenches use `$shm_open` (Cadence-specific). Adapting for Icarus Verilog would require replacing `$shm_open`/`$shm_probe` with `$dumpfile`/`$dumpvars`.

---

## 11. Known Issues and Limitations

See `docs/known_issues.md` for full details. Brief summary:

1. **Module name collision:** Two top-level files (`approx_mac_with_comp_ctrl.sv` and `approx_mac_wo_comp_ctrl.sv`) both originally defined `approx_mac_8bit` with different port lists. They are renamed in this repository.
2. **L3 compressor bias:** At Level 3, the MLAPC compressor can produce a small positive bias (overestimated carry), unlike pure truncation which is strictly negative. This is documented and expected per the reference paper.
3. **Adder characterisation:** Adder error bounds at L2 and L3 were sampled (not exhaustively proven). L3 adder error can reach the full 16-bit range.
4. **No gate-level verification:** Only RTL simulation and Python modelling were performed. No formal verification or gate-level simulation was run.
5. **Power/area comparisons are relative:** All synthesis results are from the same library and conditions but the specific standard cell library name and PVT corner are not disclosed in this repository.

---

## License

MIT License — see [LICENSE](LICENSE).

---

*Project by Rajas Ashit — VLSI Design Study, 2026*
