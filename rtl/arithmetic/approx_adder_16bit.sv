`timescale 1ns/1ps

module approx_adder_16bit (
    input  logic [15:0] A,
    input  logic [15:0] B,
    input  logic [1:0]  approx_level,
    output logic [15:0] Sum
);

    always_comb begin
        Sum = 16'b0;

        case (approx_level)

            2'd0: begin
                Sum = A + B;
            end

	     // Level 1
            2'd1: begin
                Sum[15:2] = A[15:2] + B[15:2]
                            + (A[1] & B[1]);

                Sum[1:0] = A[1:0] ^ B[1:0];
            end

	    // Level 2
            2'd2: begin
                Sum[15:4] = A[15:4] + B[15:4]
                            + (A[3] & B[3]);

                Sum[3:0] = A[3:0] ^ B[3:0];
            end

	    // Level 3
            2'd3: begin
                Sum[15:8] = A[15:8] + B[15:8]
                            + (A[7] & B[7]);

                Sum[7:0] = A[7:0] ^ B[7:0];
            end

            default: begin
                Sum = A + B;
            end
        endcase
    end
endmodule
