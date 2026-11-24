`timescale 1ns/1ps
// MAC wrapper with compressor-based multiplier implementation selected
// by the compiled approximate_multiplier_8bit module.
module approx_mac_8bit_with (
    input logic clk, rst_n, en,
    input logic [7:0] A, B,
    output logic [15:0] Acc,
    output logic [15:0] product
);
    logic [1:0] mul_level, add_level;
    logic [15:0] acc_next;
    msb_approx_controller u_ctrl (
        .A(A), .B(B),
        .mul_approx_level(mul_level),
        .add_approx_level(add_level)
    );
    approximate_multiplier_8bit u_mult (
        .A(A), .B(B), .approx_level(mul_level), .P(product)
    );
    approx_adder_16bit u_add (
        .A(product), .B(Acc), .approx_level(add_level), .Sum(acc_next)
    );
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) Acc <= 16'h0000;
        else if (en) Acc <= acc_next;
    end
endmodule
