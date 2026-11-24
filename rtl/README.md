# RTL Modules — Hierarchy and Dependencies

## Module Hierarchy

```text
exact_mac_hierarchy.sv
  ├─ exact_full_adder
  ├─ exact_adder_16bit       (uses exact_full_adder)
  ├─ exact_multiplier_8bit   (uses exact_adder_16bit)
  ├─ exact_mac_unit          (uses exact_multiplier_8bit + exact_adder_16bit)
  └─ exact_mac_unit_compat   (drop-in compatibility wrapper)

approx_mac_with_comp_ctrl.sv  (module: approx_mac_8bit_with, no clear port)
  ├─ msb_approx_controller        (controller/msb_approx_controller.sv)
  ├─ approximate_multiplier_8bit  (arithmetic/approx_multiplier_comp.sv)
  └─ approx_adder_16bit           (arithmetic/approx_adder_16bit.sv)

approx_mac_wo_comp_ctrl.sv    (module: approx_mac_8bit, with clear port)
  ├─ msb_approx_controller        (controller/msb_approx_controller.sv)
  ├─ approximate_multiplier_8bit_wo (arithmetic/approx_multiplier_wo_comp.sv)
  └─ approx_adder_16bit           (arithmetic/approx_adder_16bit.sv)

approx_mac_wo_comp.sv         (module: approx_mac_unit, external mul/add levels)
  ├─ approximate_multiplier_8bit_wo
  └─ approx_adder_16bit

approx_mac_shared_level_comp.sv (module: approx_mac_8bit_shared_comp, shared approx_level)
  ├─ approximate_multiplier_8bit
  └─ approx_adder_16bit

approx_mac_fixed_level.sv     (module: approx_mac_8bit_fixed, Mul L2 / Add L1)
  ├─ approx_multiplier_8bit_L2    (top/approx_multiplier_fixed_L2.sv)
  └─ approx_adder_16bit_L1        (top/approx_adder_fixed_L1.sv)
```

---

## Module Reference

### `arithmetic/approx_multiplier_comp.sv`
- **Module:** `approximate_multiplier_8bit`
- **Ports:** `A[7:0]`, `B[7:0]`, `approx_level[1:0]` → `P[15:0]`
- **Description:** Synthesizable static-array PPR tree multiplier (`MAXH=10`, `NPASS=8`). Zeroes columns `i + j < approx_level`. At `L3`, gates the 6 bits of column 5 and feeds them through `approx_6to3` (MLAPC, Chu et al. IEEE TVLSI 2022: `Cout = x4 | x6`, `S1 = x5`, `S0 = x2`).

### `arithmetic/approx_multiplier_wo_comp.sv`
- **Module:** `approximate_multiplier_8bit_wo`
- **Ports:** `A[7:0]`, `B[7:0]`, `approx_level[1:0]` → `P[15:0]`
- **Description:** Column-wise partial-product truncation with behavioral `+` summation (Genus infers its own adder tree).

### `arithmetic/approx_adder_16bit.sv`
- **Module:** `approx_adder_16bit`
- **Ports:** `A[15:0]`, `B[15:0]`, `approx_level[1:0]` → `Sum[15:0]`
- **Description:** Lower bits use `A[k] ^ B[k]` (`L1`: `[1:0]`, `L2`: `[3:0]`, `L3`: `[7:0]`), upper bits use exact addition with AND-predicted carry-in (`A[1]&B[1]`, `A[3]&B[3]`, or `A[7]&B[7]`). Driven at `L0` (exact) by `msb_approx_controller`.

### `arithmetic/exact_mac_hierarchy.sv`
- **Modules:** `exact_full_adder`, `exact_adder_16bit`, `exact_multiplier_8bit`, `exact_mac_unit`, `exact_mac_unit_compat`
- **Description:** Structural exact MAC golden reference built from 1-bit full adders. `exact_mac_unit_compat` accepts ignored level ports for testbench compatibility and was synthesized as `exact_mac_unit_compat`.

### `controller/msb_approx_controller.sv`
- **Module:** `msb_approx_controller`
- **Ports:** `A[7:0]`, `B[7:0]` → `mul_approx_level[1:0]`, `add_approx_level[1:0]`
- **Description:** Authoritative combinational controller from the project archive. Uses an `msb_position` loop function and maps `min(msb_A, msb_B)` to `mul_approx_level`, keeping `add_approx_level = 2'd0`.

### `controller/msb_approx_controller_pe_variant.sv`
- **Module:** `mac_controller_method5`
- **Description:** Priority-encoder (`if / else if`) variant created during the controller exploration study (`Acc` port present, unused). Not the version synthesized in Genus.
