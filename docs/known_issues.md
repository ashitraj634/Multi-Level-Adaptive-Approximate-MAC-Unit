# Known Issues and Technical Discrepancies

This document records all known problems, discrepancies between files, and acknowledged limitations. It is provided to ensure the repository is technically honest and to help future contributors avoid confusion.

---

## Issue 1 — Module Name Collision (Resolved by Renaming)

**Problem:** In the original ZIP, two files both defined a module named `approx_mac_8bit` with different port lists:
- `approx_mac.sv`: includes `clear` port, instantiates compressor multiplier, uses internal controller
- `mac_without_comp_cl.sv`: includes `clear` port, instantiates non-compressor multiplier, uses internal controller

Both have the same module name but different port sets, which would cause a compilation error if both files appeared in the same compile list.

**Resolution:** In this repository, the files are renamed:
- `approx_mac.sv` → `rtl/top/approx_mac_with_comp_ctrl.sv`
- `mac_without_comp_cl.sv` → `rtl/top/approx_mac_wo_comp_ctrl.sv`

The original module names *inside* the files are unchanged — only the filenames are different.

---

## Issue 2 — Two Adder Implementations with Different Behaviour

**Problem:** The project contains two different implementations of the approximate adder:

| File | Carry behaviour at XOR boundary |
|:---|:---|
| `rtl/arithmetic/approx_adder_16bit.sv` (from ZIP — authoritative) | AND-predicted carry injection: `carry_in_to_bit_L = A[L-1] & B[L-1]` |
| Workspace Python model (used in analysis) | Carry frozen at 0 — no carry injected at boundary |

These produce different output values at L1, L2, L3. The ZIP RTL is the design that was actually synthesised and simulated.

**Resolution:** The Python analysis model (`analysis/python_model/rtl_model.py`) was derived from the workspace adder. Since the selected architecture locks the adder at L0 (exact), this discrepancy has no effect on the final design or the controller selection. It is documented here for completeness.

The ZIP adder is the authoritative implementation.

---

## Issue 3 — L3 Compressor Location

**Problem:** An earlier version of the Python model (not in this repository) incorrectly traced the L3 compressor to column 2. Column 2 partial products are **zeroed by the L3 truncation rule** before the compressor runs, so the compressor would have had no effect in that model.

**Actual RTL behaviour:** The MLAPC 6:3 compressor (`approx_mul_A_comp.sv`) is applied to **column 5** (the six partial products with bit weight 32). Column 5 is NOT zeroed by L3 truncation (which zeroes columns 0, 1, 2 only). The compressor is therefore genuinely active at L3 and reduces six inputs to three outputs using OR-based carry.

**Effect:** At L3, the compressor can produce a small **positive bias** (carry overestimate) in addition to the negative bias from column truncation. Pure column truncation is always negative-biased; the compressor modifies this.

**Resolution:** The Python model in this repository (`rtl_model.py`) correctly implements the compressor at column 5 for L3.

---

## Issue 4 — Synthesis Duplicate Files

**Problem:** The ZIP contains a `synthesis/` subfolder inside `Approx_MAC/` with copies of the fixed-level design files and testbenches. These were placed there as the input file set for a synthesis run.

**Resolution:** These copies are excluded from the RTL and verification directories. The synthesis sub-folder context (they were the design files fed to DC) is noted here and in `synthesis/README.md`.

---

## Issue 5 — Testbench Requires Commercial Simulator

**Problem:** All three testbenches use `$shm_open()` and `$shm_probe()`, which are Cadence Incisive-specific system tasks. They cannot run on Icarus Verilog, Verilator, or other open-source simulators without modification.

**Resolution:** No workaround is provided. If you wish to run the testbenches on an open-source simulator, replace:
```systemverilog
$shm_open("filename.shm");
$shm_probe(signal_name);
```
with:
```systemverilog
$dumpfile("filename.vcd");
$dumpvars(0, tb_module_name);
```

---

## Issue 6 — Two Controller RTL Styles

**Problem:** The ZIP contains `msb_approx_controller.sv` using a task-loop-based MSB finder. The workspace contains `mac_controller_method5.sv` using a cleaner priority-encoder (if-else chain) implementation of the identical policy.

Both implement the same decision table. The loop-based version was actually synthesised (confirmed by synthesis screenshots showing the controller's contribution). The priority-encoder version was not synthesised.

**Resolution:** Both are included in `rtl/controller/` with clear naming:
- `msb_approx_controller.sv` — synthesized version (use this for PPA)
- `msb_approx_controller_pe_variant.sv` — priority-encoder variant (use for tools preferring if-else chains or for readability)

---

## Issue 7 — Adder Error at L2 and L3 is Not Exhaustively Bounded

**Problem:** The adder characterisation in `analysis/results/adder_characterization.csv` was produced by **sampling**, not exhaustive enumeration. The adder output depends on both operands and the carry chain state, making exhaustive characterisation complex over all MAC-reachable values.

**Known sampled bounds:** At L2, observed max circular error ≈ 30. At L3, errors up to the full 16-bit range (65,535) have been observed when carries that should propagate past the XOR boundary do not.

**Resolution:** None — this is a known property of the XOR-boundary approximation. It motivates the design decision to fix the adder at L0 in the final architecture.

---

## Acknowledged Limitations

- **No gate-level simulation** — only RTL simulation and Python modelling were performed.
- **No formal verification** — no equivalence checking or model checking was run.
- **Power savings are dynamic-power dominant** — static/leakage power contribution is not separated in the reported numbers.
- **Library not disclosed** — the standard cell library name and PVT corner are visible only in the QOR screenshots and are not stated in this README.
