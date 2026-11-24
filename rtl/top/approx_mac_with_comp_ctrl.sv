`timescale 1ns/1ps

// =============================================================
// Approximate 8-bit MAC (Multiply-Accumulate)
//
//   Acc <= Acc + (A * B)     on every clock edge where en = 1
//
//   Multiply : approximate_multiplier_8bit
//              (column-wise partial-product truncation +
//               compressor-based PPR tree, incl. the approximate
//               6:3 compressor at approx_level = 3)
//   Add      : approx_adder_16bit
//              (column-wise truncation with XOR-only low bits)
//
//   Both sub-blocks are driven by the same approx_level so the
//   whole datapath scales its accuracy/area tradeoff together.
//   Tie the two levels to separate inputs instead if you want the
//   multiplier and adder to be approximated independently.
// =============================================================
module approx_mac_8bit_comp_ctrl (
    input  logic        clk,
    input  logic        rst_n,       // active-low synchronous reset
    input  logic        en,          // accumulate enable
    input  logic [7:0]  A,
    input  logic [7:0]  B,
    input  logic [1:0]  approx_level,
    output logic [15:0] Acc,         // accumulator (registered)
    output logic [15:0] product      // combinational A*B, exposed for observability
);

    // -----------------------------------------------------------
    // Multiply stage (combinational)
    // -----------------------------------------------------------
    approximate_multiplier_8bit u_mult (
        .A            (A),
        .B            (B),
        .approx_level (approx_level),
        .P            (product)
    );

    // -----------------------------------------------------------
    // Accumulate stage (combinational adder, registered accumulator)
    // -----------------------------------------------------------
    logic [15:0] acc_next;

    approx_adder_16bit u_add (
        .A            (product),
        .B            (Acc),
        .approx_level (approx_level),
        .Sum          (acc_next)
    );

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            Acc <= 16'b0;
        else if (en)
            Acc <= acc_next;
        // else: hold current value
    end

endmodule


