# Verification — Testbenches and Simulation Evidence

## Overview

Three SystemVerilog testbenches are provided. They were run using **Cadence Xcelium** with **SimVision** (`$shm_open` / `$shm_probe` waveform capture).

> **Simulator note:** `$shm_open` and `$shm_probe` are Cadence-specific system tasks. To run on open-source simulators such as Icarus Verilog, replace those lines with `$dumpfile("out.vcd"); $dumpvars(0, tb_name);`.

---

## Testbench Summary

### 1. `tb_adaptive_mac_exhaustive.sv` (`module tb_approx_mac_cl`)
- **Coverage:** All **65,536 `(A, B)` pairs**, cleared (`clear = 1`) every `BATCH_SIZE = 16` vectors.
- **Metrics:** Circular 16-bit error (`min(|x-y|, 65536 - |x-y|)`), wrong-output count/percentage, max absolute error, MAE.
- **DUT Selection:**
  - Default (without `` `define USE_COMP_WRAPPER ``): instantiates `approx_mac_8bit` (`rtl/top/approx_mac_wo_comp_ctrl.sv`), which has `clear`, `mac_result`, and `product_dbg`.
  - With `` `define USE_COMP_WRAPPER ``: instantiates `approx_mac_8bit` with ports `(clk, rst_n, en, A, B, Acc, product)` — note that `approx_mac_8bit_with` (`rtl/top/approx_mac_with_comp_ctrl.sv`) matches those exact ports under the module name `approx_mac_8bit_with`.

```bash
# Example Cadence Xcelium compile/run (default non-compressor controller DUT)
xrun -sv tb_adaptive_mac_exhaustive.sv \
     ../rtl/top/approx_mac_wo_comp_ctrl.sv \
     ../rtl/arithmetic/approx_multiplier_wo_comp.sv \
     ../rtl/arithmetic/approx_adder_16bit.sv \
     ../rtl/controller/msb_approx_controller.sv
```

### 2. `tb_fixed_mac_directed.sv` (`module tb_approx_mac_8bit_fixed`)
- **DUT:** `approx_mac_8bit_fixed` (`rtl/top/approx_mac_fixed_level.sv`, fixed Mul L2 + Add L1).
- **Coverage:** 11 directed test cases (including `en=0` hold, synchronous `clear`, mid-operation async `rst_n`) + 300 random vectors, self-checked against an independent behavioral model.

### 3. `tb_fixed_mac_exhaustive.sv` (`module tb_approx_mac_fixed`)
- **DUT:** `approx_mac_8bit_fixed`.
- **Coverage:** All **65,536 `(A, B)` pairs**, cleared every 16 vectors, measuring circular error, MAE, and max error.

---

## Simulation Screenshots (`sim_screenshots/`)

| File | Description |
|:---|:---|
| `sim_01.png` – `sim_05.png` | Cadence SimVision waveforms & Xcelium outputs for controller-driven non-compressor MAC |
| `fixed_mac_func_op.png` | Fixed-level MAC directed functional output |
| `fixed_mac_func_op_exh.png` | Fixed-level MAC exhaustive sweep output |
