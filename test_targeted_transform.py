"""
test_targeted_transform.py - fast sanity check for the corrected
Modification_Circuits.Modify_circuits (targeted greedy selection).

Confirms it TERMINATES quickly on AES10 (the previous random
rejection-sampling version hung for 25+ hours) and reports whether
the transformations reduce the estimated XOR count.

Run:  python3 test_targeted_transform.py
"""
import time
import Change_Circuit_Formal
import Extract_XOR_information
import Modification_Circuits


def main():
    filename = 'AES10'
    n, m = 8, 8  # AES S-box is 8-bit -> 8-bit

    Change_Circuit_Formal.circuit_formal(n, m, filename)
    XORs, NLs, NOTs = Extract_XOR_information.extract_XOR_NOTs(n, m, filename)

    origin_depth = Modification_Circuits.estimate_depth(n, m, XORs, NLs, NOTs)
    origin_xor = Modification_Circuits._xor_count(XORs)
    print(f'AES10 original : XOR_estimate={origin_xor}, depth={origin_depth}, '
          f'nonlinear_gates={len(NLs)}')

    t0 = time.time()
    new_XORs, new_NLs, new_NOTs, new_depth = Modification_Circuits.Modify_circuits(
        n, m, XORs, NLs, NOTs)
    elapsed = time.time() - t0

    new_xor = Modification_Circuits._xor_count(new_XORs)
    print(f'AES10 modified : XOR_estimate={new_xor}, depth={new_depth}, '
          f'nonlinear_gates={len(new_NLs)}')
    print(f'Elapsed time   : {elapsed:.3f}s  (MUST be seconds, not hours)')

    if new_xor < origin_xor:
        print(f'XOR estimate reduced by {origin_xor - new_xor} '
              f'({origin_xor} -> {new_xor}) - transformations helped the starting form.')
    else:
        print(f'XOR estimate unchanged ({origin_xor} -> {new_xor}) - '
              f'the original form is already a local optimum under these transforms.')

    # Invariants that MUST hold for the result to be usable downstream
    assert len(new_NLs) == len(NLs), 'nonlinear gate count changed - BUG!'
    assert elapsed < 60, 'Modify_circuits took too long - still broken!'
    print('\nOK: Modify_circuits terminated quickly and preserved the nonlinear gate count.')


if __name__ == '__main__':
    main()