# Known Issues and Technical Discrepancies

This document records all known problems, discrepancies across project revisions, and acknowledged limitations so the repository remains transparent and reproducible.

---

## Issue 1 — Module Name Collision Across Top-Level Files (Resolved)

**Problem:** In the original archive (`Approx_MAC/`), both `approx_mac.sv` and `mac_without_comp_cl.sv` declared `module approx_mac_8bit` with incompatible port lists and different internal architectures.

**Resolution in this repository:**
- `approx_mac.sv` (shared external `approx_level`, compressor multiplier, no controller) was moved to `rtl/top/approx_mac_shared_level_comp.sv` and its module renamed to `approx_mac_8bit_shared_comp`.
- `mac_with_comp_cl.sv` (`module approx_mac_8bit_with`, internal controller + compressor, no `clear` port) was moved to `rtl/top/approx_mac_with_comp_ctrl.sv`.
- `mac_without_comp_cl.sv` (`module approx_mac_8bit`, internal controller + non-compressor + `clear` port) was moved to `rtl/top/approx_mac_wo_comp_ctrl.sv` and retains `approx_mac_8bit` so `verification/tb_adaptive_mac_exhaustive.sv` compiles cleanly in its default mode.

---

## Issue 2 — Differences Between the Python Study Model and the ZIP RTL

**Problem:** The supplementary Python study in `analysis/python_model/` was developed against an earlier workspace RTL revision, so two arithmetic details differ from the final archive RTL in `rtl/`:

| Block | Authoritative ZIP RTL (`rtl/`) | Python Model (`analysis/python_model/rtl_model.py`) |
|:---|:---|:---|
| **Multiplier L3** | `approx_multiplier_comp.sv` zeroes columns `0–2` AND applies an MLAPC 6:3 compressor (`Cout = x4 \| x6`) on **column 5** (can overestimate carry). | Models pure column truncation (columns `0–2` zeroed; L3 compressor block evaluates to zero on column 2). |
| **Adder L1–L3** | `approx_adder_16bit.sv` injects AND-predicted carry (`A[L-1] & B[L-1]`) at the XOR boundary. | Models carry frozen at `0` across the XOR boundary. |

**Impact:** None on the **selected Method 5 MSB architecture**, because Method 5 holds the adder at `L0` (exact) and only adapts the multiplier. However, standalone adder/L3-compressor metrics in `analysis/results/` reflect the earlier pure-truncation / carry-zero model rather than the column-5 MLAPC and AND-carry RTL.

---

## Issue 3 — Non-Normalized Synthesis Runs Across Configurations

**Problem:** As explicitly highlighted in Slide 28 of `presentation/Approx_MAC_Final_Project.pptx`, the four Cadence Genus synthesis runs were captured under different operating conditions and flip-flop counts:
- `Exact MAC` (`exact_mac_unit_compat`) and `Adaptive without compressor` (`approx_mac_unit`) ran at **`PVT_0P9V_125C`** with **16 sequential cells**.
- `Fixed-level` (`approx_mac_8bit_fixed`) and `Adaptive with compressor + clock gating` (`approx_mac_8bit_comp`) ran at **`PVT_1P1V_0C`** with **26** and **17** (`16 FF + 1 ICG`) sequential cells, respectively.

Additionally, two different compressor area figures (`704.178` vs `618.336`) appeared across project revisions, and the `approx_mac_8bit_comp` fused compressor RTL (`comp_mac_tree`, `comp_adder16`) referenced in `reports/Low_Power_Technique.docx` was not included in the archive's `Approx_MAC/` RTL directory.

---

## Issue 4 — Synthesis Subfolder Duplicates Excluded

**Problem:** The archive contained `Approx_MAC/synthesis/` with duplicate copies of `fixed_adder.sv`, `fixed_mul.sv`, `fixed_mac.sv`, `tb_fixed_mac.sv`, and `tb_fixed_exh_mac.sv`.

**Resolution:** Excluded duplicates to avoid stale copies diverging from `rtl/` and `verification/`.

---

## Issue 5 — Commercial EDA Tools Required for RTL Simulation & Synthesis

- Testbenches use Cadence-specific `$shm_open` / `$shm_probe` tasks (Cadence Xcelium / SimVision). Open-source simulators (e.g., Icarus Verilog) require swapping these for `$dumpfile` / `$dumpvars`.
- Genus synthesis `.tcl` / `.sdc` scripts and gate-level netlists are not included; only the report screenshots are preserved.
- No gate-level simulation, formal equivalence checking, or post-layout physical design (Innovus/Tempus) was executed.
