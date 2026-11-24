`timescale 1ns/1ps
//------------------------------------------------------------------------------
// Fixed-level approximate 8x8 multiplier : LEVEL 2
//   Partial-product bits whose column (i+j) < 2 are forced to zero, so
//   columns 0 and 1 are never generated. P[1:0] is always 0.
// Same function as approximate_multiplier_8bit_wo with approx_level = 2'd2.
//------------------------------------------------------------------------------
module approx_multiplier_8bit_L2 (
    input  logic [7:0]  A,
    input  logic [7:0]  B,
    output logic [15:0] P
);
    localparam int LEVEL = 2;

    logic [15:0] pp [8];

    always_comb begin
        for (int i = 0; i < 8; i++) begin
            pp[i] = 16'b0;
            for (int j = 0; j < 8; j++) begin
                if ((i + j) >= LEVEL)
                    pp[i][i+j] = A[j] & B[i];
            end
        end

        P = 16'b0;
        for (int i = 0; i < 8; i++)
            P = P + pp[i];
    end
endmodule


