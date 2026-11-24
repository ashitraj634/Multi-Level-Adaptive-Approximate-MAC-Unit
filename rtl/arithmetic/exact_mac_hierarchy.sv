`timescale 1ns/1ps
//=====================================================================
// exact_mac_unit.sv
//
// Exact (golden reference) MAC, structurally matched to the approximate
// MAC so the two can be compared fairly for area / power / delay:
//
//     acc <= acc + (A * B)        all operations exact
//
//   exact_full_adder        1-bit full adder
//   exact_adder_16bit       16-bit ripple-carry adder (wraps, no sat)
//   exact_multiplier_8bit   8x8 -> 16 unsigned array multiplier
//   exact_mac_unit          multiplier + adder + accumulator register
//   exact_mac_unit_compat   same port list as approx_mac_unit
//                           (approx_level inputs present but ignored)
//
// Timing/behaviour identical to approx_mac_unit:
//   - async active-low reset
//   - synchronous clear, priority over en
//   - en gates the accumulate; otherwise hold
//   - 16-bit wrap-around on overflow (no saturation)
//=====================================================================


//---------------------------------------------------------------------
// 1-bit full adder
//---------------------------------------------------------------------
module exact_full_adder (
    input  logic a,
    input  logic b,
    input  logic cin,
    output logic sum,
    output logic cout
);
    assign sum  = a ^ b ^ cin;
    assign cout = (a & b) | (b & cin) | (a & cin);
endmodule


//---------------------------------------------------------------------
// 16-bit ripple-carry adder (exact). Carry-out is discarded, so the
// result wraps modulo 2^16 -- same wrap behaviour as approx_adder_16bit.
//---------------------------------------------------------------------
module exact_adder_16bit (
    input  logic [15:0] A,
    input  logic [15:0] B,
    input  logic        Cin,
    output logic [15:0] Sum,
    output logic        Cout
);
    logic [16:0] carry;
    assign carry[0] = Cin;

    genvar i;
    generate
        for (i = 0; i < 16; i++) begin : g_fa
            exact_full_adder u_fa (
                .a    (A[i]),
                .b    (B[i]),
                .cin  (carry[i]),
                .sum  (Sum[i]),
                .cout (carry[i+1])
            );
        end
    endgenerate

    assign Cout = carry[16];
endmodule


//---------------------------------------------------------------------
// 8x8 -> 16-bit unsigned exact array multiplier.
//
// Partial products pp[j] = (A & {8{B[j]}}) << j, summed with a chain
// of exact 16-bit ripple-carry adders. Every partial product bit is
// kept -- this is what makes it exact versus the truncated / OR-based
// compression used in the approximate version.
//---------------------------------------------------------------------
module exact_multiplier_8bit (
    input  logic [7:0]  A,
    input  logic [7:0]  B,
    output logic [15:0] P
);
    logic [15:0] pp   [0:7];   // aligned partial products
    logic [15:0] psum [0:7];   // running sum

    genvar j;
    generate
        for (j = 0; j < 8; j++) begin : g_pp
            assign pp[j] = {8'b0, (A & {8{B[j]}})} << j;
        end

        assign psum[0] = pp[0];

        for (j = 1; j < 8; j++) begin : g_acc
            exact_adder_16bit u_ppa (
                .A    (psum[j-1]),
                .B    (pp[j]),
                .Cin  (1'b0),
                .Sum  (psum[j]),
                .Cout ()          // cannot overflow: max 255*255 = 65025
            );
        end
    endgenerate

    assign P = psum[7];
endmodule


//---------------------------------------------------------------------
// Exact MAC top level
//---------------------------------------------------------------------
module exact_mac_unit (
    input  logic        clk,
    input  logic        rst_n,       // async active-low reset
    input  logic        en,          // accumulate this cycle
    input  logic        clear,       // sync clear, priority over en
    input  logic [7:0]  A,
    input  logic [7:0]  B,
    output logic [15:0] mac_result,  // registered accumulator
    output logic [15:0] product_dbg  // combinational product
);

    // -------- exact multiplier ----------------------------------
    logic [15:0] product;

    exact_multiplier_8bit u_mul (
        .A (A),
        .B (B),
        .P (product)
    );

    assign product_dbg = product;

    // -------- accumulator register ------------------------------
    logic [15:0] acc_q;

    // -------- exact adder ---------------------------------------
    logic [15:0] sum_comb;

    exact_adder_16bit u_add (
        .A    (acc_q),
        .B    (product),
        .Cin  (1'b0),
        .Sum  (sum_comb),
        .Cout ()               // dropped -> 16-bit wrap, no saturation
    );

    // -------- sequential accumulate -----------------------------
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            acc_q <= 16'h0000;
        else if (clear)
            acc_q <= 16'h0000;
        else if (en)
            acc_q <= sum_comb;
        // else hold
    end

    assign mac_result = acc_q;

endmodule


//---------------------------------------------------------------------
// Drop-in compatibility wrapper.
// Identical port list to approx_mac_unit, so an existing testbench can
// instantiate this instead by changing only the module name. The
// approx_level inputs are accepted and ignored (always exact).
//---------------------------------------------------------------------
module exact_mac_unit_compat (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        en,
    input  logic        clear,
    input  logic [7:0]  A,
    input  logic [7:0]  B,
    input  logic [1:0]  mul_approx_level,  // ignored
    input  logic [1:0]  add_approx_level,  // ignored
    output logic [15:0] mac_result,
    output logic [15:0] product_dbg
);
    // verilator lint_off UNUSED
    logic [1:0] unused_lvl;
    assign unused_lvl = mul_approx_level ^ add_approx_level;
    // verilator lint_on UNUSED

    exact_mac_unit u_mac (
        .clk         (clk),
        .rst_n       (rst_n),
        .en          (en),
        .clear       (clear),
        .A           (A),
        .B           (B),
        .mac_result  (mac_result),
        .product_dbg (product_dbg)
    );
endmodule
