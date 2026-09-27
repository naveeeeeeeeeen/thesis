"""
validate_sbp_gift.py - fast correctness check for the Phase 1 SBP
integration, run BEFORE committing to a multi-hour AES10 overnight batch.

Target: the 4-bit GIFT S-box, using the exact XOR/AND/OR structure given
in the paper's own Table 1 worked example (TCHES 2025/1/21, Section 3.2):

    1  r0 = x0
    2  r1 = x2
    3  g0 = AND(r0, r1)
    4  r2 = x1 (xor) g0
    5  r3 = x3
    6  g1 = AND(r2, r3)
    7  r4 = x0 (xor) g1
    8  r5 = x1 (xor) g0
    9  g2 = OR(r4, r5)
    10 r6 = x0 (xor) g1
    11 r7 = x1 (xor) x2 (xor) x3 (xor) g0 (xor) g2
    12 g3 = AND(r6, r7)
    13 y0 = x2 (xor) x3 (xor) g2          [NOT applied]
    14 y1 = x1 (xor) x2 (xor) x3 (xor) g0 (xor) g2
    15 y2 = x2 (xor) g2 (xor) g3
    16 y3 = x0 (xor) g1

GIFT is not present as a code_target_imps/*.py file in the repository (the
files present are AES10/v2/v3, AES12/v2/v3, Ascon, Saturnin, SNOW_dn,
SNOW_up), so the exact on-disk file FORMAT for that directory has not
been directly verified against a real example. Rather than guess at that
format and risk silently mis-transcribing GIFT, this script builds the
(n, m, XORs, NLs, NOTs) structure directly in Python - exactly the data
structure Extract_XOR_information.py would hand to the optimizers - and
calls Optimizer_BPD.Optimizer_with_BPD() directly, bypassing the
file-based pipeline entirely for this validation. This is a deliberate,
documented assumption per the task instructions.

Correctness is checked TWO ways for every run:
  1. Circuit_Cleanup's own automatic brute-force verification (confirms
     the cleaned circuit matches the RAW optimizer output).
  2. An INDEPENDENT ground truth: a direct, line-by-line simulation of
     the paper's own Table 1 LEFT-hand (original, sequential/in-place)
     GIFT circuit, checked against every one of the 16 possible 4-bit
     inputs. This confirms the optimizer's OUTPUT actually computes the
     real GIFT S-box, not just that Circuit_Cleanup didn't break
     whatever the optimizer produced.

Must finish in well under a minute - GIFT is tiny (n=4, k=4 nonlinear
gates, circuit as-transcribed uses 4 XOR gates for r[...] plus a handful
more for y[...], i.e. nowhere near AES/SNOW3G/Saturnin scale).
"""

import os
import time

os.makedirs('./log', exist_ok=True)

import Optimizer_BPD
import Circuit_Cleanup


# --- GIFT S-box specification, hand-transcribed from the paper's Table 1 ---
N, M, K = 4, 4, 4
NLs = ['&', '&', '|', '&']          # g0=AND, g1=AND, g2=OR, g3=AND
NOTs = ['y[0]']
XORs = {
    'r[0]': ['x[0]'],
    'r[1]': ['x[2]'],
    'r[2]': ['x[1]', 'g[0]'],
    'r[3]': ['x[3]'],
    'r[4]': ['x[0]', 'g[1]'],
    'r[5]': ['x[1]', 'g[0]'],
    'r[6]': ['x[0]', 'g[1]'],
    'r[7]': ['x[1]', 'x[2]', 'x[3]', 'g[0]', 'g[2]'],
    'y[0]': ['x[2]', 'x[3]', 'g[2]'],
    'y[1]': ['x[1]', 'x[2]', 'x[3]', 'g[0]', 'g[2]'],
    'y[2]': ['x[2]', 'g[2]', 'g[3]'],
    'y[3]': ['x[0]', 'g[1]'],
}


def gift_reference(x0, x1, x2, x3):
    """Independent ground truth: direct line-by-line simulation of the
    paper's Table 1 LEFT-hand (original, sequential/in-place) circuit."""
    x1 = x1 ^ (x0 & x2)
    t = x0 ^ (x1 & x3)
    x2 = x2 ^ (t | x1)
    x0 = x3 ^ x2
    x1 = x1 ^ x0
    x0 = x0 ^ 1
    x2 = x2 ^ (t & x1)
    x3 = t
    return (x0, x1, x2, x3)


def check_against_ground_truth(circuit):
    """Brute-force all 16 inputs of the GIFT S-box against gift_reference."""
    for x_int in range(16):
        x_bits = [(x_int >> i) & 1 for i in range(N)]
        expected = gift_reference(*x_bits)
        actual = tuple(Circuit_Cleanup.simulate_circuit(circuit, N, M, x_bits))
        if actual != expected:
            return False, x_bits, expected, actual
    return True, None, None, None


def run_one(label, sbp_pool_size):
    t0 = time.time()
    circuit, xor_count_raw = Optimizer_BPD.Optimizer_with_BPD(
        N, M, XORs, NLs, NOTs,
        log_filename=f'validate_gift_{label}', H=20,
        sbp_pool_size=sbp_pool_size)
    elapsed = time.time() - t0

    cleaned, stats = Circuit_Cleanup.clean_circuit(circuit, n=N, m=M, verbose=False)
    gt_ok, bad_input, expected, actual = check_against_ground_truth(cleaned)

    status = 'PASS' if (stats['verified'] and gt_ok) else 'FAIL'
    print(f'  {label:14s} XOR={stats["final_xor_count"]:3d}  '
          f'(raw={xor_count_raw}, cleanup_removed={stats["total_removed"]})  '
          f'self-verified={stats["verified"]}  ground-truth={gt_ok}  '
          f'time={elapsed:.3f}s  [{status}]')

    if not gt_ok:
        print(f'    !! MISMATCH on input {bad_input}: expected {expected}, got {actual}')

    return status == 'PASS'


def main():
    print('GIFT S-box validation: original selection vs. SBP pool sizes 2, 3, 5\n')
    t_start = time.time()

    configs = [
        ('original', None),
        ('sbp_pool=2', 2),
        ('sbp_pool=3', 3),
        ('sbp_pool=5', 5),
    ]

    all_pass = True
    for label, pool_size in configs:
        ok = run_one(label, pool_size)
        all_pass = all_pass and ok

    total_time = time.time() - t_start
    print(f'\nTotal validation time: {total_time:.2f}s')
    if all_pass:
        print('ALL CONFIGURATIONS PASSED - safe to proceed to the AES10 overnight batch.')
    else:
        print('!! AT LEAST ONE CONFIGURATION FAILED - DO NOT run the overnight batch '
              'until this is fixed.')


if __name__ == '__main__':
    main()
