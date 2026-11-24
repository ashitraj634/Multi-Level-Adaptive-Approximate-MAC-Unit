`timescale 1ns/1ps

module tb_approx_mac_fixed;

    logic        clk;
    logic        rst_n;
    logic        en;
    logic        clear;
    logic [7:0]  A, B;
    logic [15:0] acc_out;
    logic [15:0] prod_out;

    // DUT Instantiation (fixed: multiplier level 2, adder level 1)
    approx_mac_8bit_fixed DUT (
        .clk         (clk),
        .rst_n       (rst_n),
        .en          (en),
        .clear       (clear),
        .A           (A),
        .B           (B),
        .mac_result  (acc_out),
        .product_dbg (prod_out)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    localparam int BATCH_SIZE = 16;

    integer exact_acc;
    integer error;
    real    total_abs_error;
    integer max_error;
    integer error_count;
    integer total_vectors;

    // Reset Task
    task automatic reset_dut();
        rst_n = 1'b0;
        en    = 1'b0;
        clear = 1'b1;
        A     = 8'd0;
        B     = 8'd0;

        repeat (2) @(negedge clk);

        rst_n = 1'b1;
        clear = 1'b0;
        exact_acc = 0;
    endtask

    // Circular Error Function (16-bit result)
    function automatic integer circular_error(
        input integer x,
        input integer y
    );
        integer d;
        begin
            d = (x > y) ? (x - y) : (y - x);
            circular_error =
                (d < (65536 - d)) ? d : (65536 - d);
        end
    endfunction

    // Main Test and Automatic SHM Waveform Dump
    initial begin
        $shm_open("approx_mac_fixed.shm");
        $shm_probe(clk);
        $shm_probe(rst_n);
        $shm_probe(en);
        $shm_probe(clear);
        $shm_probe(A);
        $shm_probe(B);
        $shm_probe(acc_out);
        $shm_probe(prod_out);

        // Initialize DUT
        reset_dut();

        total_abs_error = 0.0;
        max_error       = 0;
        error_count     = 0;
        total_vectors   = 0;
        exact_acc       = 0;

        $display("\n==============================================");
        $display("Starting Exhaustive Testing of Fixed-Level MAC");
        $display("(Multiplier Level 2, Adder Level 1)");
        $display("==============================================\n");

        // Test all 256 x 256 input combinations
        for (int a = 0; a < 256; a++) begin
            for (int b = 0; b < 256; b++) begin

                // Clear the accumulator at each batch boundary
                if ((total_vectors % BATCH_SIZE) == 0) begin
                    clear = 1'b1;
                    exact_acc = 0;

                    @(posedge clk);
                    #1;

                    clear = 1'b0;
                end

                // Apply inputs
                A  = a[7:0];
                B  = b[7:0];
                en = 1'b1;

                // Sample after sequential logic settles
                @(posedge clk);
                #1;

                // Exact 16-bit reference MAC result
                exact_acc = (exact_acc + (a * b)) & 32'h0000_FFFF;

                error = circular_error(acc_out, exact_acc);

                total_abs_error += error;

                if (error > max_error)
                    max_error = error;

                if (error != 0)
                    error_count++;

                total_vectors++;
            end
        end

        // Final Statistics
        en = 1'b0;

        $display("\n==============================================");
        $display("Exhaustive Verification Completed.");
        $display("Total Vectors Checked       : %0d", total_vectors);

        if (total_vectors > 0) begin
            $display("Erroneous Outputs (vs Exact): %0d (%0.2f%%)",
                     error_count,
                     (100.0 * error_count) / total_vectors);

            $display("Max Absolute Error          : %0d", max_error);

            $display("Mean Absolute Error (MAE)    : %0.4f",
                     total_abs_error / total_vectors);
        end

        $display("==============================================\n");

        $finish;
    end

endmodule
