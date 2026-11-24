`timescale 1ns/1ps
module msb_approx_controller (
    input logic [7:0] A, B,
    output logic [1:0] mul_approx_level,
    output logic [1:0] add_approx_level
);
    integer msb_a, msb_b, min_msb;
    function automatic integer msb_position(input logic [7:0] value);
        integer i;
        begin
            msb_position = -1;
            for (i=0; i<8; i=i+1)
                if (value[i]) msb_position = i;
        end
    endfunction

    always_comb begin
        msb_a = msb_position(A);
        msb_b = msb_position(B);
        min_msb = (msb_a < msb_b) ? msb_a : msb_b;
        if (min_msb >= 6) mul_approx_level = 2'd3;
        else if (min_msb >= 5) mul_approx_level = 2'd2;
        else if (min_msb >= 4) mul_approx_level = 2'd1;
        else mul_approx_level = 2'd0;
        add_approx_level = 2'd0;
    end
endmodule
