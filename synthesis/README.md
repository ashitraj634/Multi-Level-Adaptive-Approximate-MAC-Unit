# Synthesis Results

All synthesis runs were performed with **Synopsys Design Compiler (DC)**. Screenshots of the actual DC reports (area, power, QOR, timing, clock-gating) are provided for each design variant.

---

## PPA Comparison Table

| Configuration | Area (µm²) | Total Power (µW) | Power vs. Exact | Critical Path | Clock period met? |
|:---|---:|---:|:---:|:---|:---:|
| **Exact MAC** | 625.52 | 25.41 | — (baseline) | — | ✓ |
| Fixed-Level (mul L2, add L1) | 692.93 | 29.52 | **+16.2%** | — | ✓ |
| **Adaptive MAC — no compressor** | 651.17 | 21.38 | **−15.9%** | — | ✓ |
| **Adaptive MAC — with compressor + clock gating** | 704.18 | 18.58 | **−26.9%** | — | ✓ |

> Source: PPT slide data, confirmed by DC report screenshots in sub-directories.

---

## Key Observations

### Why fixed-level is larger AND more power-hungry than exact:
The fixed-level design instantiates the full `approx_adder_16bit` with its level mux, and the fixed-L2 multiplier still computes columns 2–14 (12 out of 15). The approximation mux logic costs gates without proportional savings. Result: **+10.8% area, +16.2% power** vs exact.

### Why adaptive-without-compressor saves power (−15.9%):
The MSB controller gates the multiplier at L3 for ~41% of cycles (column 5 onwards only computed), reducing average switching activity. The adder is exact but small (16-bit ripple-carry). No clock gating applied — savings are purely from input-dependent switching reduction.

### Why adaptive-with-compressor is the most efficient (−26.9% power):
1. The MLAPC compressor reduces the reduction tree depth at L3, lowering combinational toggling
2. Clock gating is applied — the accumulator register clock is gated when `en = 0`, eliminating register switching power during idle cycles
3. Operand isolation gates inputs to the multiplier when `en = 0`

---

## Screenshot Index

### `exact_mac/`
| File | Report type |
|:---|:---|
| `exact_power.png` | Power analysis report |
| `exact_qor.png` | Quality of Results (QOR) summary |
| `exact_timing.png` | Timing path report |

### `fixed_level_mac/`
| File | Report type |
|:---|:---|
| `fixed_mac_area.jpeg` | Area report |
| `fixed_mac_power.png` | Power analysis |
| `fixed_mac_qor.jpeg` | QOR summary |
| `fixed_mac_timing.png` | Timing path |

### `adaptive_mac_wo_compressor/`
| File | Report type |
|:---|:---|
| `wo_comp_area.png` | Area report |
| `wo_comp_power.png` | Power analysis |
| `wo_comp_qor.png` | QOR summary |
| `wo_comp_timing.png` | Timing path |

### `adaptive_mac_with_compressor/`
| File | Report type |
|:---|:---|
| `COMP_area.png` | Area report |
| `COMP_clk_gating.png` | Clock gating report |
| `COMP_power.png` | Power analysis |
| `COMP_qor.png` | QOR summary |
| `COMP_timing.png` | Timing path |

---

## Synthesis Conditions

Tool: Synopsys Design Compiler  
Synthesis conditions (library, PVT corner, timing constraint) are visible in the QOR screenshot files. The same conditions were applied to all four designs for a fair comparison.

> **Limitation:** This repository does not include synthesis scripts, constraint files (SDC), or netlist outputs. Only the evidence screenshots from the tool runs are preserved.
