`timescale 1ns/1ps
//------------------------------------------------------------------------------
// Fixed-level approximate adder : LEVEL 1
//   Sum[15:2] = A[15:2] + B[15:2] + (A[1] & B[1])   (accurate upper part,
//                                                    carry predicted from bit 1)
//   Sum[1:0]  = A[1:0] ^ B[1:0]                      (approximate lower part)
// Same function as approx_adder_16bit with approx_level = 2'd1, but with the
// level mux removed.
//------------------------------------------------------------------------------
module approx_adder_16bit_L1 (
    input  logic [15:0] A,
    input  logic [15:0] B,
    output logic [15:0] Sum
);
    assign Sum[15:2] = A[15:2] + B[15:2] + 14'(A[1] & B[1]);
    assign Sum[1:0]  = A[1:0] ^ B[1:0];
endmodule


