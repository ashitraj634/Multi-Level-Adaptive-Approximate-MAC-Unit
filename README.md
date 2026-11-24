# Adaptive Approximate MAC Unit for Energy-Efficient Edge AI

[![RTL](https://img.shields.io/badge/RTL-SystemVerilog-blue)](#)
[![Synthesis](https://img.shields.io/badge/Synthesis-Cadence%20Genus%2021.14-green)](#7-synthesis-results)
[![Simulation](https://img.shields.io/badge/Simulation-Cadence%20Xcelium-orange)](#6-verification)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An adaptive, multi-level approximate **Multiply-Accumulate (MAC)** unit implemented in SystemVerilog. The design dynamically selects the multiplier approximation level at runtime based on operand MSB magnitude while keeping the 16-bit accumulator adder exact (`L0`), targeting energy-efficient Edge AI and DSP workloads.

> **Engineering transparency note:** This repository preserves the project's **actual** RTL, testbenches, Cadence Xcelium simulation results, Cadence Genus synthesis screenshots, presentation, reports, and supplementary Python controller study — including documented limitations (such as mixed PVT corners across preliminary synthesis runs) rather than presenting an artificially normalized story.

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

```text
Acc_next = Acc + (A × B)
```

Exact arithmetic uses full partial-product reduction and carry propagation every cycle, even when operands are large enough that losing a few least-significant bits causes negligible error. Conversely, approximating small operands or the accumulator adder can introduce large relative or carry-chain errors.

This project investigates **8-bit unsigned inputs (`A`, `B`)** with a **16-bit accumulator (`Acc`)**, exploring:
- **Four approximation levels (`L0–L3`)** for both multiplier and adder.
- **Runtime MSB-driven adaptive control** (`msb_approx_controller`) that adjusts only the multiplier level per cycle while locking the adder at `L0` (exact).
- **Compressor-based vs. non-compressor partial-product reduction**, plus **clock gating** and **operand isolation**.

---

## 2. Architecture Overview

```text
        A [7:0]        B [7:0]
            │               │
            ├───────────────┤
            │  MSB Controller│◄── Combinational MSB detector
            │  (pure logic)  │    (min(msb_A, msb_B))
            └──┬────────────┘
               │
         mul_approx_level [1:0]    add_approx_level = 2'b00 (Exact L0)
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
   │      16-bit Adder (held at L0 Exact)     │
   └──────────────────────┬───────────────────┘
                          │ sum_comb [15:0]
                          ▼
              ┌────────────────────┐
              │  Accumulator Reg   │◄── clk, rst_n, en, clear
              └────────┬───────────┘
                       │
                   Acc [15:0]
```

**Why keep the adder exact (`L0`)?** Standalone Xcelium characterization (`196,608` vectors per level) showed that approximate adder `L3` reaches **86.65% error rate** and **max error 254** per step (and up to **65,534** in MAC wraparound/carry-loss scenarios), whereas the multiplier max error at `L3` is bounded (`17` for column truncation). Keeping the adder exact prevents carry-chain corruption in the accumulator.

---

## 3. Approximation Levels

### Multiplier (`rtl/arithmetic/approx_multiplier_comp.sv` and `approx_multiplier_wo_comp.sv`)

Partial products `pp[i][j] = A[j] & B[i]` contribute to output column `(i + j)`. Column-wise truncation forces `pp[i][j] = 0` when `(i + j) < approx_level`.

| Level | Columns Removed | Compressor Behavior (`approx_multiplier_comp.sv`) | Multiplier Exhaustive Max Error | Multiplier MAE |
|:---:|:---|:---|:---:|:---:|
| **L0** | None (exact) | Exact 3:2 / 2:2 PPR tree | 0 | 0.000 |
| **L1** | Column C0 | Exact 3:2 / 2:2 PPR tree | 1 | 0.250 |
| **L2** | Columns C0–C1 | Exact 3:2 / 2:2 PPR tree | 5 | 1.250 |
| **L3** | Columns C0–C2 | MLAPC 6:3 approx. compressor on **column 5** (`Cout = x4 \| x6`) | 17 *(pure trunc. ref.)* | 4.250 *(pure trunc. ref.)* |

> **Important RTL detail:** In `approx_multiplier_comp.sv`, the MLAPC 6:3 approximate compressor (Chu et al., IEEE TVLSI 2022) replaces the 6 bits of **column 5** (weight 32) at `L3`, which can overestimate carry (`Cout = x4 | x6`). See [docs/known_issues.md](docs/known_issues.md) for how this differs from the Python model's pure truncation model.

### Adder (`rtl/arithmetic/approx_adder_16bit.sv`)

| Level | Low Bits Using XOR-Only (`A[k] ^ B[k]`) | Carry Injection to Upper Bits | Xcelium Tested Error Rate (196,608 vecs) | Max Single-Step Error |
|:---:|:---|:---|:---:|:---:|
| **L0** | None (exact `+`) | Exact ripple carry | 0.00% | 0 |
| **L1** | Bits `[1:0]` | `A[1] & B[1]` (AND-predicted) | 25.00% | 2 |
| **L2** | Bits `[3:0]` | `A[3] & B[3]` | 57.81% | 14 |
| **L3** | Bits `[7:0]` | `A[7] & B[7]` | 86.65% | 254 |

---

## 4. Adaptive Controller

**Module:** `rtl/controller/msb_approx_controller.sv`

The controller finds the highest set bit (`msb_position`) of `A` and `B` (`-1` if zero) and uses `min(msb_A, msb_B)`:

| `min(msb_A, msb_B)` | `mul_approx_level` | `add_approx_level` | Rationale |
|:---:|:---:|:---:|:---|
| `>= 6` (both `>= 64`) | **L3** | L0 | Large operands tolerate 3 truncated columns with tiny relative error |
| `== 5` | **L2** | L0 | Medium-high operands truncate 2 columns |
| `== 4` | **L1** | L0 | Medium operands truncate 1 column |
| `< 4` or either operand `== 0` | **L0** | L0 | Small/zero operands stay exact |

An alternative priority-encoder RTL variant created during the controller exploration study is included at `rtl/controller/msb_approx_controller_pe_variant.sv`.

---

## 5. Design Variants

| File | Module Name | Multiplier Used | Controller | `clear` Port |
|:---|:---|:---|:---|:---:|
| `rtl/top/approx_mac_with_comp_ctrl.sv` | `approx_mac_8bit_with` | Compressor (`approximate_multiplier_8bit`) | `msb_approx_controller` | ✗ |
| `rtl/top/approx_mac_wo_comp_ctrl.sv` | `approx_mac_8bit` | Non-comp (`approximate_multiplier_8bit_wo`) | `msb_approx_controller` | ✓ |
| `rtl/top/approx_mac_wo_comp.sv` | `approx_mac_unit` | Non-comp (`approximate_multiplier_8bit_wo`) | External `mul`/`add_approx_level` | ✓ |
| `rtl/top/approx_mac_shared_level_comp.sv` | `approx_mac_8bit_shared_comp` | Compressor (`approximate_multiplier_8bit`) | External shared `approx_level` | ✗ |
| `rtl/top/approx_mac_fixed_level.sv` | `approx_mac_8bit_fixed` | Fixed L2 (`approx_multiplier_8bit_L2`) + Fixed L1 adder | None | ✓ |
| `rtl/arithmetic/exact_mac_hierarchy.sv` | `exact_mac_unit` / `exact_mac_unit_compat` | Exact array multiplier + exact RCA | None | ✓ |

---

## 6. Verification

Three SystemVerilog testbenches are located in `verification/`, executed on **Cadence Xcelium / SimVision** (`$shm_open` / `$shm_probe` waveforms):

1. **`tb_adaptive_mac_exhaustive.sv`**: Sweeps all **65,536 `(A, B)` pairs** in batches of 16 cycles (`clear` between batches) and computes circular modular error against an exact 16-bit reference.
   - Reported exhaustive controller-driven MAC metrics (PPT Slide 17): **65.73% outputs differ**, **max error = 136** (0.21% of full scale), **MAE = 20.07**.
2. **`tb_fixed_mac_exhaustive.sv`**: Sweeps all **65,536 `(A, B)` pairs** in 16-cycle batches on `approx_mac_8bit_fixed` (Mul L2, Add L1).
   - Reported exhaustive fixed MAC metrics (PPT Slides 21 & 27): **70.31% outputs differ**, **max error = 40**, **MAE = 9.75**.
3. **`tb_fixed_mac_directed.sv`**: 11 directed tests (`rst_n`, `clear`, `en=0` hold, mid-operation async reset) + 300 random vectors on `approx_mac_8bit_fixed`.

Waveform captures and console outputs are preserved in `verification/sim_screenshots/`.

---

## 7. Synthesis Results

Synthesis was performed in **Cadence Genus 21.14 (`21.14-s082_1`)** with a **10 ns clock (`10000 ps`)** and **Joules** power estimation. Report screenshots are in `synthesis/`.

| Configuration | Synthesized Module | PVT Corner (from QOR) | Sequential Cells | Cell Area | Total Power (µW) | Power vs. Exact | Slack (ps) |
|:---|:---|:---|:---:|---:|---:|---:|---:|
| **Exact MAC** | `exact_mac_unit_compat` | `PVT_0P9V_125C` | 16 | 625.518 | 25.409 | Baseline | 1268.8 |
| **Fixed-Level (Mul L2 / Add L1)** | `approx_mac_8bit_fixed` | `PVT_1P1V_0C` | 26 | 692.932 | 29.519 | +16.2% | 5181.9 |
| **Adaptive (no compressor)** | `approx_mac_unit` | `PVT_0P9V_125C` | 16 | 651.168 | 21.380 | −15.9% | 2831.4 |
| **Adaptive (comp + clock gating)** | `approx_mac_8bit_comp` | `PVT_1P1V_0C` | 17 *(16 FF + 1 ICG)* | 704.178 | 18.583 | −26.9% | 6916.5 |

> **Critical caveat (also noted on PPT Slide 28):** The preliminary Genus synthesis runs were **not normalized** across one uniform PVT corner, wrapper, or flip-flop count (`0.9 V / 125 °C` vs `1.1 V / 0 °C`, and `16` vs `26` sequential instances). Moreover, `approx_mac_8bit_comp` (which used a fused compressor tree + clock gating + operand isolation) is documented in `reports/Low_Power_Technique.docx` and `synthesis/adaptive_mac_with_compressor/`, while its fused `.sv` sub-blocks (`comp_mac_tree`, `comp_adder16`) were not packaged in the archive. Re-running all variants under identical SDC, PVT corner, and activity is planned future work.

---

## 8. Python Controller Analysis

The `analysis/python_model/` directory contains a multi-workload Python comparison of **5 control strategies** across **25 named workloads** (707 MAC steps total, 26 architectures = 650 rows):

```bash
cd analysis/python_model
python run_experiment.py
python analyze.py
python cross_verify.py
```

Key comparison across the 5 methods (on identical 25 workloads; `rtl_model.py` uses pure column truncation for L3 and carry-zero XOR adder):

| Method / Architecture | Controls | Avg Workload Error | Max Error | Exact-Match Workloads | Mult at L3 | Adder Exact (L0) |
|:---|:---|:---:|:---:|:---:|:---:|:---:|
| `Exact` / `Fix_M0A0` | Baseline | 0.00 | 0 | 100.0% | 0.0% | 100.0% |
| **M5_AdaptMult_MSB** *(Selected)* | Multiplier only | **74.80** | **340** | **36.0%** | **41.4%** | **100.0%** |
| `M3_Threshold` | Both | 81.84 | 340 | 20.0% | 41.4% | 20.8% |
| `M5_AdaptMult_Mag` | Multiplier only | 95.44 | 375 | 36.0% | 59.5% | 100.0% |
| `M2_DualAdaptive` | Both | 101.04 | 395 | 20.0% | 59.5% | 17.8% |
| `M4_ErrorBudget` | Both | 124.44 | 459 | 16.0% | 75.8% | 24.0% |
| `M1_L11` (Fixed L1/L1) | Both fixed | 30.16 | 113 | 4.0% | 0.0% | 0.0% |

---

## 9. Repository Navigation

```text
adaptive-approximate-mac/
├── rtl/
│   ├── arithmetic/        ← Multipliers, approx adder, exact MAC hierarchy
│   ├── controller/        ← MSB adaptive controller (synthesized & PE variants)
│   └── top/               ← Top-level MAC wrappers (adaptive, fixed, shared)
├── verification/
│   ├── *.sv               ← Exhaustive & directed SystemVerilog testbenches
│   └── sim_screenshots/   ← Xcelium / SimVision functional captures
├── synthesis/             ← Cadence Genus QOR, area, power, timing, clk-gating PNGs
├── analysis/
│   ├── python_model/      ← Python 5-method controller study scripts
│   └── results/           ← Generated CSV datasets
├── figures/               ← Summary plots from Python evaluation
├── docs/                  ← Known issues & technical reconciliation notes
├── presentation/          ← Approx_MAC_Final_Project.pptx (30 slides)
└── reports/               ← Report_Approx_MAC.docx & Low_Power_Technique.docx
```

---

## 10. Tool Requirements

- **HDL Simulation:** Cadence Xcelium (uses `$shm_open` / `$shm_probe` for SimVision waveforms; replace with `$dumpfile` / `$dumpvars` for open-source simulators).
- **Synthesis:** Cadence Genus 21.14+ (evidence preserved as report screenshots; TCL/SDC scripts are not included).
- **Python Analysis:** Python 3.8+ (standard library only).

---

## 11. Known Issues and Limitations

Full details are documented in [docs/known_issues.md](docs/known_issues.md):
- Synthesis runs across configurations used non-normalized PVT corners (`0.9 V / 125 °C` vs `1.1 V / 0 °C`) and differing FF counts.
- `rtl_model.py` in `analysis/python_model/` models pure-truncation L3 and carry-zero XOR adder (from an earlier workspace revision), not the ZIP's column-5 MLAPC compressor (`approx_multiplier_comp.sv`) or AND-predicted adder (`approx_adder_16bit.sv`).
- No open-source RTL simulation was run in this environment; simulation evidence comes from the Cadence Xcelium runs preserved in the project deliverables.
- No physical design (Innovus PnR), post-layout STA, or application-level CNN/image PSNR-SSIM benchmarks have been executed yet.

---

## License

MIT License — see [LICENSE](LICENSE).
