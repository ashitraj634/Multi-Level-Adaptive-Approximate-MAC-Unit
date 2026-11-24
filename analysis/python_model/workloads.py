"""
workloads.py
============
At least 20 named workload scenarios covering the required cases.

Each workload is a dict:
  id, description, operands (list of (A,B)), enable_mask, reset_mask, initial_acc
"""
import random

def _rng(seed):
    return random.Random(seed)


def build_workloads():
    wls = []

    # WL01: Zero operands — all (0,0). Exact result always 0.
    wls.append(dict(
        id='WL01', description='All-zero operands (20 steps)',
        operands=[(0, 0)] * 20,
        enable_mask=None, reset_mask=None, initial_acc=0))

    # WL02: Very small operands [1,5]
    rng = _rng(1)
    wls.append(dict(
        id='WL02', description='Very small operands [1,5], 30 steps',
        operands=[(rng.randint(1,5), rng.randint(1,5)) for _ in range(30)],
        enable_mask=None, reset_mask=None, initial_acc=0))

    # WL03: Boundary operands for L1 truncation — products where bit-0 matters
    pairs = [(a, b) for a in range(1, 5) for b in range(1, 5)]
    wls.append(dict(
        id='WL03', description='Boundary operands for L1 truncation (A,B in {1,2,3,4})',
        operands=pairs,
        enable_mask=None, reset_mask=None, initial_acc=0))

    # WL04: Medium operands [32,96]
    rng = _rng(4)
    wls.append(dict(
        id='WL04', description='Medium operands [32,96], 40 steps',
        operands=[(rng.randint(32,96), rng.randint(32,96)) for _ in range(40)],
        enable_mask=None, reset_mask=None, initial_acc=0))

    # WL05: Large operands [192,255]
    rng = _rng(5)
    wls.append(dict(
        id='WL05', description='Large operands [192,255], 30 steps',
        operands=[(rng.randint(192,255), rng.randint(192,255)) for _ in range(30)],
        enable_mask=None, reset_mask=None, initial_acc=0))

    # WL06: Maximum operands (255,255) — maximum product per step
    wls.append(dict(
        id='WL06', description='Maximum operands (255,255), 20 steps',
        operands=[(255, 255)] * 20,
        enable_mask=None, reset_mask=None, initial_acc=0))

    # WL07: Alternating small and large
    rng = _rng(7)
    ops = []
    for _ in range(8):
        ops.append((rng.randint(1,10), rng.randint(1,10)))
        ops.append((rng.randint(200,255), rng.randint(200,255)))
    wls.append(dict(
        id='WL07', description='Alternating small and large operands, 16 steps',
        operands=ops, enable_mask=None, reset_mask=None, initial_acc=0))

    # WL08: One large (255) one small operand
    rng = _rng(8)
    wls.append(dict(
        id='WL08', description='One large (255) and one small (2..8) operand, 20 steps',
        operands=[(255, rng.randint(2,8)) for _ in range(20)],
        enable_mask=None, reset_mask=None, initial_acc=0))

    # WL09: Operands around 127/128
    rng = _rng(9)
    wls.append(dict(
        id='WL09', description='Operands around 127/128, 16 steps',
        operands=[(rng.randint(120,135), rng.randint(120,135)) for _ in range(16)],
        enable_mask=None, reset_mask=None, initial_acc=0))

    # WL10: Random mixed — general random
    rng = _rng(10)
    wls.append(dict(
        id='WL10', description='Random mixed operands, 50 steps',
        operands=[(rng.randint(0,255), rng.randint(0,255)) for _ in range(50)],
        enable_mask=None, reset_mask=None, initial_acc=0))

    # WL11: Accumulator near 32768 at start
    rng = _rng(11)
    wls.append(dict(
        id='WL11', description='Medium operands, initial_acc=32000 (near midpoint)',
        operands=[(rng.randint(20,80), rng.randint(20,80)) for _ in range(20)],
        enable_mask=None, reset_mask=None, initial_acc=32000))

    # WL12: Accumulator near 49152
    rng = _rng(12)
    wls.append(dict(
        id='WL12', description='Small operands, initial_acc=49000 (near 49152)',
        operands=[(rng.randint(1,20), rng.randint(1,20)) for _ in range(30)],
        enable_mask=None, reset_mask=None, initial_acc=49000))

    # WL13: Accumulator near 65535 (wraparound imminent)
    rng = _rng(13)
    wls.append(dict(
        id='WL13', description='Large operands, initial_acc=64000 (near 65535, wraparound risk)',
        operands=[(rng.randint(100,200), rng.randint(100,200)) for _ in range(10)],
        enable_mask=None, reset_mask=None, initial_acc=64000))

    # WL14: Accumulator wraparound — deliberately crosses 65535
    rng = _rng(14)
    wls.append(dict(
        id='WL14', description='Operands that cause accumulator to wrap around 65535',
        operands=[(200, 200)] * 5 + [(255, 255)] * 5,
        enable_mask=None, reset_mask=None, initial_acc=60000))

    # WL15: Enable pauses — alternating enabled/disabled
    rng = _rng(15)
    ops15 = [(rng.randint(10, 200), rng.randint(10, 200)) for _ in range(20)]
    en15  = [True, True, False, True, True, False, False, True, True, True,
             False, True, False, True, True, True, False, True, True, False]
    wls.append(dict(
        id='WL15', description='Enable pauses (alternating en=0), 20 steps',
        operands=ops15, enable_mask=en15, reset_mask=None, initial_acc=0))

    # WL16: Reset between sequences
    rng = _rng(16)
    ops16 = [(rng.randint(50,150), rng.randint(50,150)) for _ in range(24)]
    rst16 = [False]*8 + [True] + [False]*7 + [True] + [False]*7
    wls.append(dict(
        id='WL16', description='Reset events mid-sequence (rst at step 9 and 17)',
        operands=ops16, enable_mask=None, reset_mask=rst16, initial_acc=0))

    # WL17: Long accumulation — 100 steps, random
    rng = _rng(17)
    wls.append(dict(
        id='WL17', description='Long accumulation, 100 random steps',
        operands=[(rng.randint(0,255), rng.randint(0,255)) for _ in range(100)],
        enable_mask=None, reset_mask=None, initial_acc=0))

    # WL18: Positive error accumulation — operands that maximize truncation
    # At L1, bit-0 of each partial product zeroed. Worst case: A=B=255 (odd product corner).
    # Use A=255 odd, B=255 odd to maximise lower-bit contributions.
    rng = _rng(18)
    wls.append(dict(
        id='WL18', description='Error accumulation: A,B always odd (maximize truncation effect)',
        operands=[(2*rng.randint(1,127)+1, 2*rng.randint(1,127)+1) for _ in range(40)],
        enable_mask=None, reset_mask=None, initial_acc=0))

    # WL19: Near-zero accumulator after reset, small increments
    wls.append(dict(
        id='WL19', description='Acc near zero (initial=5), small operands [1,3]',
        operands=[(1,1),(1,2),(2,2),(1,3),(2,3),(3,3),(1,1),(2,2)],
        enable_mask=None, reset_mask=None, initial_acc=5))

    # WL20: Operands where A=0 or B=0 (no contribution)
    ops20 = [(0,255),(255,0),(0,0),(128,0),(0,128),(50,0),(0,50),(0,0),(255,255),(0,100)]
    wls.append(dict(
        id='WL20', description='One or both operands = 0 (zero-product steps)',
        operands=ops20, enable_mask=None, reset_mask=None, initial_acc=1000))

    # WL21: Single large step to test max-error case
    wls.append(dict(
        id='WL21', description='Single step: A=7, B=7 (worst-case L3 mult error)',
        operands=[(7, 7)], enable_mask=None, reset_mask=None, initial_acc=0))

    # WL22: Steps designed to expose adder carry-suppression (products ending in 11..1 in low bits)
    # Product A*B where lower bits are all 1: e.g. A=3,B=5=0b101,product=15=0b1111
    wls.append(dict(
        id='WL22', description='Products designed to expose adder XOR-carry suppression, 16 steps',
        operands=[(3,5),(5,7),(7,9),(9,11),(11,13),(3,21),(5,13),(7,9),
                  (3,5),(5,7),(7,9),(9,11),(3,21),(5,13),(7,9),(3,5)],
        enable_mask=None, reset_mask=None, initial_acc=0))

    # WL23: Monotonic decrease accumulator pattern (simulate repeated small values)
    rng = _rng(23)
    wls.append(dict(
        id='WL23', description='Monotonic small increments, 60 steps [1,8]',
        operands=[(rng.randint(1,8), rng.randint(1,8)) for _ in range(60)],
        enable_mask=None, reset_mask=None, initial_acc=0))

    # WL24: Uniform full-range random (calibration-held-out seed)
    rng = _rng(999)  # different seed from calibration seeds above
    wls.append(dict(
        id='WL24', description='Held-out: uniform random full-range, 80 steps',
        operands=[(rng.randint(0,255), rng.randint(0,255)) for _ in range(80)],
        enable_mask=None, reset_mask=None, initial_acc=0))

    # WL25: Adversarial for adder — products with maximum low-bit density
    # A = 0b11111111 (255), B values that produce max low bits in product
    wls.append(dict(
        id='WL25', description='Adversarial adder: A=255 with B in {1,3,5,7,...}, 20 steps',
        operands=[(255, 2*k+1) for k in range(20)],
        enable_mask=None, reset_mask=None, initial_acc=0))

    return wls
