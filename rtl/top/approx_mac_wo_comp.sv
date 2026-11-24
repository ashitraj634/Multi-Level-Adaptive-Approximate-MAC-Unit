`timescale 1ns/1ps

module approx_mac_unit (
    input  logic        clk,
    input  logic         rst_n,        
    input  logic         en,           
    input  logic         clear,        
    input  logic [7:0]   A,
    input  logic [7:0]   B,
    input  logic [1:0]   mul_approx_level,
    input  logic [1:0]   add_approx_level,
    output logic [15:0]  mac_result,   // registered accumulator output
    output logic [15:0]  product_dbg  
);

    logic [15:0] product;

    approximate_multiplier_8bit_wo u_mul (
        .A            (A),
        .B            (B),
        .approx_level (mul_approx_level),
        .P            (product)
    );

    assign product_dbg = product;
    logic [15:0] acc_q;
    logic [15:0] sum_comb;

    approx_adder_16bit u_add (
        .A            (acc_q),
        .B            (product),
        .approx_level (add_approx_level),
        .Sum          (sum_comb)
    );

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            acc_q <= 16'h0000;
        else if (clear)
            acc_q <= 16'h0000;
        else if (en)
            acc_q <= sum_comb;
        // else: hold current value
    end

    assign mac_result = acc_q;

endmodule
