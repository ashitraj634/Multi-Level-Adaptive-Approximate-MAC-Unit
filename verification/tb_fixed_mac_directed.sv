`timescale 1ns/1ps
//------------------------------------------------------------------------------
// Self-checking testbench for approx_mac_8bit_fixed (mul L2, add L1)
// Reference models are written independently of the RTL.
//------------------------------------------------------------------------------
module tb_approx_mac_8bit_fixed;

    logic        clk = 0, rst_n, en, clear;
    logic [7:0]  A, B;
    logic [15:0] mac_result, product_dbg;

    approx_mac_8bit_fixed dut (.*);

    always #5 clk = ~clk;

    // ---------------- reference models ----------------
    logic [15:0] acc_model;
    int errors = 0, checks = 0;

    function automatic logic [15:0] mul_ref(input logic [7:0] a, b);
        logic [15:0] r = 16'd0;
        for (int i = 0; i < 8; i++)
            for (int j = 0; j < 8; j++)
                if (i + j >= 2 && a[j] && b[i])
                    r += 16'd1 << (i + j);
        return r;
    endfunction

    function automatic logic [15:0] add_ref(input logic [15:0] x, y);
        logic [13:0] hi;
        hi = x[15:2] + y[15:2] + 14'(x[1] & y[1]);
        return {hi, x[1:0] ^ y[1:0]};
    endfunction

    task automatic check(input string name);
        checks++;
        if (product_dbg !== mul_ref(A, B) || mac_result !== acc_model) begin
            errors++;
            $display("[FAIL] %-28s A=%0d B=%0d | prod=%0d (exp %0d) | mac=%0d (exp %0d)",
                     name, A, B, product_dbg, mul_ref(A,B), mac_result, acc_model);
        end else
            $display("[PASS] %-28s A=%3d B=%3d | prod=%5d | mac=%5d",
                     name, A, B, product_dbg, mac_result);
    endtask

    // one clock cycle with given stimulus, then compare
    task automatic cycle(input string name, input logic e, c,
                         input logic [7:0] a, b);
        @(negedge clk);
        en = e; clear = c; A = a; B = b;
        #1;                                   // product is combinational
        if (c)      acc_model = 16'd0;        // model the coming posedge
        else if (e) acc_model = add_ref(acc_model, mul_ref(a, b));
        @(posedge clk); #1;
        check(name);
    endtask

    initial begin
        rst_n = 0; en = 0; clear = 0; A = 0; B = 0; acc_model = 0;
        #12;

        // TC1: reset state
        checks++;
        if (mac_result !== 16'd0) begin errors++; $display("[FAIL] TC1 reset"); end
        else $display("[PASS] TC1 reset value = 0");
        rst_n = 1;

        // TC2: 0 x 0
        cycle("TC2  0 x 0",              1, 0, 8'd0,   8'd0);
        // TC3: 1 x 1 (column 0 dropped -> product 0)
        cycle("TC3  1 x 1",              1, 0, 8'd1,   8'd1);
        // TC4: 3 x 3 (exact 9, approx 4)
        cycle("TC4  3 x 3",              1, 0, 8'd3,   8'd3);
        // TC5: 15 x 15
        cycle("TC5  15 x 15",            1, 0, 8'd15,  8'd15);
        // TC6: 255 x 255 (max product)
        cycle("TC6  255 x 255",          1, 0, 8'd255, 8'd255);
        // TC7: accumulate 5 x (100 x 50)
        repeat (5) cycle("TC7  accumulate 100x50", 1, 0, 8'd100, 8'd50);
        // TC8: enable low -> accumulator must hold
        cycle("TC8  en=0 hold",          0, 0, 8'd77,  8'd88);
        // TC9: synchronous clear
        cycle("TC9  clear",              0, 1, 8'd12,  8'd34);
        // TC10: async reset in the middle of operation
        cycle("TC10a build acc",         1, 0, 8'd200, 8'd201);
        @(negedge clk); #2 rst_n = 0; #1 acc_model = 0;
        #1 check("TC10b async reset");
        rst_n = 1;
        // TC11: 300 random vectors
        for (int k = 0; k < 300; k++)
            cycle("TC11 random", 1, 0, $urandom_range(255,0), $urandom_range(255,0));

        $display("------------------------------------------------");
        $display("Checks: %0d   Errors: %0d  ->  %s", checks, errors,
                 (errors == 0) ? "ALL TESTS PASSED" : "TESTS FAILED");
        $finish;
    end

    initial begin #200000; $display("TIMEOUT"); $finish; end
endmodule
