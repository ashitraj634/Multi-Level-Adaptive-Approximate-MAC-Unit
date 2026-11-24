# RTL Modules — Hierarchy and Dependencies

## Module Hierarchy

```
exact_mac_hierarchy.sv
  └─ exact_full_adder
  └─ exact_adder_16bit  (uses exact_full_adder)
  └─ exact_multiplier_8bit  (uses exact_adder_16bit)
  └─ exact_mac_unit  (uses exact_multiplier_8bit + exact_adder_16bit)
  └─ exact_mac_unit_compat  (drop-in wrapper for exact_mac_unit)

approx_mac_with_comp_ctrl.sv  [FINAL ADAPTIVE DESIGN]
  └─ msb_approx_controller  (controller/)
  └─ approximate_multiplier_8bit  (arithmetic/approx_multiplier_comp.sv)
  └─ approx_adder_16bit  (arithmetic/approx_adder_16bit.sv)

approx_mac_wo_comp.sv
  └─ approximate_multiplier_8bit_wo  (arithmetic/approx_multiplier_wo_comp.sv)
  └─ approx_adder_16bit

approx_mac_wo_comp_ctrl.sv
  └─ msb_approx_controller
  └─ approximate_multiplier_8bit_wo
  └─ approx_adder_16bit

approx_mac_with_comp_no_clear.sv
  └─ msb_approx_controller
  └─ approximate_multiplier_8bit
  └─ approx_adder_16bit

approx_mac_fixed_level.sv
  └─ approx_multiplier_8bit_L2  (top/approx_multiplier_fixed_L2.sv)
  └─ approx_adder_16bit_L1  (top/approx_adder_fixed_L1.sv)
```

---

## Module Reference

### arithmetic/approx_multiplier_comp.sv
**Module:** `approximate_multiplier_8bit`  
**Ports:** `A[7:0]`, `B[7:0]`, `approx_level[1:0]` → `P[15:0]`  
**Description:** Synthesis-safe compressor-PPR multiplier. Uses static column arrays (not dynamic queues). Applies MLAPC 6:3 approximate compressor to column 5 at L3. Verified exhaustively against all 65,536 input pairs at all 4 levels.

### arithmetic/approx_multiplier_wo_comp.sv
**Module:** `approximate_multiplier_8bit_wo`  
**Ports:** `A[7:0]`, `B[7:0]`, `approx_level[1:0]` → `P[15:0]`  
**Description:** Column-wise truncation with behavioural `+` reduction. Simulation-only PPR (not synthesis-optimised). Used in the non-compressor adaptive MAC variant.

### arithmetic/approx_adder_16bit.sv
**Module:** `approx_adder_16bit`  
**Ports:** `A[15:0]`, `B[15:0]`, `approx_level[1:0]` → `Sum[15:0]`  
**Description:** XOR-boundary approximate adder. Lower bits (determined by level) use XOR-only logic; upper bits use exact ripple-carry with AND-predicted carry injection from the boundary. **Always driven at L0 (exact) in the final design.**

### arithmetic/exact_mac_hierarchy.sv
**Modules:** `exact_full_adder`, `exact_adder_16bit`, `exact_multiplier_8bit`, `exact_mac_unit`, `exact_mac_unit_compat`  
**Description:** Structural exact MAC built from gate-level full adders and a ripple-carry chain. Used as the golden reference for PPA comparison. `exact_mac_unit_compat` accepts `mul_approx_level` and `add_approx_level` inputs (ignored) for direct testbench compatibility.

### controller/msb_approx_controller.sv
**Module:** `msb_approx_controller`  
**Ports:** `A[7:0]`, `B[7:0]` → `mul_approx_level[1:0]`, `add_approx_level[1:0]`  
**Description:** Loop-based MSB finder (synthesized version). Pure combinational. `add_approx_level` is always `2'b00`.

### controller/msb_approx_controller_pe_variant.sv
**Module:** `mac_controller_method5`  
**Description:** Priority-encoder implementation of the same policy (cleaner, but not the synthesized version). Use as reference or for tools that prefer if-else priority chains.

---

## Signal Conventions

| Signal | Direction | Width | Description |
|:---|:---|:---:|:---|
| `clk` | input | 1 | Rising-edge clock |
| `rst_n` | input | 1 | Asynchronous active-low reset |
| `en` | input | 1 | Accumulate enable (hold when 0) |
| `clear` | input | 1 | Synchronous accumulator clear (priority over `en`) |
| `A`, `B` | input | 8 | Unsigned multiplicand operands |
| `mul_approx_level` | input | 2 | Multiplier approximation (0=exact, 3=most approx) |
| `add_approx_level` | input | 2 | Adder approximation (held at 0 in final design) |
| `mac_result` / `Acc` | output | 16 | Registered accumulator output |
| `product_dbg` / `product` | output | 16 | Combinational product (debug/observe) |
