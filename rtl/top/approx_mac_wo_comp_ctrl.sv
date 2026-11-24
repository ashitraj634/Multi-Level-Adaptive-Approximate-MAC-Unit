`timescale 1ns/1ps

module approx_mac_8bit_wo_comp_ctrl (
    input logic clk, rst_n, en, clear,
    input logic [7:0] A, B,
    output logic [15:0] mac_result,
    output logic [15:0] product_dbg
);

    logic [1:0] mul_level, add_level;
    logic [15:0] acc_q, sum_comb, product;

    msb_approx_controller u_ctrl (
        .A(A), .B(B),
        .mul_approx_level(mul_level),
        .add_approx_level(add_level)
    );

    approximate_multiplier_8bit_wo u_mul (
        .A(A), .B(B), .approx_level(mul_level), .P(product)
    );

    assign product_dbg = product;

    approx_adder_16bit u_add (
        .A(acc_q), .B(product), .approx_level(add_level), .Sum(sum_comb)
    );

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) acc_q <= 16'h0000;
        else if (clear) acc_q <= 16'h0000;
        else if (en) acc_q <= sum_comb;
    end
    assign mac_result = acc_q;
endmodule

