`timescale 1ns/1ps
//------------------------------------------------------------------------------
// Fixed-level approximate 8-bit MAC
//   Multiplier : level 2      Adder : level 1
// No MSB controller and no level muxes -> baseline for PPA comparison against
// the multi-level approx_mac_8bit.
//------------------------------------------------------------------------------
module approx_mac_8bit_fixed (
    input  logic        clk,
    input  logic        rst_n,        // async active-low reset
    input  logic        en,
    input  logic        clear,        // sync clear of accumulator
    input  logic [7:0]  A,
    input  logic [7:0]  B,
    output logic [15:0] mac_result,
    output logic [15:0] product_dbg
);
    logic [15:0] acc_q, sum_comb, product;

    approx_multiplier_8bit_L2 u_mul (
        .A(A), .B(B), .P(product)
    );

    assign product_dbg = product;

    approx_adder_16bit_L1 u_add (
        .A(acc_q), .B(product), .Sum(sum_comb)
    );

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)      acc_q <= 16'h0000;
        else if (clear)  acc_q <= 16'h0000;
        else if (en)     acc_q <= sum_comb;
    end

    assign mac_result = acc_q;
endmodule
