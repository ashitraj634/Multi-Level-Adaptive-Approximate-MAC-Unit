`timescale 1ns/1ps

module approximate_multiplier_8bit_wo (
    input  logic [7:0] A,
    input  logic [7:0] B,
    input  logic [1:0] approx_level,
    output logic [15:0] P
);

    // Partial-product matrix
    logic [15:0] pp [7:0];

    integer i, j;

    always_comb begin

        for (i = 0; i < 8; i = i + 1) begin
            pp[i] = 16'b0;

            for (j = 0; j < 8; j = j + 1) begin

                // Column position = i + j
                if ((i + j) >= approx_level)
                    pp[i][i+j] = A[j] & B[i];
                else
                    pp[i][i+j] = 1'b0;

            end
        end
        P = 16'b0;

        for (i = 0; i < 8; i = i + 1)
            P = P + pp[i];

    end

endmodule
