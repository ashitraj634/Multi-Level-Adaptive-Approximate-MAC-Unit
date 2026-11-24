# Verification — Testbenches and Simulation Evidence

## Overview

Three SystemVerilog testbenches are provided. All testbenches were executed on **Cadence Incisive** (NC-Verilog). They require a commercial HDL simulator.

> **Waveform format:** `$shm_open` / `$shm_probe` — Cadence Incisive SHM database format.  
> **Adapting for open-source simulators:** Replace `$shm_open`/`$shm_probe` with `$dumpfile`/`$dumpvars` for Icarus Verilog compatibility.

---

## Testbench Summary

### 1. `tb_adaptive_mac_exhaustive.sv`

| Property | Value |
|:---|:---|
| **DUT** | Controller-driven adaptive MAC |
| **Coverage** | All 65,536 (A, B) combinations |
| **Accumulator handling** | Synchronous `clear` every 16 vectors |
| **Error metric** | Circular error (correctly handles 16-bit wrap) |
| **Outputs** | MAE, max absolute error, error count, error rate % |

**DUT selection:** Compile with `` `define USE_COMP_WRAPPER `` to instantiate the simpler port style (no `clear`), or leave undefined to use the full `clear`-capable top level.

```bash
# Cadence Incisive — compressor MAC variant
ncvlog -sv tb_adaptive_mac_exhaustive.sv ../rtl/top/approx_mac_with_comp_ctrl.sv \
       ../rtl/arithmetic/approx_multiplier_comp.sv \
       ../rtl/arithmetic/approx_adder_16bit.sv \
       ../rtl/controller/msb_approx_controller.sv
ncelab tb_approx_mac_cl
ncsim tb_approx_mac_cl
```

### 2. `tb_fixed_mac_directed.sv`

| Property | Value |
|:---|:---|
| **DUT** | `approx_mac_8bit_fixed` (mul L2, add L1) |
| **Coverage** | 11 directed test cases + 300 random vectors |
| **Checks** | Reset, clear, en=0 hold, mid-operation async reset |
| **Self-checking** | Yes — reports PASS/FAIL per test case |

Specific directed tests:
- TC1–TC7: Accumulation sequence, en gating, hold
- TC8: `en=0` — verify accumulator holds previous value
- TC9: Synchronous clear — accumulator resets to 0
- TC10a/b: Async reset asserted mid-operation — immediate effect
- TC11: 300 random vectors against software reference model

### 3. `tb_fixed_mac_exhaustive.sv`

| Property | Value |
|:---|:---|
| **DUT** | `approx_mac_8bit_fixed` (mul L2, add L1) |
| **Coverage** | All 65,536 (A, B) combinations |
| **Purpose** | PPA comparison baseline — same coverage as adaptive exhaustive TB |
| **Outputs** | MAE, max absolute error, error count, error rate % |

---

## Simulation Screenshots

Located in `sim_screenshots/`. These are captures from Cadence waveform viewer showing the non-compressor adaptive MAC (`approx_mac_wo_comp_ctrl.sv`) operating correctly.

| File | Shows |
|:---|:---|
| `sim_01.png` | Reset and first accumulation |
| `sim_02.png` | Accumulation sequence |
| `sim_03.png` | Clear behaviour |
| `sim_04.png` | Full accumulation sequence |
| `sim_05.png` | Edge-case inputs |
| `fixed_mac_func_op.png` | Fixed-level MAC functional output |
| `fixed_mac_func_op_exh.png` | Exhaustive TB terminal output |

---

## Circular Error Function

Both exhaustive testbenches use a **circular distance** error metric for 16-bit values:

```
circular_error(x, y) = min(|x − y|, 65536 − |x − y|)
```

This correctly handles accumulator wrap-around at 65,535 → 0, where a linear distance of 65,534 is actually a circular distance of 2.
