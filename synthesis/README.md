# Synthesis Results (Cadence Genus 21.14)

All synthesis runs were performed with **Cadence Genus(TM) Synthesis Solution 21.14-s082_1** using the **Joules** power engine and a **10 ns (`10000 ps`) clock constraint**. Report screenshots are preserved in the subdirectories below.

---

## PPA Comparison Table (From Genus Report Screenshots & Final Presentation)

| Configuration | Module Name | Operating Conditions (PVT) | Seq. Cells | Total Cells | Cell Area | Total Power (µW) | Power vs. Exact | Worst Slack (ps) |
|:---|:---|:---|---:|---:|---:|---:|:---:|---:|
| **Exact MAC** | `exact_mac_unit_compat` | `PVT_0P9V_125C` | 16 | 194 | 625.518 | 25.409 | Baseline | 1268.8 |
| **Fixed-Level (Mul L2 / Add L1)** | `approx_mac_8bit_fixed` | `PVT_1P1V_0C` | 26 | 228 | 692.932 | 29.519 | +16.2% | 5181.9 |
| **Adaptive (no compressor)** | `approx_mac_unit` | `PVT_0P9V_125C` | 16 | 213 | 651.168 | 21.380 | −15.9% | 2831.4 |
| **Adaptive (comp + clock gating)** | `approx_mac_8bit_comp` | `PVT_1P1V_0C` | 17 *(16 FF + 1 ICG)* | 313 | 704.178 | 18.583 | −26.9% | 6916.5 |

> **Important Normalization Caveat:** As documented in Slide 28 of `presentation/Approx_MAC_Final_Project.pptx`, these preliminary synthesis runs were **not normalized** to a single PVT corner or flip-flop count (`PVT_0P9V_125C` vs `PVT_1P1V_0C`, and 16 vs 26 sequential cells in the fixed-level run). Power estimates also depend on synthesis switching activity assumptions (e.g., 25% toggle saving estimate on 16 clock-gated FFs in `COMP_clk_gating.png`).

---

## Observations From the Reports

1. **Exact MAC (`exact_mac/`):** 194 cells, 625.518 cell area, 25.409 µW (68.39% logic, 30.59% register, 1.02% clock).
2. **Fixed-Level MAC (`fixed_level_mac/`):** Higher area (692.932) and power (29.519 µW) than exact in these runs, synthesized at `PVT_1P1V_0C` with 26 sequential instances.
3. **Adaptive without Compressor (`adaptive_mac_wo_compressor/`):** Synthesized `approx_mac_unit` at `PVT_0P9V_125C` (matching Exact MAC's PVT corner and 16 FFs): **21.380 µW (−15.9% power)** for **+4.1% area (651.168)** and improved slack (`2831.4 ps` vs `1268.8 ps`).
4. **Adaptive with Compressor + Clock Gating (`adaptive_mac_with_compressor/`):** Synthesized `approx_mac_8bit_comp` (using Genus `lp_insert_clock_gating` + RTL operand isolation documented in `reports/Low_Power_Technique.docx`): **18.583 µW (−26.9% vs Exact)**, 1 clock-gating cell gating 16/16 FFs, slack `6916.5 ps`, cell area `704.178` (`PVT_1P1V_0C`).

---

## Limitations

- TCL synthesis scripts, `.sdc` constraint files, and gate-level netlists are not included in this repository (only the Genus terminal screenshots).
- The `approx_mac_8bit_comp` sub-modules (`comp_mac_tree`, `comp_adder16`) referenced in `Low_Power_Technique.docx` and `COMP_qor.png` were not packaged in the archive's RTL folder; `rtl/arithmetic/approx_multiplier_comp.sv` and `rtl/top/approx_mac_with_comp_ctrl.sv` contain the standalone compressor-based RTL preserved in the archive.
